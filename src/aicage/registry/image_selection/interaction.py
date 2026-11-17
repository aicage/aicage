from dataclasses import dataclass
from typing import Protocol

from aicage.config.agent.models import AgentMetadata
from aicage.config.context import ConfigContext


@dataclass(frozen=True)
class BaseChoiceRequest:
    agent: str
    context: ConfigContext
    agent_metadata: AgentMetadata
    default_base: str


@dataclass(frozen=True)
class ExtensionChoiceOption:
    name: str
    description: str
    has_dockerfile: bool = False


class _SelectionInteraction(Protocol):
    def choose_base(self, request: BaseChoiceRequest) -> str: ...

    def choose_extensions(
        self,
        options: list[ExtensionChoiceOption],
    ) -> list[str]: ...
