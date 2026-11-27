from collections.abc import Callable
from copy import deepcopy

from aicage.config.context import ConfigContext
from aicage.config.run_config import RunConfig
from aicage.config.run_config_draft import RunConfigDraft
from aicage.reporting import OperationReporter
from aicage.runtime._confirm import prompt_update_aicage
from aicage.runtime.menu._interaction_types import ConfigSelectionResult
from aicage.runtime.menu.scope_change import ConfigScopeChange

from ._config_app import ConfigApp
from ._execution_app import ExecutionApp
from ._image_update_app import ImageUpdateApp
from .services.execution_reporting import ExecutionReporter


class TextualInteraction:
    def __init__(self, reporter: ExecutionReporter) -> None:
        self._reporter = reporter

    @property
    def reporter(self) -> OperationReporter:
        return self._reporter

    def configure_run(
        self,
        draft: RunConfigDraft,
        context: ConfigContext,
        agent: str,
    ) -> ConfigSelectionResult | ConfigScopeChange:
        del agent  # Textual reads agent from draft.agent.
        return _edit_draft_with_textual_app(draft, context, self._reporter)

    def confirm_aicage_update(
        self,
        installed_version: str,
        latest_version: str,
    ) -> bool:
        return prompt_update_aicage(installed_version, latest_version)

    def confirm_image_update(self, image_ref: str) -> bool:
        result = ImageUpdateApp(image_ref).run(inline=True)
        if result is None:
            raise KeyboardInterrupt
        return result

    def execute_image_setup(self, run_config: RunConfig, update_approved: bool) -> None:
        result = ExecutionApp(
            run_config,
            update_approved,
            self._reporter,
        ).run(inline=True)
        if isinstance(result, BaseException):
            raise result

    def execute_operation(self, operation: Callable[[OperationReporter], None]) -> None:
        result = ExecutionApp(None, False, self._reporter, operation).run(inline=True)
        if isinstance(result, BaseException):
            raise result


def _edit_draft_with_textual_app(
    draft: RunConfigDraft,
    context: ConfigContext,
    reporter: ExecutionReporter,
) -> ConfigSelectionResult | ConfigScopeChange:
    original_project_cfg = deepcopy(draft.project_cfg)
    original_parsed = deepcopy(draft.parsed)
    draft.prefill_for_overview()
    result = ConfigApp(draft, context, reporter).run(inline=True)
    if result is None:
        draft.project_cfg.path = original_project_cfg.path
        draft.project_cfg.agents = original_project_cfg.agents
        draft.parsed = original_parsed
        raise KeyboardInterrupt
    if isinstance(result, BaseException):
        raise result
    draft.consume_overview_prefill()
    return result
