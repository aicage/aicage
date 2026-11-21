from pathlib import Path

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.support.git_support import (
    resolve_ssh_dir,
    uses_ssh_remotes,
)
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
    signing_enabled = is_commit_signing_enabled(project_path)
    signing_format = resolve_signing_format(project_path) if signing_enabled else None
    ssh_needed = (signing_enabled and signing_format == "ssh") or uses_ssh_remotes(
        project_path
    )
    if not ssh_needed:
        return ResolvedArgs()

    ssh_dir = resolve_ssh_dir()
    if not ssh_dir.exists():
        return ResolvedArgs()

    mounts_cfg = agent_cfg.mounts
    if mounts_cfg.ssh:
        return ResolvedArgs(mounts=[MountRequest(host_path=ssh_dir)])
    return ResolvedArgs()
