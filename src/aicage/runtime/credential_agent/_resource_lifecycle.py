"""Docker lifecycle operations for credential sidecars."""

import time
from collections.abc import Iterator
from contextlib import contextmanager
from os import name as _os_name
from pathlib import Path, PurePosixPath, PureWindowsPath

import portalocker
from docker.client import DockerClient
from docker.errors import DockerException, NotFound
from docker.models.containers import Container
from docker.models.volumes import Volume

from aicage.docker.errors import DockerError
from aicage.paths import CREDENTIAL_AGENT_LOCK_PATH, container_project_path

from ._resource_models import (
    _IMAGE_ID_LABEL,
    _OWNER_LABEL,
    _PROTOCOL_LABEL,
    _RESOURCE_LABEL,
    _RESOURCE_VALUE,
    _CredentialProtocol,
    _CredentialResource,
    _ImageSpec,
)

_LOCK_TIMEOUT_SECONDS = 30
_READY_TIMEOUT_SECONDS = 10
_READY_POLL_SECONDS = 0.1


def _ensure_volume(client: DockerClient, resource: _CredentialResource) -> Volume:
    try:
        volume = client.volumes.get(resource.volume_name)
    except NotFound:
        volume = client.volumes.create(
            name=resource.volume_name, labels=_labels(resource, None)
        )
    if not _is_owned(volume, resource):
        raise DockerError(
            f"Credential socket volume '{resource.volume_name}' is not owned by aicage."
        )
    return volume


def _find_container(
    client: DockerClient, resource: _CredentialResource
) -> Container | None:
    try:
        return client.containers.get(resource.container_name)
    except NotFound:
        return None


def _requires_replacement(
    container: Container,
    resource: _CredentialResource,
    image_id: str,
    credential_path: Path | None,
) -> bool:
    if not _is_owned(container, resource):
        raise DockerError(
            f"Credential sidecar '{resource.container_name}' is not owned by aicage."
        )
    labels = _labels_for(container)
    return labels.get(_IMAGE_ID_LABEL) != image_id or not _credential_mount_matches(
        container, resource, credential_path
    )


def _create_container(
    client: DockerClient,
    resource: _CredentialResource,
    volume: Volume,
    image: _ImageSpec,
    credential_path: Path | None,
) -> Container:
    volumes = {
        volume.name: {"bind": resource.socket_directory.as_posix(), "mode": "rw"}
    }
    if credential_path is not None:
        volumes[str(credential_path)] = {
            "bind": resource.credential_directory.as_posix(),
            "mode": "ro",
        }
    tmpfs = _ssh_tmpfs_mounts(resource, credential_path, image.user)
    return client.containers.run(
        image.image_ref,
        [resource.protocol.value, "serve"],
        detach=True,
        name=resource.container_name,
        labels=_labels(resource, image.image_id),
        environment=_credential_agent_environment(image.user),
        volumes=volumes,
        tmpfs=tmpfs,
        network_disabled=True,
    )


def _ssh_tmpfs_mounts(
    resource: _CredentialResource,
    credential_path: Path | None,
    user: str,
) -> dict[str, str]:
    if resource.protocol is not _CredentialProtocol.SSH or credential_path is None:
        return {}
    uid, separator, gid = user.partition(":")
    if not separator:
        gid = uid
    return {
        container_project_path(credential_path).as_posix(): (
            f"rw,uid={uid},gid={gid},mode=0700"
        )
    }


def _ensure_ready(
    client: DockerClient, resource: _CredentialResource, container: Container
) -> None:
    deadline = time.monotonic() + _READY_TIMEOUT_SECONDS
    while True:
        try:
            created = client.api.exec_create(
                container.id,
                ["credential-agent", resource.protocol.value, "ready"],
                user=resource.user,
            )
            execution_id = created["Id"]
            client.api.exec_start(execution_id)
            result = client.api.exec_inspect(execution_id)
            if result.get("ExitCode") == 0:
                return
        except DockerException as exc:
            raise DockerError(
                f"Credential sidecar '{resource.container_name}' did not become ready."
            ) from exc
        if time.monotonic() >= deadline:
            raise DockerError(
                f"Credential sidecar '{resource.container_name}' did not become ready."
            )
        time.sleep(_READY_POLL_SECONDS)


def _is_stopped(container: Container) -> bool:
    container.reload()
    return _state_for(container).get("Status") != "running"


def _labels(resource: _CredentialResource, image_id: str | None) -> dict[str, str]:
    labels = {
        _RESOURCE_LABEL: _RESOURCE_VALUE,
        _PROTOCOL_LABEL: resource.protocol.value,
        _OWNER_LABEL: resource.owner,
    }
    if image_id is not None:
        labels[_IMAGE_ID_LABEL] = image_id
    return labels


def _is_owned(resource: Container | Volume, expected: _CredentialResource) -> bool:
    labels = _labels_for(resource)
    return (
        labels.get(_RESOURCE_LABEL) == _RESOURCE_VALUE
        and labels.get(_PROTOCOL_LABEL) == expected.protocol.value
        and labels.get(_OWNER_LABEL) == expected.owner
    )


def _labels_for(resource: Container | Volume) -> dict[str, str]:
    labels = getattr(resource, "labels", None)
    if isinstance(labels, dict):
        return {
            key: value
            for key, value in labels.items()
            if isinstance(key, str) and isinstance(value, str)
        }
    attrs = getattr(resource, "attrs", {})
    if not isinstance(attrs, dict):
        return {}
    labels = attrs.get("Labels", {})
    if not isinstance(labels, dict):
        config = attrs.get("Config", {})
        labels = config.get("Labels", {}) if isinstance(config, dict) else {}
    return (
        {
            key: value
            for key, value in labels.items()
            if isinstance(key, str) and isinstance(value, str)
        }
        if isinstance(labels, dict)
        else {}
    )


def _state_for(container: Container) -> dict[str, object]:
    attrs = getattr(container, "attrs", {})
    state = attrs.get("State", {}) if isinstance(attrs, dict) else {}
    return state if isinstance(state, dict) else {}


def _credential_mount_path(
    container: Container, resource: _CredentialResource
) -> Path | None:
    attrs = getattr(container, "attrs", {})
    mounts = attrs.get("Mounts", []) if isinstance(attrs, dict) else []
    if not isinstance(mounts, list):
        return None
    for mount in mounts:
        if (
            isinstance(mount, dict)
            and mount.get("Destination") == resource.credential_directory.as_posix()
        ):
            source = mount.get("Source")
            return Path(source) if isinstance(source, str) else None
    return None


def _credential_mount_matches(
    container: Container,
    resource: _CredentialResource,
    credential_path: Path | None,
) -> bool:
    source = _credential_mount_path(container, resource)
    if source == credential_path:
        return True
    if _os_name != "nt" or credential_path is None or source is None:
        return False
    return (
        source.as_posix().casefold()
        == _docker_desktop_host_path(credential_path).as_posix().casefold()
    )


def _credential_agent_environment(user: str) -> dict[str, str]:
    uid, _, gid = user.partition(":")
    return {"AICAGE_UID": uid, "AICAGE_GID": gid or uid}


def _docker_desktop_host_path(path: Path) -> PurePosixPath:
    windows_path = PureWindowsPath(path)
    drive = windows_path.drive.rstrip(":").lower()
    parts = [part for part in windows_path.parts if part != windows_path.anchor]
    return PurePosixPath("/run/desktop/mnt/host", drive, *parts)


@contextmanager
def _resource_lock() -> Iterator[None]:
    CREDENTIAL_AGENT_LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with portalocker.Lock(
            str(CREDENTIAL_AGENT_LOCK_PATH), timeout=_LOCK_TIMEOUT_SECONDS, mode="a+"
        ):
            yield
    except portalocker.exceptions.LockException as exc:
        raise DockerError("Failed to lock credential-agent resources.") from exc
