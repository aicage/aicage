import os
import subprocess  # nosec B404 -- subprocess is the intended wrapper for Docker CLI execution.
from typing import Literal, TextIO, overload

from aicage._execution_cleanup import register_process
from aicage.docker.errors import DockerError


def run_docker_command(
    command: list[str],
    *,
    check: bool,
    stdin: TextIO | int | None = None,
    stdout: TextIO | int | None = None,
    stderr: TextIO | int | None = None,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    try:
        with subprocess.Popen(  # nosec B603 -- command is a caller-built Docker CLI argv list without shell usage.
            command,
            stdin=stdin,
            stdout=stdout,
            stderr=stderr,
            env=docker_cli_environment(),
        ) as process:
            register_process(process)
            process.wait()
            result: (
                subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]
            ) = subprocess.CompletedProcess(command, process.returncode)
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(result.returncode, command)
        return result
    except FileNotFoundError as exc:
        raise DockerError(
            "Docker CLI not found. Install Docker and ensure it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise DockerError(
            f"Docker command failed with exit code {exc.returncode}."
        ) from exc


def docker_cli_environment() -> dict[str, str]:
    return {**os.environ, "DOCKER_CLI_HINTS": "false"}


@overload
def run_docker_command_capture(
    command: list[str],
    *,
    check: bool,
    text: Literal[True],
) -> subprocess.CompletedProcess[str]: ...


@overload
def run_docker_command_capture(
    command: list[str],
    *,
    check: bool,
    text: Literal[False],
) -> subprocess.CompletedProcess[bytes]: ...


def run_docker_command_capture(
    command: list[str],
    *,
    check: bool,
    text: bool,
) -> subprocess.CompletedProcess[str] | subprocess.CompletedProcess[bytes]:
    try:
        with subprocess.Popen(  # nosec B603 -- command is a caller-built Docker CLI argv list without shell usage.
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=text,
            env=docker_cli_environment(),
        ) as process:
            register_process(process)
            stdout, stderr = process.communicate()
            result = subprocess.CompletedProcess(
                command,
                process.returncode,
                stdout=stdout,
                stderr=stderr,
            )
        if check and result.returncode != 0:
            raise subprocess.CalledProcessError(
                result.returncode,
                command,
                output=result.stdout,
                stderr=result.stderr,
            )
        return result
    except FileNotFoundError as exc:
        raise DockerError(
            "Docker CLI not found. Install Docker and ensure it is on PATH."
        ) from exc
    except subprocess.CalledProcessError as exc:
        raise DockerError(
            f"Docker command failed with exit code {exc.returncode}."
        ) from exc
