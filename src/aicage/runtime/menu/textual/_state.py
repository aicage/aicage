from dataclasses import dataclass, field

from ._models import BuiltInShareValue, CustomShareValue


@dataclass
class OverviewState:
    last_section_id: str | None
    built_in_shares: list[BuiltInShareValue]
    custom_shares: list[CustomShareValue]
    docker_socket_enabled: bool
    docker_socket_inherited: bool = False
    git_values: dict[str, bool | None] = field(default_factory=dict)
    credential_values: dict[str, bool | None] = field(default_factory=dict)
