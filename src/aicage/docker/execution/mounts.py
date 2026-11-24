from aicage.runtime.run_args import BindMountSpec


def mount_args(mounts: list[BindMountSpec]) -> list[str]:
    args: list[str] = []
    for mount in mounts:
        args.extend(_bind_mount_args(mount))
    return args


def _bind_mount_args(mount: BindMountSpec) -> list[str]:
    parts = [
        "type=bind",
        f"src={mount.host_path.as_posix()}",
        f"dst={mount.container_path.as_posix()}",
    ]
    if mount.read_only:
        parts.append("readonly")
    return ["--mount", ",".join(parts)]
