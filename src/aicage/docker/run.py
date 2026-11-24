import shlex
import subprocess  # nosec B404 -- subprocess is required for Docker CLI execution and result handling.
import sys
from pathlib import Path

from aicage._proxy import proxy_run_env_args_from_host
from aicage.constants import BUILDER_VERSION_CHECK_TIMEOUT_SECONDS
from aicage.docker._env import resolve_user_ids
from aicage.docker.execution import cli as _docker_cli
from aicage.docker.execution.mounts import mount_args
from aicage.docker.query import cleanup_old_digest, get_local_repo_digest_for_repo
from aicage.docker.refs import repository_from_image_ref
from aicage.runtime.run_args import DockerRunArgs


def run_container(args: DockerRunArgs) -> None:
    command = _assemble_docker_run(args)
    repository = repository_from_image_ref(args.image_ref)
    old_digest = get_local_repo_digest_for_repo(args.image_ref, repository)
    try:
        _docker_cli.run_docker_command(command, check=True)
    finally:
        cleanup_old_digest(repository, old_digest, args.image_ref)


def print_run_command(args: DockerRunArgs) -> None:
    command = _assemble_docker_run(args)
    print(shlex.join(command))


def run_builder_version_check(
    image_ref: str, definition_dir: Path
) -> subprocess.CompletedProcess[str]:
    command = [
        "/bin/bash",
        "-c",
        "cp /agent/version.sh /tmp/version.sh "
        "&& sed -i 's/\\r$//' /tmp/version.sh "
        "&& chmod +x /tmp/version.sh "
        "&& /bin/bash /tmp/version.sh",
    ]
    run_command = [
        "docker",
        "run",
        "--rm",
        *proxy_run_env_args_from_host(),
        "-v",
        f"{str(definition_dir.resolve())}:/agent:ro",
        "-w",
        "/agent",
        image_ref,
        *command,
    ]
    try:
        process = subprocess.run(  # nosec B603 -- command is an internal Docker argv list without shell usage.
            run_command,
            check=False,
            capture_output=True,
            text=True,
            timeout=BUILDER_VERSION_CHECK_TIMEOUT_SECONDS,
            env=_docker_cli.docker_cli_environment(),
        )
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(
            command, 124, stdout="", stderr="Version check timed out."
        )
    except Exception as exc:
        return subprocess.CompletedProcess(command, 1, stdout="", stderr=str(exc))


def _assemble_docker_run(args: DockerRunArgs) -> list[str]:
    cmd: list[str] = ["docker", "run", "--rm", "-it" if sys.stdin.isatty() else "-i"]
    cmd.extend(resolve_user_ids())
    for env in args.env:
        cmd.extend(["-e", f"{env.name}={env.value}"])
    cmd.extend(mount_args(args.mounts))

    if args.merged_docker_args:
        cmd.extend(shlex.split(args.merged_docker_args))

    cmd.append(args.image_ref)
    cmd.extend(args.agent_args)
    return cmd
