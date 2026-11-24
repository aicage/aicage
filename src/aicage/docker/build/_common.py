import subprocess  # nosec B404 -- subprocess is required to stream docker build output incrementally.
from pathlib import Path
from typing import TextIO

from aicage._execution_cleanup import register_process
from aicage.config.run_config import RunConfig
from aicage.docker.errors import DockerError
from aicage.docker.execution.cli import docker_cli_environment
from aicage.reporting import OperationReporter


def build_context_dir(run_config: RunConfig, dockerfile_path: Path) -> Path:
    agent_metadata = run_config.context.agents[run_config.agent]
    local_definition_dir = agent_metadata.local_definition_dir
    if local_definition_dir.is_relative_to(dockerfile_path.parent):
        return dockerfile_path.parent
    return local_definition_dir.parent.parent


def run_build_command(
    command: list[str],
    log_handle: TextIO,
    reporter: OperationReporter,
) -> int:
    try:
        with subprocess.Popen(  # nosec B603 -- command is an internal Docker CLI argument list without shell usage.
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            env=docker_cli_environment(),
        ) as process:
            register_process(process)
            if process.stdout is None:
                raise RuntimeError("Docker build process did not provide stdout.")
            for line in process.stdout:
                stripped = line.rstrip("\n")
                log_handle.write(line)
                log_handle.flush()
                reporter.on_phase_log("build", stripped)
            return process.wait()
    except FileNotFoundError as exc:
        raise DockerError(
            "Docker CLI not found. Install Docker and ensure it is on PATH."
        ) from exc
