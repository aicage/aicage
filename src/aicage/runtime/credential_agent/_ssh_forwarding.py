"""SSH credential-forwarding operations."""

import os
import subprocess  # nosec B404 -- SSH key inspection uses fixed local commands.
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from shutil import which

from aicage._logging import get_logger
from aicage.docker.errors import DockerError
from aicage.paths import HOST_SSH_DIR, container_project_path
from aicage.runtime._ssh_agent import (
    _resolve_ssh_key_files,
    _resolve_ssh_support_files,
)
from aicage.runtime.run_args import BindMountSpec, EnvVar, MountSpec, VolumeMountSpec

from ._resource_models import _CredentialProtocol, _CredentialResource
from ._resource_ssh import (
    _list_ssh_identities,
    _load_ssh_key,
    _load_ssh_key_interactively,
    _remove_ssh_identity,
)
from ._resource_ssh import (
    _ssh_identity_fingerprint as _sidecar_ssh_identity_fingerprint,
)
from ._resource_ssh import _ssh_key_fingerprint as _sidecar_ssh_key_fingerprint
from ._resource_ssh import _ssh_key_is_encrypted as _sidecar_ssh_key_is_encrypted

_SSH_AUTH_SOCK = "SSH_AUTH_SOCK"
_SSH_SOCKET_DIRECTORY = PurePosixPath("/run/credential-agent")
_SSH_SOCKET = _SSH_SOCKET_DIRECTORY / "ssh-agent.sock"
_SSH_FINGERPRINT_FIELD = 1
_SSH_FINGERPRINT_FIELD_COUNT = 2
_SSH_ADD = which("ssh-add")
_SSH_KEYGEN = which("ssh-keygen")


@dataclass(frozen=True)
class _SshForwardingPlan:
    mounts: list[BindMountSpec]
    env: list[EnvVar]
    requires_sidecar: bool
    direct_socket: Path | None


def _ssh_forwarding() -> _SshForwardingPlan:
    support_mounts = _ssh_support_mounts()
    socket = _direct_ssh_socket()
    if socket is not None:
        return _SshForwardingPlan(
            [BindMountSpec(socket, _SSH_SOCKET), *support_mounts],
            [EnvVar(_SSH_AUTH_SOCK, _SSH_SOCKET.as_posix())],
            False,
            socket,
        )
    if not _resolve_ssh_key_files() and not HOST_SSH_DIR.is_dir():
        return _SshForwardingPlan(support_mounts, [], False, None)
    return _SshForwardingPlan(support_mounts, [], True, None)


def _prepare_ssh_forwarding(plan: _SshForwardingPlan, *, interactive: bool) -> None:
    if plan.direct_socket is not None:
        _prepare_host_ssh_agent(plan.direct_socket, interactive=interactive)


def _append_ssh_target_args(
    resource: _CredentialResource,
    mounts: list[MountSpec],
    env: list[EnvVar],
) -> None:
    mounts.append(VolumeMountSpec(resource.volume_name, _SSH_SOCKET_DIRECTORY, True))
    env.append(EnvVar(_SSH_AUTH_SOCK, _SSH_SOCKET.as_posix()))


def _ssh_support_mounts() -> list[BindMountSpec]:
    return [
        BindMountSpec(path, container_project_path(path), True)
        for path in _resolve_ssh_support_files()
    ]


def _direct_ssh_socket() -> Path | None:
    if os.name == "nt" or _SSH_ADD is None or _SSH_KEYGEN is None:
        return None
    socket_path = os.environ.get(_SSH_AUTH_SOCK)
    if not socket_path:
        return None
    socket = Path(socket_path)
    if not socket.is_socket():
        raise RuntimeError(
            f"SSH_AUTH_SOCK does not refer to a Unix socket: '{socket}'."
        )
    result = subprocess.run(
        [_SSH_ADD, "-l"],
        env=_host_ssh_env(socket),
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603 -- fixed local SSH agent probe.
    if result.returncode not in {0, 1}:
        raise RuntimeError(f"Cannot communicate with the host SSH agent at '{socket}'.")
    return socket


def _prepare_host_ssh_agent(socket: Path, *, interactive: bool) -> None:
    identities = _host_ssh_identities(socket)
    if identities is None:
        raise RuntimeError(
            f"Cannot list identities in the host SSH agent at '{socket}'."
        )
    loaded_fingerprints = {
        _ssh_identity_fingerprint(identity) for identity in identities
    }
    for key in _resolve_ssh_key_files():
        fingerprint = _ssh_key_fingerprint(key)
        if fingerprint in loaded_fingerprints:
            continue
        if _ssh_key_is_encrypted(key):
            if not interactive:
                _warn_unavailable_ssh_key(key, "host SSH agent")
                continue
            if not _load_host_ssh_key(socket, key, interactive=True):
                _warn_unavailable_ssh_key(key, "host SSH agent")
                continue
            loaded_fingerprints.add(fingerprint)
            continue
        if not _load_host_ssh_key(socket, key, interactive=interactive):
            raise RuntimeError(f"Failed to load unprotected SSH key '{key.name}'.")
        loaded_fingerprints.add(fingerprint)


def _host_ssh_identities(socket: Path) -> list[str] | None:
    if _SSH_ADD is None:
        return None
    result = subprocess.run(
        [_SSH_ADD, "-L"],
        env=_host_ssh_env(socket),
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603 -- fixed local SSH agent query.
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        return None
    return result.stdout.splitlines()


def _load_host_ssh_key(socket: Path, key: Path, *, interactive: bool) -> bool:
    if _SSH_ADD is None:
        return False
    if interactive:
        return (
            subprocess.run(  # nosec B603 -- resolved local ssh-add receives argv without shell evaluation.
                [_SSH_ADD, str(key)],
                env=_host_ssh_env(socket),
                check=False,
            ).returncode
            == 0
        )
    return (
        subprocess.run(  # nosec B603 -- resolved local ssh-add receives argv without shell evaluation.
            [_SSH_ADD, str(key)],
            env=_host_ssh_env(socket),
            check=False,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
        ).returncode
        == 0
    )


def _host_ssh_env(socket: Path) -> dict[str, str]:
    return {**os.environ, _SSH_AUTH_SOCK: str(socket)}


def _ssh_key_is_encrypted(key: Path) -> bool:
    result = subprocess.run(
        [_ssh_keygen(), "-y", "-P", "", "-f", str(key)],
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603 -- fixed local SSH key inspection.
    return result.returncode != 0


def _reload_ssh_keys(
    resources: list[_CredentialResource], *, interactive: bool
) -> None:
    resource = next(
        (item for item in resources if item.protocol is _CredentialProtocol.SSH), None
    )
    if resource is None:
        return
    desired_keys: dict[str, tuple[Path, PurePosixPath, PurePosixPath]] = {}
    for key in _resolve_ssh_key_files():
        try:
            relative_key = key.relative_to(HOST_SSH_DIR)
        except ValueError as exc:
            raise RuntimeError(
                f"SSH key '{key}' is outside {HOST_SSH_DIR} and cannot be shared safely."
            ) from exc
        sidecar_key = resource.credential_directory / relative_key
        desired_keys[_sidecar_ssh_key_fingerprint(resource, sidecar_key)] = (
            key,
            sidecar_key,
            container_project_path(key),
        )
    sidecar_keys = {
        _sidecar_ssh_identity_fingerprint(resource, identity): identity
        for identity in _list_ssh_identities(resource)
    }
    for fingerprint, identity in sidecar_keys.items():
        if fingerprint not in desired_keys:
            _remove_ssh_identity(resource, identity)
    for fingerprint, (key, sidecar_key, target_key) in desired_keys.items():
        if fingerprint not in sidecar_keys:
            try:
                _load_ssh_key(resource, sidecar_key, "", target_key)
            except DockerError:
                if not _sidecar_ssh_key_is_encrypted(resource, sidecar_key):
                    raise RuntimeError(
                        f"Failed to load unprotected SSH key '{key.name}' into the "
                        "credential sidecar."
                    ) from None
                if interactive:
                    try:
                        _load_ssh_key_interactively(resource, sidecar_key, target_key)
                    except DockerError:
                        _warn_unavailable_ssh_key(key, "credential sidecar")
                else:
                    _warn_unavailable_ssh_key(key, "credential sidecar")


def _warn_unavailable_ssh_key(key: Path, destination: str) -> None:
    get_logger().warning(
        "SSH key '%s' is unavailable in the %s; continuing without it.",
        key.name,
        destination,
    )


def _ssh_key_fingerprint(key: Path) -> str:
    public_key = key.with_name(f"{key.name}.pub")
    result = subprocess.run(
        [
            _ssh_keygen(),
            "-lf",
            str(public_key if public_key.is_file() else key),
            "-E",
            "sha256",
        ],
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603
    fields = result.stdout.split()
    if (
        result.returncode != 0
        or len(fields) < _SSH_FINGERPRINT_FIELD_COUNT
        or not fields[_SSH_FINGERPRINT_FIELD].startswith("SHA256:")
    ):
        raise RuntimeError(
            f"Cannot determine the fingerprint for SSH key '{key.name}'."
        )
    return fields[_SSH_FINGERPRINT_FIELD]


def _ssh_identity_fingerprint(identity: str) -> str:
    result = subprocess.run(
        [_ssh_keygen(), "-lf", "-", "-E", "sha256"],
        input=f"{identity}\n",
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603 -- fixed local SSH identity inspection.
    fields = result.stdout.split()
    if (
        result.returncode != 0
        or len(fields) < _SSH_FINGERPRINT_FIELD_COUNT
        or not fields[_SSH_FINGERPRINT_FIELD].startswith("SHA256:")
    ):
        raise RuntimeError(
            "Cannot determine the fingerprint for a sidecar SSH identity."
        )
    return fields[_SSH_FINGERPRINT_FIELD]


def _ssh_keygen() -> str:
    if _SSH_KEYGEN is None:
        raise RuntimeError("ssh-keygen is required to inspect SSH keys.")
    return _SSH_KEYGEN
