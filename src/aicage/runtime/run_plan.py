from collections.abc import Iterator
from contextlib import contextmanager

from aicage._proxy import proxy_env_vars_from_host
from aicage.cli_types import ParsedArgs
from aicage.config.run_config import RunConfig
from aicage.runtime._host_timezone import resolve_host_timezone
from aicage.runtime.credential_agent.forwarding import (
    CredentialSetup,
    credential_forwarding,
)
from aicage.runtime.run_args import DockerRunArgs, EnvVar, _merge_docker_args


def _build_run_args(config: RunConfig, parsed: ParsedArgs) -> DockerRunArgs:
    merged_docker_args: str = _merge_docker_args(
        config.project_docker_args,
        parsed.docker_args,
    )
    return DockerRunArgs(
        image_ref=config.selection.image_ref,
        merged_docker_args=merged_docker_args,
        agent_args=parsed.agent_args,
        env=[*config.env, *_host_timezone_env(config.env), *proxy_env_vars_from_host()],
        mounts=list(config.mounts),
    )


@contextmanager
def prepare_run_args(
    config: RunConfig, parsed: ParsedArgs, credentials: CredentialSetup
) -> Iterator[DockerRunArgs]:
    run_args = _build_run_args(config, parsed)
    with credential_forwarding(credentials) as (
        mounts,
        env,
    ):
        run_args.mounts.extend(mounts)
        run_args.env.extend(env)
        yield run_args


def _host_timezone_env(existing_env: list[EnvVar]) -> list[EnvVar]:
    if any(env.name == "TZ" for env in existing_env):
        return []

    timezone = resolve_host_timezone()
    if not timezone:
        return []

    return [EnvVar(name="TZ", value=timezone)]
