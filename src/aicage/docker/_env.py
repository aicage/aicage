import os
from pathlib import Path

from aicage.docker.runtime import _is_rootless_docker
from aicage.paths import container_project_path
from aicage.runtime.env_vars import (
    AICAGE_GID,
    AICAGE_HOME,
    AICAGE_HOST_USER,
    AICAGE_MOUNT_HOME,
    AICAGE_UID,
)


def resolve_user_ids() -> list[str]:
    env_flags: list[str] = []
    host_home = _resolve_host_home()
    host_home_posix = container_project_path(host_home).as_posix()
    if os.name == "nt":
        env_flags.extend(
            [
                "-e",
                f"{AICAGE_UID}=0",
                "-e",
                f"{AICAGE_GID}=0",
                "-e",
                f"{AICAGE_HOST_USER}=root",
                "-e",
                f"{AICAGE_HOME}=/root",
                "-e",
                f"{AICAGE_MOUNT_HOME}={host_home_posix}",
            ]
        )
        return env_flags

    uid, gid = _resolve_host_user_ids()
    is_rootless = _is_rootless_docker()

    user = _resolve_host_user()
    if uid is not None and not is_rootless:
        env_flags.extend(["-e", f"{AICAGE_UID}={uid}", "-e", f"{AICAGE_GID}{'='}{gid}"])
    elif is_rootless:
        env_flags.extend(["-e", f"{AICAGE_UID}=0", "-e", f"{AICAGE_GID}=0"])
    env_flags.extend(["-e", f"{AICAGE_HOST_USER}={'root' if is_rootless else user}"])
    env_flags.extend(
        [
            "-e",
            f"{AICAGE_HOME}={'/root' if is_rootless else host_home_posix}",
        ]
    )
    if is_rootless:
        env_flags.extend(["-e", f"{AICAGE_MOUNT_HOME}={host_home_posix}"])
    return env_flags


def _resolve_host_user() -> str:
    return os.environ.get("USERNAME") or os.environ.get("USER") or "aicage"


def _resolve_host_user_ids() -> tuple[int | None, int | None]:
    return _resolve_host_user_id("getuid"), _resolve_host_user_id("getgid")


def _resolve_host_user_id(method_name: str) -> int | None:
    method = vars(os).get(method_name)
    if not callable(method):
        return None
    value = method()
    return value if isinstance(value, int) else None


def _resolve_host_home() -> Path:
    return Path.home()
