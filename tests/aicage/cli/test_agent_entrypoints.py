import sys
from collections.abc import Callable
from unittest import TestCase, mock

from aicage.cli import agent_entrypoints


class AgentEntrypointsTests(TestCase):
    def test_amp_runs_amp_with_original_arguments(self) -> None:
        self._assert_runs_agent(agent_entrypoints.amp, "amp")

    def test_claude_runs_claude_with_original_arguments(self) -> None:
        self._assert_runs_agent(agent_entrypoints.claude, "claude")

    def test_codex_runs_codex_with_original_arguments(self) -> None:
        self._assert_runs_agent(agent_entrypoints.codex, "codex")

    def _assert_runs_agent(self, entrypoint: Callable[[], int], agent: str) -> None:
        with (
            mock.patch.object(sys, "argv", ["aicage-agent", "--acp"]),
            mock.patch(
                "aicage.cli.agent_entrypoints.main", return_value=7
            ) as main_mock,
        ):
            exit_code = entrypoint()

        self.assertEqual(7, exit_code)
        main_mock.assert_called_once_with(["--acp-wsl", agent, "--acp"])
