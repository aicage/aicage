import json
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from aicage.docker.execution.cli import run_docker_command_capture
from aicage.paths import HOST_DOCKER_SOCKET_PATH
from aicage.runtime.env_vars import DOCKER_HOST

_DEFAULT_DOCKER_HOST = f"unix://{HOST_DOCKER_SOCKET_PATH.as_posix()}"


@dataclass(frozen=True)
class _DockerHostSpec:
    host: str
    socket_path: Path | None
    named_pipe_path: Path | None


@lru_cache(maxsize=1)
def get_active_docker_host() -> _DockerHostSpec:
    env_host = os.environ.get(DOCKER_HOST)
    if env_host:
        return _parse_docker_host(env_host)

    context_host = _read_active_context_docker_host()
    if context_host:
        return _parse_docker_host(context_host)

    return _parse_docker_host(_DEFAULT_DOCKER_HOST)


@lru_cache(maxsize=1)
def is_rootless_docker() -> bool:
    if os.name != "posix":
        return False

    try:
        process = run_docker_command_capture(
            ["docker", "info", "--format", "{{json .SecurityOptions}}"],
            check=True,
            text=True,
        )
    except Exception:
        return False

    try:
        security_options = json.loads(process.stdout.strip() or "[]")
    except json.JSONDecodeError:
        return False

    return any("rootless" in str(option).lower() for option in security_options)


def _read_active_context_docker_host() -> str | None:
    try:
        process = run_docker_command_capture(
            [
                "docker",
                "context",
                "inspect",
                "--format",
                "{{json .Endpoints.docker.Host}}",
            ],
            check=True,
            text=True,
        )
    except Exception:
        return None

    output = process.stdout.strip()
    if not output:
        return None

    try:
        host = json.loads(output)
    except json.JSONDecodeError:
        return None

    return host if isinstance(host, str) and host else None


def _parse_unix_socket_path(host: str) -> Path | None:
    prefix = "unix://"
    if not host.startswith(prefix):
        return None
    path = host[len(prefix) :]
    if not path:
        return None
    return Path(path)


def _parse_docker_host(host: str) -> _DockerHostSpec:
    return _DockerHostSpec(
        host=host,
        socket_path=_parse_unix_socket_path(host),
        named_pipe_path=_parse_named_pipe_path(host),
    )


def _parse_named_pipe_path(host: str) -> Path | None:
    prefix = "npipe:////"
    if not host.startswith(prefix):
        return None
    path = host[len(prefix) :]
    if not path:
        return None
    return Path("\\\\" + path.replace("/", "\\"))
