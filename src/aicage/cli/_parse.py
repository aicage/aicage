import argparse
import sys
from collections.abc import Sequence
from typing import Literal

from aicage import __version__
from aicage._logging import get_logger
from aicage.cli._errors import CliError
from aicage.cli_types import (
    CliArgs,
    ConfigInfoArgs,
    ConfigRemoveArgs,
    ConfigScope,
    ConfigUpdateArgs,
    ParsedArgs,
)
from aicage.config.agent.loader import load_agents
from aicage.config.base.loader import load_bases
from aicage.config.errors import ConfigError

_MAX_CONFIG_TOKENS = 3
_DRY_RUN_OPTION = "--dry-run"
_MENU_OPTION = "--menu"
_DOCKER_OPTION = "--docker"
_ACP_WSL_OPTION = "--acp-wsl"
_BASE_OPTION = "--base"
_SHARE_OPTION = "--share"
_EXTENSION_OPTION = "--extension"
_GIT_OPTION = "--git"
_CONFIG_OPTION = "--config"
_HELP_SHORT_OPTION = "-h"
_HELP_OPTION = "--help"
_VERSION_SHORT_OPTION = "-v"
_VERSION_OPTION = "--version"
_OPTIONS_WITH_VALUES: set[str] = {
    _MENU_OPTION,
    _BASE_OPTION,
    _SHARE_OPTION,
    _EXTENSION_OPTION,
    _GIT_OPTION,
}
_ConfigAction = Literal["info", "remove", "global", "tree"]

_CONFIG_ACTION_ALIASES: dict[str, _ConfigAction] = {
    "print": "info",
}


def parse_cli(argv: Sequence[str]) -> CliArgs:
    """
    Returns parsed CLI args.
    Docker args are captured as an opaque string; precedence is resolved later.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument(
        _DRY_RUN_OPTION,
        action="store_true",
        help="Print docker run command without executing.",
    )
    parser.add_argument(
        _MENU_OPTION,
        choices=["ui", "none"],
        default="ui",
        help="Select menu mode: ui or none.",
    )
    parser.add_argument(
        _DOCKER_OPTION,
        action="store_true",
        help="Mount the host Docker socket into the container.",
    )
    parser.add_argument(
        _ACP_WSL_OPTION,
        action="store_true",
        help="Translate ACP paths between Windows and WSL.",
    )
    parser.add_argument(
        _BASE_OPTION,
        help="Select the agent base image.",
    )
    parser.add_argument(
        _SHARE_OPTION,
        action="append",
        default=[],
        help="Mount a host directory into the container (repeatable).",
    )
    parser.add_argument(
        _EXTENSION_OPTION,
        action="append",
        default=[],
        help="Select an extension (repeatable).",
    )
    parser.add_argument(
        _GIT_OPTION,
        choices=["on", "off"],
        help="Enable or disable Git support mounts.",
    )
    parser.add_argument(
        _CONFIG_OPTION,
        nargs="*",
        help="Perform config actions such as the default info or 'remove [agent]'.",
    )
    parser.add_argument(
        _HELP_SHORT_OPTION,
        _HELP_OPTION,
        action="store_true",
        help="Show help message and exit.",
    )
    pre_argv, post_argv = _split_argv(argv)
    pre_argv = _normalize_git_option(pre_argv)

    opts: argparse.Namespace
    remaining: list[str]
    if (
        len(pre_argv) == 1
        and pre_argv[0] in (_VERSION_SHORT_OPTION, _VERSION_OPTION)
        and post_argv is None
    ):
        print(__version__)
        get_logger().info("Displayed CLI version.")
        sys.exit(0)

    option_argv, agent_argv = _split_before_agent_args(pre_argv, post_argv)
    opts, remaining = parser.parse_known_args(option_argv)
    opts.git = _git_value(opts.git)
    remaining.extend(agent_argv)
    if (
        opts.config is None
        and not sys.stdin.isatty()
        and _MENU_OPTION not in option_argv
    ):
        opts.menu = "none"

    if opts.help:
        usage: str = (
            "Usage:\n"
            "  aicage <agent>\n"
            "  aicage [--menu <mode>] [--dry-run] [--docker] [--acp-wsl] [--base <id>] [--git [on|off]] "
            "[--share <path>]... [--extension <id>]... <agent> [<agent-args>]\n"
            "  aicage [--menu <mode>] [--dry-run] [--docker] [--acp-wsl] [--base <id>] [--git [on|off]] "
            "[--share <path>]... [--extension <id>]... <docker-args> -- <agent>"
            " [<agent-args>]\n"
            "  aicage --config\n"
            "  aicage --config info\n"
            "  aicage --config info <global|tree>\n"
            "  aicage --config remove <agent>\n"
            "  aicage --config remove <global|tree> <agent>\n"
            "  aicage --config global <agent>\n"
            "  aicage --config tree <agent>\n"
            "  aicage [<docker-args>] --config <global|tree> -- <agent>\n"
            "  aicage --version\n\n"
            "Arguments:\n"
            "  --dry-run        Print the generated docker run command and exit.\n"
            "  --menu <mode>    Choose menu mode: ui or none.\n"
            "  --docker         Mount /run/docker.sock into the container.\n"
            "  --acp-wsl        Translate ACP paths between Windows and WSL.\n"
            "  --base <id>      Select the agent base image.\n"
            "  --git [on|off]   Enable or disable Git support mounts (default: on).\n"
            "  --share <path>   Mount a host path into the container. Repeatable.\n"
            "  --extension <id> Select an extension. Repeatable.\n"
            "  --config [<command>] Inspect or change saved configuration; see usage above.\n"
            "  -v, --version    Print aicage version and exit.\n"
            "  -h, --help       Show this help and exit.\n\n"
            "Behavior:\n"
            "  - '--menu ui' uses the default config overview.\n"
            "  - '--menu none' skips menus and uses defaults.\n"
            "  - The default menu is 'ui' with a TTY and 'none' without one.\n"
            "  - Docker TTY allocation is enabled only when stdin is a TTY.\n"
            "  - aicage options are parsed only before <agent>.\n"
            "  - <docker-args> are forwarded verbatim to docker run.\n"
            "  - If docker args are present, use '--' before <agent>.\n"
            "  - <agent-args> are forwarded verbatim to the agent.\n"
        )
        print(usage)
        get_logger().info("Displayed CLI usage help.")
        sys.exit(0)

    if opts.config is not None:
        config_tokens: list[str] = opts.config
        return _parse_config_command(config_tokens, opts, remaining, post_argv)

    docker_args, agent, agent_args = _parse_agent_section(remaining, post_argv)

    if not agent:
        raise CliError("Agent name is required.")

    return ParsedArgs(
        opts.dry_run,
        docker_args,
        agent,
        agent_args,
        opts.docker,
        opts.share,
        opts.menu,
        extensions=opts.extension,
        git=opts.git,
        base=opts.base,
        acp_wsl=opts.acp_wsl,
    )


def _split_argv(argv: Sequence[str]) -> tuple[list[str], list[str] | None]:
    if "--" not in argv:
        return list(argv), None
    sep_index = argv.index("--")
    pre_argv = list(argv[:sep_index])
    post_argv = list(argv[sep_index + 1 :])
    return pre_argv, post_argv


def _normalize_git_option(argv: list[str]) -> list[str]:
    normalized: list[str] = []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token != _GIT_OPTION:
            normalized.append(token)
            index += 1
            continue
        if index + 1 < len(argv) and argv[index + 1] in {"on", "off"}:
            normalized.extend((token, argv[index + 1]))
            index += 2
            continue
        normalized.append(f"{_GIT_OPTION}=on")
        index += 1
    return normalized


def _git_value(value: str | None) -> bool | None:
    if value is None:
        return None
    return value == "on"


def _split_before_agent_args(
    argv: list[str],
    post_argv: list[str] | None,
) -> tuple[list[str], list[str]]:
    if post_argv is not None:
        return argv, []
    index = 0
    while index < len(argv):
        token = argv[index]
        if token == _CONFIG_OPTION:
            return argv, []
        if token in _OPTIONS_WITH_VALUES:
            index += 2
            continue
        if _is_agent_token(token):
            return argv[:index], argv[index:]
        index += 1
    return argv, []


def _is_agent_token(token: str) -> bool:
    return not token.startswith("-") and "=" not in token


def _normalize_config_action(action: str) -> _ConfigAction:
    match _CONFIG_ACTION_ALIASES.get(action, action):
        case "info" | "remove" | "global" | "tree" as normalized:
            return normalized
        case _:
            raise CliError(f"Unknown config action: {action}")


def _parse_config_command(
    config_tokens: list[str],
    opts: argparse.Namespace,
    remaining: list[str],
    post_argv: list[str] | None,
) -> CliArgs:
    if not config_tokens:
        config_tokens = ["info"]
    if len(config_tokens) > _MAX_CONFIG_TOKENS:
        raise CliError("Too many values for --config.")
    raw_action = config_tokens[0]
    config_action = _normalize_config_action(raw_action)
    if _is_config_update(config_action, config_tokens, post_argv):
        if opts.dry_run:
            raise CliError("--dry-run cannot be used when updating configuration.")
        if opts.acp_wsl:
            raise CliError("--acp-wsl cannot be used when updating configuration.")
        if post_argv is None or len(post_argv) != 1:
            raise CliError(
                "Configuration updates require exactly one agent after '--'."
            )
        scope = _config_scope(config_action)
        if scope is None:
            raise CliError("Configuration updates require a global or tree scope.")
        return ConfigUpdateArgs(
            opts.dry_run,
            " ".join(remaining).strip(),
            post_argv[0],
            [],
            opts.docker,
            opts.share,
            opts.menu,
            extensions=opts.extension,
            git=opts.git,
            base=opts.base,
            scope=scope,
        )
    if (
        remaining
        or post_argv
        or opts.docker
        or opts.acp_wsl
        or opts.base is not None
        or opts.dry_run
        or opts.share
        or opts.extension
        or opts.git is not None
        or opts.menu != "ui"
    ):
        raise CliError("No additional arguments are allowed with --config.")
    if config_action == "remove":
        remove_agent, remove_scope = _remove_config_target(config_tokens[1:])
        return ConfigRemoveArgs(remove_agent, remove_scope)
    config_agent, config_scope = _config_target(config_action, config_tokens)
    if config_action == "info":
        return ConfigInfoArgs(config_scope)
    if config_agent is None:
        raise CliError(f"An agent is required with '--config {config_action}'.")
    return ConfigUpdateArgs(
        opts.dry_run,
        "",
        config_agent,
        [],
        opts.docker,
        opts.share,
        opts.menu,
        extensions=opts.extension,
        git=opts.git,
        base=opts.base,
        scope=config_action,
    )


def _is_config_update(
    config_action: _ConfigAction,
    config_tokens: list[str],
    post_argv: list[str] | None,
) -> bool:
    return (
        config_action in {"global", "tree"}
        and len(config_tokens) == 1
        and post_argv is not None
    )


def _config_target(
    config_action: _ConfigAction,
    config_tokens: list[str],
) -> tuple[str | None, ConfigScope | None]:
    values = config_tokens[1:]
    if config_action in {"global", "tree"}:
        if len(values) != 1:
            raise CliError(f"An agent is required with '--config {config_action}'.")
        return values[0], None
    if config_action == "info":
        return _info_config_target(values)
    return _remove_config_target(values)


def _info_config_target(values: list[str]) -> tuple[None, ConfigScope | None]:
    if not values:
        return None, None
    scope = _config_scope(values[0]) if len(values) == 1 else None
    if scope is not None:
        return None, scope
    raise CliError("Use '--config info [global|tree]'.")


def _remove_config_target(values: list[str]) -> tuple[str, ConfigScope | None]:
    usage = "Use '--config remove <agent>' or '--config remove <global|tree> <agent>'."
    if not values:
        raise CliError(usage)
    scope = _config_scope(values[0])
    if scope is None:
        if len(values) == 1:
            return values[0], None
        raise CliError(usage)
    if len(values) == _MAX_CONFIG_TOKENS - 1:
        return values[1], scope
    raise CliError(usage)


def _config_scope(value: str) -> ConfigScope | None:
    if value == "global":
        return "global"
    if value == "tree":
        return "tree"
    return None


def _parse_agent_section(
    remaining: list[str],
    post_argv: list[str] | None,
) -> tuple[str, str, list[str]]:
    if post_argv is not None:
        if not post_argv:
            raise CliError("Missing agent after '--'.")
        docker_args = " ".join(remaining).strip()
        return docker_args, post_argv[0], post_argv[1:]
    if not remaining:
        raise CliError(_missing_agent_message())
    first: str = remaining[0]
    if first.startswith("-") or "=" in first:
        raise CliError("Docker args require '--' before the agent.")
    return "", first, remaining[1:]


def _missing_agent_message() -> str:
    message = "Missing argument. Provide an agent name."
    available_agents = _available_agents()
    if not available_agents:
        return message
    agent_list = ", ".join(available_agents)
    return f"{message} Available agents: {agent_list}."


def _available_agents() -> list[str]:
    try:
        return sorted(load_agents(load_bases()))
    except ConfigError:
        return []
