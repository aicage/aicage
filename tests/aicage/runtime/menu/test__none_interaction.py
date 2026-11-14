from unittest import TestCase, mock

from aicage.cli_types import ConfigUpdateArgs, ParsedArgs
from aicage.config.project_config import AgentConfig
from aicage.registry.image_selection.interaction import (
    BaseChoiceRequest,
    ExtensionChoiceOption,
)
from aicage.runtime.menu import _none_interaction

from ._test_support import _build_context, _build_draft


class NoneInteractionTests(TestCase):
    def test_init(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())

        self.assertEqual("_NoneInteraction", resolved.__class__.__name__)


class ConfigureRunTests(TestCase):
    def test_configure_run(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())
        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(
                False,
                "--cli",
                "codex",
                [],
                False,
                ["logs"],
                menu="none",
                extensions=["extra"],
            ),
        )
        selection = mock.Mock()
        selection.base = "ubuntu"

        with (
            mock.patch(
                "aicage.runtime.menu._none_interaction.select_agent_image",
                return_value=selection,
            ) as select_mock,
            mock.patch.object(draft, "apply_selection") as apply_mock,
            mock.patch(
                "aicage.runtime.menu._none_interaction.apply_mount_preferences"
            ) as mount_mock,
            mock.patch.object(draft, "persist_docker_args") as persist_docker_args_mock,
            mock.patch.object(
                draft, "merge_shares", wraps=draft.merge_shares
            ) as merge_shares_mock,
            mock.patch.object(draft, "persist_shares") as persist_shares_mock,
        ):
            result = resolved.configure_run(draft, _build_context(), "codex")

        self.assertIs(selection, result.selection)
        selection_interaction = select_mock.call_args.args[2]
        self.assertEqual(
            ["extra"],
            selection_interaction.choose_extensions([]),
        )
        apply_mock.assert_called_once_with(selection)
        mount_mock.assert_called_once()
        persist_docker_args_mock.assert_not_called()
        merge_shares_mock.assert_called_once_with()
        persist_shares_mock.assert_not_called()

    def test_configure_run_skips_implicit_mounts_for_config_update(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())
        draft = _build_draft(
            AgentConfig(base="ubuntu", extensions=["gh"]),
            ConfigUpdateArgs(
                False,
                "",
                "codex",
                [],
                False,
                [],
                menu="none",
                scope="global",
            ),
        )
        selection = mock.Mock()
        selection.base = "ubuntu"

        with (
            mock.patch(
                "aicage.runtime.menu._none_interaction.select_agent_image",
                return_value=selection,
            ),
            mock.patch.object(draft, "apply_selection"),
            mock.patch(
                "aicage.runtime.menu._none_interaction.apply_mount_preferences"
            ) as mount_mock,
        ):
            resolved.configure_run(draft, _build_context(), "codex")

        mount_mock.assert_not_called()
        self.assertEqual({"gh": True}, draft.agent_cfg.extension_mounts)

    def test_configure_run_applies_git_mount_defaults_for_run(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())
        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(
                False,
                "",
                "codex",
                [],
                False,
                [],
                menu="none",
                git=True,
            ),
        )
        selection = mock.Mock()
        selection.base = "ubuntu"

        with (
            mock.patch(
                "aicage.runtime.menu._none_interaction.select_agent_image",
                return_value=selection,
            ),
            mock.patch.object(draft, "apply_selection"),
            mock.patch(
                "aicage.runtime.menu._none_interaction.apply_git_mount_defaults"
            ) as git_mount_mock,
            mock.patch(
                "aicage.runtime.menu._none_interaction.apply_mount_preferences"
            ) as mount_mock,
        ):
            resolved.configure_run(draft, _build_context(), "codex")

        git_mount_mock.assert_called_once_with(mock.ANY, draft.agent_cfg)
        mount_mock.assert_called_once()

    def test_configure_run_selects_configured_extensions_without_cli_extensions(
        self,
    ) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())
        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(False, "", "codex", [], False, [], menu="none"),
        )
        selection = mock.Mock()
        selection.base = "ubuntu"
        context = _build_context()
        context.project_cfg.agents["codex"] = AgentConfig(
            base="ubuntu", extensions=["gh"]
        )

        with (
            mock.patch(
                "aicage.runtime.menu._none_interaction.select_agent_image",
                return_value=selection,
            ) as select_mock,
            mock.patch.object(draft, "apply_selection"),
            mock.patch(
                "aicage.runtime.menu._none_interaction.apply_mount_preferences"
            ),
        ):
            resolved.configure_run(draft, context, "codex")

        selection_interaction = select_mock.call_args.args[2]
        self.assertEqual(["gh"], selection_interaction.choose_extensions([]))

    def test_configure_run_disables_git_mounts_for_git_off(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())
        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(False, "", "codex", [], False, [], menu="none", git=False),
        )
        selection = mock.Mock()
        selection.base = "ubuntu"

        with (
            mock.patch(
                "aicage.runtime.menu._none_interaction.select_agent_image",
                return_value=selection,
            ),
            mock.patch.object(draft, "apply_selection"),
            mock.patch(
                "aicage.runtime.menu._none_interaction.disable_git_mounts"
            ) as disable_git_mounts_mock,
            mock.patch("aicage.runtime.menu._none_interaction.apply_mount_preferences"),
        ):
            resolved.configure_run(draft, _build_context(), "codex")

        disable_git_mounts_mock.assert_called_once_with(draft.agent_cfg)


class ExecuteImageSetupTests(TestCase):
    def test_execute_image_setup(self) -> None:
        reporter = mock.Mock()
        resolved = _none_interaction._NoneInteraction(reporter)
        run_config = mock.Mock()

        with mock.patch("aicage.runtime.menu._none_interaction.ensure_image") as ensure:
            resolved.execute_image_setup(run_config, update_approved=True)

        ensure.assert_called_once_with(
            run_config,
            update_approved=True,
            reporter=reporter,
        )


class RuntimeUpdateTests(TestCase):
    def test_confirm_aicage_update(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())

        self.assertTrue(resolved.confirm_aicage_update("1.0.0", "1.1.0"))

    def test_confirm_image_update(self) -> None:
        resolved = _none_interaction._NoneInteraction(mock.Mock())

        self.assertTrue(resolved.confirm_image_update("repo:tag"))


class NonInteractiveSelectionInteractionTests(TestCase):
    def test_choose_base(self) -> None:
        resolved = _none_interaction._NonInteractiveSelectionInteraction()

        choice = resolved.choose_base(
            BaseChoiceRequest(
                agent="codex",
                context=_build_context(),
                agent_metadata=mock.Mock(),
                default_base="ubuntu",
            )
        )

        self.assertEqual("ubuntu", choice)

    def test_choose_extensions(self) -> None:
        resolved = _none_interaction._NonInteractiveSelectionInteraction(["gh"])

        choice = resolved.choose_extensions(
            [ExtensionChoiceOption(name="gh", description="GitHub CLI")]
        )

        self.assertEqual(["gh"], choice)

    def test_choose_image_ref(self) -> None:
        resolved = _none_interaction._NonInteractiveSelectionInteraction()

        choice = resolved.choose_image_ref("repo:default")

        self.assertEqual("repo:default", choice)
