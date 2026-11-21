from pathlib import Path

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.support.git_support import resolve_gpg_home
from aicage.runtime.docker_args.support.signing import (
    is_commit_signing_enabled,
    resolve_signing_format,
)


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    _ = parsed
    project_path = Path(context.project_cfg.path)
    agent_cfg: AgentConfig = context.project_cfg.agents[agent]
    if not is_commit_signing_enabled(project_path):
        return ResolvedArgs()
    if resolve_signing_format(project_path) == "ssh":
        return ResolvedArgs()

    gpg_home = resolve_gpg_home()
    if not gpg_home or not gpg_home.exists():
        return ResolvedArgs()

    mounts_cfg = agent_cfg.mounts
    if mounts_cfg.gnupg:
        return ResolvedArgs(mounts=[MountRequest(host_path=gpg_home)])
    return ResolvedArgs()
