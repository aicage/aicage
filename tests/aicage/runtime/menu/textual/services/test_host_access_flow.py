from unittest import IsolatedAsyncioTestCase

from aicage.cli_types import ParsedArgs
from aicage.config.project_config import AgentConfig
from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
    DockerOptionValue,
)
from aicage.runtime.menu.textual.services import host_access_flow

from ..._test_support import _build_draft


class HostAccessFlowTests(IsolatedAsyncioTestCase):
    async def test_confirm_and_apply_host_access_applies_without_prompt_when_already_persisted(
        self,
    ) -> None:
        draft = _build_draft(
            AgentConfig(), ParsedArgs(False, "", "codex", [], False, [])
        )
        built_in_shares = [
            BuiltInShareValue(
                BuiltInShareSource.GIT_SUPPORT,
                "ssh",
                "SSH",
                "/test-tmp/.ssh",
                True,
                True,
            ),
        ]
        docker_options = [
            DockerOptionValue("docker", "Docker socket", None, True, True)
        ]

        async def confirm_host_access(_values: object) -> None:
            raise AssertionError("confirmation should not be requested")

        accepted, current = await host_access_flow.confirm_and_apply_host_access(
            draft,
            built_in_shares,
            [CustomShareValue("/test-tmp/logs")],
            docker_options,
            confirm_host_access,
        )

        self.assertTrue(accepted)
        self.assertEqual(built_in_shares, current)
        self.assertEqual(["/test-tmp/logs"], draft.agent_cfg.shares)
