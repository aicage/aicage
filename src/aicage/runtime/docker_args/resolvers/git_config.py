from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.support.git_support import resolve_git_config_path


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    _ = parsed
    agent_cfg: AgentConfig = context.project_cfg.agents[agent]
    git_config = resolve_git_config_path()
    if not git_config or not git_config.exists():
        return ResolvedArgs()

    mounts_cfg = agent_cfg.mounts
    if mounts_cfg.gitconfig:
        return ResolvedArgs(mounts=[MountRequest(host_path=git_config)])
    return ResolvedArgs()
