"""Credential-agent container identity helpers."""

import os

from aicage.docker.runtime import is_rootless_docker


def _credential_agent_user() -> str:
    if os.name == "nt" or is_rootless_docker():
        return "0:0"
    uid = _resolve_host_user_id("getuid")
    gid = _resolve_host_user_id("getgid")
    if uid is None or gid is None:
        return "0:0"
    return f"{uid}:{gid}"


def _resolve_host_user_id(method_name: str) -> int | None:
    method = vars(os).get(method_name)
    if not callable(method):
        return None
    value = method()
    return value if isinstance(value, int) else None
