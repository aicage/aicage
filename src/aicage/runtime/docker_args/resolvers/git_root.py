from pathlib import Path

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.support.git_support import resolve_git_root


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    _ = parsed
    project_path = Path(context.project_cfg.path)
    agent_cfg: AgentConfig = context.project_cfg.agents[agent]
    git_root = resolve_git_root(project_path)
    if not git_root or git_root == project_path:
        return ResolvedArgs()

    mounts_cfg = agent_cfg.mounts
    if mounts_cfg.gitroot:
        return ResolvedArgs(mounts=[MountRequest(host_path=git_root)])
    return ResolvedArgs()
