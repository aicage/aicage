from pathlib import Path

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    _ = (agent, parsed)
    project_path = Path(context.project_cfg.path).resolve()
    return ResolvedArgs(mounts=[MountRequest(host_path=project_path)])
