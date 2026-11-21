from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.project_config import AgentConfig
from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    ExtrasValues,
    SharesValues,
)
from aicage.runtime.menu.textual.services import summary

from ..._test_support import _build_context, _build_draft


class OverviewSummaryTests(TestCase):
    def test_extras_values_reads_mount_preferences(self) -> None:
        draft = _build_draft(
            AgentConfig(base="ubuntu", docker_args="--rm"),
            ParsedArgs(False, "", "codex", [], False, []),
        )

        values = summary.extras_values(draft)

        self.assertEqual("--rm", values.docker_args)

    def test_extensions_summary_returns_none_for_empty_selection(self) -> None:
        summary_text = summary.extensions_summary([])

        self.assertEqual("none", summary_text)

    def test_extensions_summary_returns_count_for_single_selection(self) -> None:
        summary_text = summary.extensions_summary(["gh"])

        self.assertEqual("1 selected", summary_text)

    def test_extensions_summary_returns_count_for_multiple_selections(self) -> None:
        summary_text = summary.extensions_summary(["gh", "missing"])

        self.assertEqual("2 selected", summary_text)

    def test_shares_values_reads_mount_preferences(self) -> None:
        draft = _build_draft(
            AgentConfig(base="ubuntu", shares=["/test-tmp/logs"]),
            ParsedArgs(False, "", "codex", [], False, []),
        )
        built_in_share = BuiltInShareValue(
            BuiltInShareSource.GIT_SUPPORT,
            "gitconfig",
            "Git config",
            "/test-tmp/gitconfig",
            True,
            True,
        )

        with mock.patch(
            "aicage.runtime.menu.textual.services.summary.built_in_share_values",
            return_value=[built_in_share],
        ):
            values = summary.shares_values(draft, _build_context())

        self.assertEqual(["/test-tmp/logs"], values.shares)
        self.assertEqual([built_in_share], values.built_in_shares)

    def test_list_summary_returns_none_for_empty(self) -> None:
        self.assertEqual("none", summary._list_summary([]))

    def test_shares_summary_formats_values(self) -> None:
        summary_text = summary._shares_summary(
            SharesValues(
                ["/test-tmp/logs"],
                [
                    BuiltInShareValue(
                        BuiltInShareSource.GIT_SUPPORT,
                        "gitconfig",
                        "Git config",
                        "/test-tmp/gitconfig",
                        None,
                        True,
                    )
                ],
            )
        )

        self.assertIn("/test-tmp/logs", summary_text)
        self.assertIn("git config", summary_text)

    def test_extras_summary_formats_values(self) -> None:
        summary_text = summary.extras_summary(ExtrasValues("--rm"))

        self.assertEqual("yes", summary_text)
