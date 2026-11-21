from collections.abc import Mapping
from pathlib import Path

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import AgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.mounts.shares import ShareSpec, resolve_share_specs


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    cwd = Path.cwd().resolve()
    agent_cfg: AgentConfig = context.project_cfg.agents.setdefault(agent, AgentConfig())
    extension_shares = _approved_extension_shares(agent_cfg, context.extensions)
    share_values = list(agent_cfg.shares)
    if parsed is not None and parsed.shares:
        share_values = list(parsed.shares)
    if not share_values and not extension_shares:
        return ResolvedArgs()
    share_mounts: list[ShareSpec] = resolve_share_specs(
        [*share_values, *extension_shares], cwd
    )
    mounts = [
        MountRequest(host_path=share.host_path, read_only=share.read_only)
        for share in share_mounts
    ]
    return ResolvedArgs(mounts=mounts)


def _approved_extension_shares(
    agent_cfg: AgentConfig,
    available_extensions: Mapping[str, ExtensionMetadata],
) -> list[str]:
    shares: list[str] = []
    for extension_id in agent_cfg.extensions:
        if not agent_cfg.extension_mounts.get(extension_id):
            continue
        extension = available_extensions.get(extension_id)
        if extension is None:
            continue
        shares.extend(extension.shares)
    return shares
