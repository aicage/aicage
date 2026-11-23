from pathlib import Path, PurePosixPath

from aicage.paths import container_project_path
from aicage.runtime.run_args import BindMountSpec

from .resolver_types import MountRequest


def map_mount_requests(requests: list[MountRequest]) -> list[BindMountSpec]:
    deduped_requests = _dedupe_exact_mount_requests(requests)
    # Process shallower paths first so parents are seen before children.
    # That makes nested deduplication one-directional.
    sorted_requests = _sort_mount_requests(deduped_requests)
    selected_requests = _dedupe_nested_mount_requests(sorted_requests)
    return _build_mount_specs(selected_requests)


def _dedupe_exact_mount_requests(requests: list[MountRequest]) -> list[MountRequest]:
    deduped_requests: dict[tuple[Path, PurePosixPath | None], MountRequest] = {}
    for request in requests:
        host_path = _host_path(request)
        key = (host_path, request.container_path)
        if key in deduped_requests:
            continue
        deduped_requests[key] = MountRequest(
            host_path=host_path,
            read_only=request.read_only,
            container_path=request.container_path,
        )
    return list(deduped_requests.values())


def _dedupe_nested_mount_requests(requests: list[MountRequest]) -> list[MountRequest]:
    selected_requests: list[MountRequest] = []
    for request in requests:
        host_path = _host_path(request)
        if any(
            _is_redundant_nested_mount(
                request, selected, host_path, _host_path(selected)
            )
            for selected in selected_requests
        ):
            continue
        selected_requests.append(request)
    return selected_requests


def _build_mount_specs(requests: list[MountRequest]) -> list[BindMountSpec]:
    mounts: list[BindMountSpec] = []
    for request in requests:
        host_path = _host_path(request)
        container_path = request.container_path or container_project_path(host_path)
        mounts.append(
            BindMountSpec(
                host_path=host_path,
                container_path=container_path,
                read_only=request.read_only,
            )
        )
    return mounts


def _sort_mount_requests(requests: list[MountRequest]) -> list[MountRequest]:
    return sorted(
        requests,
        key=lambda request: (
            len(_host_path(request).parts),
            _host_path(request).as_posix(),
        ),
    )


def _host_path(request: MountRequest) -> Path:
    if request.container_path is not None:
        return request.host_path
    return request.host_path.resolve()


def _is_redundant_nested_mount(
    nested_request: MountRequest,
    parent_request: MountRequest,
    nested_host_path: Path,
    parent_host_path: Path,
) -> bool:
    return nested_request.read_only == parent_request.read_only and _is_path_within(
        nested_host_path, parent_host_path
    )


def _is_path_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False
