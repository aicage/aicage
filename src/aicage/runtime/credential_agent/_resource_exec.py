"""Shared Docker exec operations for credential sidecars."""

import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import TextIO

from docker.client import DockerClient

from aicage.docker.errors import DockerError

_EXEC_COMPLETION_TIMEOUT_SECONDS = 10
_EXEC_COMPLETION_POLL_SECONDS = 0.05


@contextmanager
def terminal_streams() -> Iterator[tuple[TextIO, TextIO]]:
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        raise DockerError("An interactive terminal is required to load credentials.")
    yield sys.stdin, sys.stdout


def write_exec_input(stream: object, content: bytes) -> None:
    for socket in (stream, getattr(stream, "_sock", None)):
        sendall = getattr(socket, "sendall", None)
        if callable(sendall):
            sendall(content)
            return
    write = getattr(stream, "write", None)
    writable = getattr(stream, "writable", None)
    if not callable(write) or (callable(writable) and not writable()):
        raise OSError("Docker exec stream does not support stdin.")
    remaining = content
    while remaining:
        written = write(remaining)
        if written is None:
            return
        if not isinstance(written, int) or written <= 0:
            raise OSError("Docker exec stream rejected stdin.")
        remaining = remaining[written:]


def close_exec_stream(stream: object) -> None:
    response = getattr(stream, "_response", None)
    response_close = getattr(response, "close", None)
    if callable(response_close):
        response_close()
    close = getattr(stream, "close", None)
    if callable(close):
        close()


def wait_for_exec_completion(
    client: DockerClient, execution_id: str
) -> dict[str, object]:
    deadline = time.monotonic() + _EXEC_COMPLETION_TIMEOUT_SECONDS
    while True:
        result = client.api.exec_inspect(execution_id)
        if not result.get("Running") and result.get("ExitCode") is not None:
            return result
        if time.monotonic() >= deadline:
            return result
        time.sleep(_EXEC_COMPLETION_POLL_SECONDS)
