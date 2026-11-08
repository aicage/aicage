"""GnuPG credential-forwarding operations."""

import os
import subprocess  # nosec B404 -- GnuPG readiness uses a fixed host command.
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from shutil import copy2, which

from aicage._logging import get_logger
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig
from aicage.docker.errors import DockerError
from aicage.gpg import (
    resolve_gpg_agent_socket,
    resolve_gpg_home,
    resolve_gpg_public_files,
)
from aicage.gpg import (
    resolve_gpg_secret_key_state as _resolve_host_gpg_secret_key_state,
)
from aicage.paths import container_project_path
from aicage.runtime.run_args import BindMountSpec, MountSpec, VolumeMountSpec

from ._resource_gpg import (
    _gpg_fingerprints,
    _gpg_key_is_usable,
    _gpg_keygrips,
    _gpg_source_keygrips,
    _load_gpg_key_interactively,
    _reset_gpg_agent,
)
from ._resource_models import _CredentialProtocol, _CredentialResource

_GPG_SOCKET_NAME = "S.gpg-agent"
_GPG_CONNECT_AGENT = which("gpg-connect-agent")
_GPG = which("gpg")
_GPG_STAGING_HOME = PurePosixPath("/run/aicage/gnupg-staging")
_GPG_SOCKET_DIRECTORY = PurePosixPath("/run/aicage/gnupg-socket")
_GPG_SOCKET_PATH = _GPG_SOCKET_DIRECTORY / _GPG_SOCKET_NAME


@dataclass
class _GpgForwardingPlan:
    credential_home: Path
    requires_sidecar: bool
    direct_socket: Path | None = None

    @contextmanager
    def sidecar_target_args(
        self, resource: _CredentialResource
    ) -> Iterator[list[MountSpec]]:
        with _gpg_sidecar_target_args(resource, self.credential_home) as args:
            yield args

    @contextmanager
    def direct_target_args(self) -> Iterator[list[MountSpec]]:
        if self.direct_socket is None:
            raise RuntimeError("The GnuPG forwarding plan has no direct agent socket.")
        with _gpg_direct_target_args(self.direct_socket, self.credential_home) as args:
            yield args


def _gpg_enabled(context: ConfigContext, agent: str) -> bool:
    agent_cfg = context.project_cfg.agents.get(agent, AgentConfig())
    return agent_cfg.mounts.gnupg is True


def _gpg_forwarding() -> _GpgForwardingPlan | None:
    gpg_home = resolve_gpg_home()
    if gpg_home is None:
        return None
    socket = _direct_gpg_socket()
    if socket is not None:
        return _GpgForwardingPlan(
            gpg_home,
            False,
            socket,
        )
    return _GpgForwardingPlan(gpg_home, True)


def _reload_gpg_keys(
    resources: list[_CredentialResource],
    *,
    interactive: bool,
) -> None:
    resource = next(
        (item for item in resources if item.protocol is _CredentialProtocol.GPG), None
    )
    if resource is None:
        return
    keygrips = _gpg_source_keygrips(resource)
    if _gpg_keygrips(resource) != keygrips:
        _reset_gpg_agent(resource)
    fingerprints = _gpg_fingerprints(resource)
    for fingerprint in fingerprints:
        if _gpg_key_is_usable(resource, fingerprint):
            continue
        if not interactive:
            _warn_unavailable_gpg_key(fingerprint, "credential sidecar")
            continue
        try:
            _load_gpg_key_interactively(resource, fingerprint)
        except DockerError:
            _warn_unavailable_gpg_key(fingerprint, "credential sidecar")
            continue
        if not _gpg_key_is_usable(resource, fingerprint):
            _warn_unavailable_gpg_key(fingerprint, "credential sidecar")


def _prepare_direct_gpg_keys(gpg_home: Path, *, interactive: bool) -> None:
    """Make host keys available when possible without blocking startup."""
    fingerprints, _keygrips = _resolve_host_gpg_secret_key_state()
    with tempfile.TemporaryDirectory(prefix="aicage-gpg-") as directory:
        message = Path(directory) / "message"
        message.write_text("aicage GnuPG credential preparation\n", encoding="utf-8")
        for fingerprint in fingerprints:
            signature = Path(directory) / f"{fingerprint}.sig"
            if _sign_with_direct_gpg(gpg_home, fingerprint, message, signature):
                continue
            if not interactive:
                _warn_unavailable_gpg_key(fingerprint, "host GnuPG agent")
                continue
            if not _sign_with_direct_gpg_interactively(
                gpg_home, fingerprint, message, signature
            ):
                _warn_unavailable_gpg_key(fingerprint, "host GnuPG agent")


def _sign_with_direct_gpg(
    gpg_home: Path,
    fingerprint: str,
    message: Path,
    signature: Path,
) -> bool:
    command = [
        _gpg(),
        "--batch",
        "--pinentry-mode",
        "error",
    ]
    command.extend(
        [
            "--homedir",
            str(gpg_home),
            "--local-user",
            fingerprint,
            "--detach-sign",
            "--output",
            str(signature),
            str(message),
        ]
    )
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603 -- The fixed GnuPG executable receives an argument vector, never a shell command.
    return result.returncode == 0


def _sign_with_direct_gpg_interactively(
    gpg_home: Path,
    fingerprint: str,
    message: Path,
    signature: Path,
) -> bool:
    result = subprocess.run(
        [
            _gpg(),
            "--homedir",
            str(gpg_home),
            "--local-user",
            fingerprint,
            "--detach-sign",
            "--output",
            str(signature),
            str(message),
        ],
        check=False,
    )  # nosec B603 -- The fixed GnuPG executable receives an argument vector, never a shell command.
    return result.returncode == 0


def _gpg() -> str:
    if _GPG is None:
        raise RuntimeError("GnuPG is required to prepare GnuPG credentials.")
    return _GPG


def _warn_unavailable_gpg_key(fingerprint: str, destination: str) -> None:
    get_logger().warning(
        "GnuPG key '%s' is unavailable in the %s; continuing without it.",
        fingerprint,
        destination,
    )


@contextmanager
def _gpg_sidecar_target_args(
    resource: _CredentialResource,
    gpg_home: Path,
) -> Iterator[list[MountSpec]]:
    with tempfile.TemporaryDirectory(
        dir=gpg_home.parent, prefix=".aicage-gpg-"
    ) as directory:
        client_home = Path(directory)
        _copy_gpg_support_files(gpg_home, client_home)
        yield [
            BindMountSpec(client_home, _GPG_STAGING_HOME),
            *_external_gpg_support_mounts(gpg_home),
            VolumeMountSpec(resource.volume_name, _GPG_SOCKET_DIRECTORY, True),
        ]


@contextmanager
def _gpg_direct_target_args(socket: Path, gpg_home: Path) -> Iterator[list[MountSpec]]:
    with tempfile.TemporaryDirectory(
        dir=gpg_home.parent, prefix=".aicage-gpg-"
    ) as directory:
        client_home = Path(directory)
        _copy_gpg_support_files(gpg_home, client_home)
        yield [
            BindMountSpec(client_home, _GPG_STAGING_HOME),
            BindMountSpec(socket, _GPG_SOCKET_PATH),
            *_external_gpg_support_mounts(gpg_home),
        ]


def _gpg_support_mounts(gpg_home: Path) -> list[BindMountSpec]:
    return [
        BindMountSpec(path, container_project_path(path), True)
        for path in resolve_gpg_public_files(gpg_home)
    ]


def _copy_gpg_support_files(gpg_home: Path, client_home: Path) -> None:
    for path in resolve_gpg_public_files(gpg_home):
        try:
            relative_path = path.relative_to(gpg_home)
        except ValueError:
            continue
        destination = client_home / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy2(path, destination)


def _external_gpg_support_mounts(gpg_home: Path) -> list[BindMountSpec]:
    return [
        BindMountSpec(path, container_project_path(path), True)
        for path in resolve_gpg_public_files(gpg_home)
        if not path.is_relative_to(gpg_home)
    ]


def _direct_gpg_socket() -> Path | None:
    if os.name == "nt" or _GPG is None or _GPG_CONNECT_AGENT is None:
        return None
    socket = resolve_gpg_agent_socket()
    if socket is None:
        return None
    if not socket.is_socket():
        raise RuntimeError(
            f"The configured host GnuPG agent socket is not a Unix socket: '{socket}'."
        )
    result = subprocess.run(
        [_GPG_CONNECT_AGENT, "--raw-socket", str(socket), "/bye"],
        check=False,
        capture_output=True,
        text=True,
    )  # nosec B603 -- The fixed gpg-connect-agent executable receives an argument vector, never a shell command.
    if result.returncode != 0:
        raise RuntimeError(
            f"Cannot communicate with the host GnuPG agent at '{socket}'."
        )
    return socket
