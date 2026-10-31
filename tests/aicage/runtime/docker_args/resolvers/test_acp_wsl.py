from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.runtime.docker_args.resolvers.acp_wsl import resolve
from aicage.runtime.env_vars import _AICAGE_ACP_WSL
from aicage.runtime.run_args import EnvVar


class AcpWslTests(TestCase):
    def test_resolve_enables_acp_wsl(self) -> None:
        resolved = resolve(_context(), "codex", _parsed(acp_wsl=True))

        self.assertEqual(
            [EnvVar(name=_AICAGE_ACP_WSL, value="")],
            resolved.env,
        )

    def test_resolve_skips_acp_wsl_without_cli_option(self) -> None:
        resolved = resolve(_context(), "codex", _parsed())

        self.assertEqual([], resolved.env)


def _context() -> ConfigContext:
    return ConfigContext(
        store=mock.Mock(),
        project_cfg=mock.Mock(),
        agents={},
        bases={},
        extensions={},
    )


def _parsed(acp_wsl: bool = False) -> ParsedArgs:
    return ParsedArgs(False, "", "codex", [], False, [], acp_wsl=acp_wsl)
