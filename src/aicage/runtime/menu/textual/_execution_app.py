from collections.abc import Callable

from textual import work
from textual.app import ComposeResult

from aicage._execution_cleanup import (
    cancel_current_execution_cleanup,
    current_execution_cleanup,
)
from aicage.config.run_config import RunConfig
from aicage.registry.ensure_image import ensure_image
from aicage.reporting import OperationReporter

from ._textual_app import TextualApp
from .services.execution_reporting import ExecutionReporter
from .views.execution_screen import ExecutionScreen


class ExecutionApp(TextualApp[BaseException | None]):
    def __init__(
        self,
        run_config: RunConfig | None,
        update_approved: bool,
        reporter: ExecutionReporter,
        operation: Callable[[OperationReporter], None] | None = None,
    ) -> None:
        super().__init__("container setup")
        self._run_config = run_config
        self._update_approved = update_approved
        self._reporter = reporter
        self._operation = operation

    def compose(self) -> ComposeResult:
        yield ExecutionScreen()

    def on_mount(self) -> None:
        self._run_execution()

    def action_cancel(self) -> None:
        self.query_one(ExecutionScreen).mark_cancelled()
        cancel_current_execution_cleanup()
        self.exit(KeyboardInterrupt())

    @work(thread=True, exclusive=True)
    def _run_execution(self) -> None:
        screen = self.query_one(ExecutionScreen)
        self._reporter.attach_screen(screen)
        error: BaseException | None = None
        try:
            with current_execution_cleanup():
                if self._operation is not None:
                    self._operation(self._reporter)
                else:
                    if self._run_config is None:
                        raise RuntimeError("Image setup requires a run configuration.")
                    ensure_image(
                        self._run_config,
                        update_approved=self._update_approved,
                        reporter=self._reporter,
                    )
        except BaseException as exc:
            error = exc
        self.call_from_thread(self.exit, error)
