from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.project_config import AgentConfig
from aicage.registry.image_selection.models import ImageSelection
from aicage.runtime.menu._interaction_types import ConfigSelectionResult
from aicage.runtime.menu.textual import interaction
from aicage.runtime.menu.textual.services.execution_reporting import ExecutionReporter

from .._test_support import _build_context, _build_draft


class ConfigureRunTests(TestCase):
    def test_configure_run(self) -> None:
        resolved = interaction.TextualInteraction(ExecutionReporter())
        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(False, "", "codex", [], False, [], menu="ui"),
        )
        selection = mock.Mock()
        selection.base = "ubuntu"

        with mock.patch(
            "aicage.runtime.menu.textual.interaction._edit_draft_with_textual_app",
            return_value=ConfigSelectionResult(
                selection=selection,
                project_docker_args="--project",
            ),
        ) as edit_mock:
            result = resolved.configure_run(draft, _build_context(), "codex")

        edit_mock.assert_called_once_with(draft, mock.ANY, resolved._reporter)
        self.assertIsInstance(result, ConfigSelectionResult)
        assert isinstance(result, ConfigSelectionResult)
        self.assertIs(selection, result.selection)
        self.assertEqual("--project", result.project_docker_args)


class ExecuteImageSetupTests(TestCase):
    def test_execute_image_setup(self) -> None:
        reporter = ExecutionReporter()
        resolved = interaction.TextualInteraction(reporter)
        run_config = mock.Mock()

        with mock.patch(
            "aicage.runtime.menu.textual.interaction.ExecutionApp.run",
            return_value=None,
        ) as run_mock:
            resolved.execute_image_setup(run_config, update_approved=True)

        run_mock.assert_called_once_with(inline=True)


class ExecuteOperationTests(TestCase):
    def test_execute_operation(self) -> None:
        reporter = ExecutionReporter()
        resolved = interaction.TextualInteraction(reporter)
        operation = mock.Mock()

        with mock.patch(
            "aicage.runtime.menu.textual.interaction.ExecutionApp.run",
            return_value=None,
        ) as run_mock:
            resolved.execute_operation(operation)

        run_mock.assert_called_once_with(inline=True)


class TextualInteractionTests(TestCase):
    def test_reporter(self) -> None:
        reporter = ExecutionReporter()

        resolved = interaction.TextualInteraction(reporter)

        self.assertIs(reporter, resolved.reporter)

    def test_confirm_image_update(self) -> None:
        with mock.patch(
            "aicage.runtime.menu.textual.interaction.ImageUpdateApp.run",
            return_value=True,
        ) as confirm_mock:
            confirmed = interaction.TextualInteraction(
                ExecutionReporter()
            ).confirm_image_update("repo:tag")

        self.assertTrue(confirmed)
        confirm_mock.assert_called_once_with(inline=True)

    def test_confirm_aicage_update(self) -> None:
        with mock.patch(
            "aicage.runtime.menu.textual.interaction.prompt_update_aicage",
            return_value=False,
        ) as confirm_mock:
            confirmed = interaction.TextualInteraction(
                ExecutionReporter()
            ).confirm_aicage_update("1.0.0", "1.1.0")

        self.assertFalse(confirmed)
        confirm_mock.assert_called_once_with("1.0.0", "1.1.0")


class EditDraftWithTextualAppTests(TestCase):
    def test__edit_draft_with_textual_app_prefills_and_consumes_cli_values(
        self,
    ) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu"),
            parsed=ParsedArgs(
                dry_run=False,
                docker_args="--new",
                agent="codex",
                agent_args=[],
                docker_socket=True,
                shares=["logs"],
            ),
            project_path=Path.cwd(),
        )
        context = _build_context()
        app_result = ConfigSelectionResult(
            selection=ImageSelection(
                image_ref="repo:ubuntu",
                base="ubuntu",
                extensions=[],
                agent_image_ref="repo:ubuntu",
            ),
            project_docker_args="--new",
        )

        with mock.patch(
            "aicage.runtime.menu.textual.interaction.ConfigApp.run",
            return_value=app_result,
        ):
            result = interaction._edit_draft_with_textual_app(
                draft,
                context,
                ExecutionReporter(),
            )

        parsed = draft.parsed
        if parsed is None:
            self.fail("Expected parsed args to be available.")
        self.assertIsInstance(result, ConfigSelectionResult)
        assert isinstance(result, ConfigSelectionResult)
        self.assertEqual("repo:ubuntu", result.selection.image_ref)
        self.assertEqual("--new", result.project_docker_args)
        self.assertEqual("--new", draft.agent_cfg.docker_args)
        self.assertEqual([str((Path.cwd() / "logs").resolve())], draft.agent_cfg.shares)
        self.assertTrue(draft.agent_cfg.mounts.docker)
        self.assertEqual("", parsed.docker_args)
        self.assertEqual([], parsed.shares)
        self.assertFalse(parsed.docker_socket)

    def test__edit_draft_with_textual_app_reraises_app_error(self) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu"),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )
        app_mock = mock.Mock()
        app_mock.run.return_value = RuntimeError("boom")

        with (
            mock.patch(
                "aicage.runtime.menu.textual.interaction.ConfigApp.run",
                return_value=app_mock.run.return_value,
            ),
            self.assertRaises(RuntimeError),
        ):
            interaction._edit_draft_with_textual_app(
                draft, _build_context(), ExecutionReporter()
            )

    def test__edit_draft_with_textual_app_raises_keyboard_interrupt_on_cancel(
        self,
    ) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(
                base="ubuntu", docker_args="--existing", shares=["/repo/existing"]
            ),
            parsed=ParsedArgs(False, "--new", "codex", [], True, ["logs"]),
            project_path=Path.cwd(),
        )
        app_mock = mock.Mock()
        app_mock.run.return_value = None

        with (
            mock.patch(
                "aicage.runtime.menu.textual.interaction.ConfigApp.run",
                return_value=None,
            ),
            self.assertRaises(KeyboardInterrupt),
        ):
            interaction._edit_draft_with_textual_app(
                draft, _build_context(), ExecutionReporter()
            )

    def test_confirm_image_update_raises_keyboard_interrupt_for_none(
        self,
    ) -> None:
        with (
            mock.patch(
                "aicage.runtime.menu.textual.interaction.ImageUpdateApp.run",
                return_value=None,
            ),
            self.assertRaises(KeyboardInterrupt),
        ):
            interaction.TextualInteraction(ExecutionReporter()).confirm_image_update(
                "repo:tag"
            )

    def test_execute_image_setup_raises_app_error(self) -> None:
        run_config = mock.Mock()

        with (
            mock.patch(
                "aicage.runtime.menu.textual.interaction.ExecutionApp.run",
                return_value=RuntimeError("boom"),
            ),
            self.assertRaises(RuntimeError),
        ):
            interaction.TextualInteraction(ExecutionReporter()).execute_image_setup(
                run_config,
                update_approved=True,
            )
