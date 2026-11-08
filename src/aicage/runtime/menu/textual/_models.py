from dataclasses import dataclass
from enum import Enum


class BuiltInShareSource(Enum):
    GIT_SUPPORT = "git_support"
    CREDENTIALS = "credentials"
    EXTENSION = "extension"


@dataclass(frozen=True)
class BuiltInShareValue:
    source: BuiltInShareSource
    key: str
    label: str
    path: str | None
    persisted: bool | None
    enabled: bool
    row_key: str | None = None
    inherited: bool = False


@dataclass(frozen=True)
class SharesValues:
    shares: list[str]
    built_in_shares: list[BuiltInShareValue]


@dataclass(frozen=True)
class CustomShareValue:
    value: str
    inherited: bool = False


@dataclass(frozen=True)
class ShareEditorResult:
    share: str | None
    remove: bool


@dataclass(frozen=True)
class DockerOptionValue:
    key: str
    label: str
    description: str | None
    persisted: bool | None
    enabled: bool
    requires_confirmation: bool = True
    inherited: bool = False


@dataclass(frozen=True)
class HostAccessConfirmValues:
    docker_options: list[DockerOptionValue]
    git_shares: list[BuiltInShareValue]
    credential_shares: list[BuiltInShareValue]
    extension_shares: list[BuiltInShareValue]


@dataclass(frozen=True)
class ExtrasValues:
    docker_args: str
    inherited_docker_args: str = ""
