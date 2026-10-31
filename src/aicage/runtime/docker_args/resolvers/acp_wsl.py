from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.runtime.docker_args.support.resolver_types import ResolvedArgs
from aicage.runtime.env_vars import _AICAGE_ACP_WSL
from aicage.runtime.run_args import EnvVar


def resolve(
    context: ConfigContext,
    agent: str,
    parsed: ParsedArgs | None,
) -> ResolvedArgs:
    del context, agent
    if parsed is None or not parsed.acp_wsl:
        return ResolvedArgs()
    return ResolvedArgs(env=[EnvVar(name=_AICAGE_ACP_WSL, value="")])
