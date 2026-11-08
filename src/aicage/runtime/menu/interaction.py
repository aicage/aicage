from collections.abc import Callable
from typing import Protocol

from aicage.cli_types import MenuMode
from aicage.config.context import ConfigContext
from aicage.config.run_config import RunConfig
from aicage.config.run_config_draft import RunConfigDraft
from aicage.reporting import ConsoleOperationReporter, OperationReporter
from aicage.runtime.menu._interaction_types import ConfigSelectionResult
from aicage.runtime.menu._none_interaction import _NoneInteraction
from aicage.runtime.menu.scope_change import ConfigScopeChange
from aicage.runtime.menu.textual.interaction import TextualInteraction
from aicage.runtime.menu.textual.services.execution_reporting import ExecutionReporter


class RuntimeInteraction(Protocol):
    @property
    def reporter(self) -> OperationReporter: ...

    def configure_run(
        self,
        draft: RunConfigDraft,
        context: ConfigContext,
        agent: str,
    ) -> ConfigSelectionResult | ConfigScopeChange: ...

    def confirm_aicage_update(
        self,
        installed_version: str,
        latest_version: str,
    ) -> bool: ...

    def confirm_image_update(self, image_ref: str) -> bool: ...

    def execute_image_setup(
        self, run_config: RunConfig, update_approved: bool
    ) -> None: ...

    def execute_operation(
        self, operation: Callable[[OperationReporter], None]
    ) -> None: ...


def create_runtime_interaction(menu: MenuMode) -> RuntimeInteraction:
    if menu == "none":
        return _NoneInteraction(ConsoleOperationReporter())
    return TextualInteraction(ExecutionReporter())
