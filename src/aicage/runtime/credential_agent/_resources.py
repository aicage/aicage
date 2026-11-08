"""Credential-sidecar resource orchestration."""

from collections.abc import Callable, Iterable
from pathlib import Path

from aicage.docker.execution.client import get_docker_client
from aicage.paths import HOST_SSH_DIR

from ._resource_lifecycle import (
    _create_container,
    _ensure_ready,
    _ensure_volume,
    _find_container,
    _is_stopped,
    _requires_replacement,
    _resource_lock,
)
from ._resource_models import (
    _CredentialProtocol,
    _CredentialResource,
    _ImageSpec,
    _resources,
)


def _ensure_resources(
    protocols: Iterable[_CredentialProtocol],
    image: _ImageSpec,
    gpg_home: Path | None = None,
    reconcile: Callable[[list[_CredentialResource]], None] | None = None,
) -> list[_CredentialResource]:
    requested = _resources(protocols, image.user)
    if not requested:
        return []
    with _resource_lock():
        client = get_docker_client()
        for resource in requested:
            volume = _ensure_volume(client, resource)
            container = _find_container(client, resource)
            credential_path = _credential_path(resource, gpg_home)
            if container is None or _requires_replacement(
                container,
                resource,
                image.image_id,
                credential_path,
            ):
                if container is not None:
                    container.remove(force=True)
                container = _create_container(
                    client, resource, volume, image, credential_path
                )
            elif _is_stopped(container):
                container.start()
            _ensure_ready(client, resource, container)
    if reconcile is not None:
        reconcile(requested)
    return requested


def _credential_path(
    resource: _CredentialResource, gpg_home: Path | None
) -> Path | None:
    if resource.protocol is _CredentialProtocol.SSH:
        return HOST_SSH_DIR if HOST_SSH_DIR.is_dir() else None
    return gpg_home
