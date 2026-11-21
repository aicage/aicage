from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.runtime._agent_config import AgentConfig, resolve_agent_config
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    _ = parsed
    agent_metadata = context.agents[agent]
    agent_config: AgentConfig = resolve_agent_config(agent_metadata)
    mounts = [
        MountRequest(host_path=host_path)
        for host_path in agent_config.agent_config_host
    ]
    return ResolvedArgs(mounts=mounts)
