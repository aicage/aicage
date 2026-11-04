from dataclasses import dataclass, field
from typing import Literal

MenuMode = Literal["ui", "none"]
ConfigScope = Literal["global", "tree"]


@dataclass
class ParsedArgs:
    dry_run: bool
    docker_args: str
    agent: str
    agent_args: list[str]
    docker_socket: bool
    shares: list[str]
    menu: MenuMode = "ui"
    extensions: list[str] = field(default_factory=list)
    git: bool | None = None
    base: str | None = None
    acp_wsl: bool = False


@dataclass
class ConfigInfoArgs:
    scope: ConfigScope | None


@dataclass
class ConfigRemoveArgs:
    agent: str
    scope: ConfigScope | None


@dataclass
class ConfigUpdateArgs(ParsedArgs):
    scope: ConfigScope = field(kw_only=True)


CliArgs = ParsedArgs | ConfigInfoArgs | ConfigRemoveArgs
