from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.agent.models import AgentMetadata
from aicage.config.context import ConfigContext
from aicage.config.project_config import _ProjectConfig
from aicage.runtime._agent_config import AgentConfig as RuntimeAgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import agent_config


class AgentConfigResolverTests(TestCase):
    def test_resolve_maps_agent_config_paths(self) -> None:
        host_paths = [
            Path("/test-tmp/agent/.codex"),
            Path("/test-tmp/agent/.config/codex"),
        ]
        runtime_agent_config = RuntimeAgentConfig(
            agent_path_files=[],
            agent_path_directories=["~/.codex", "~/.config/codex"],
            agent_config_host=host_paths,
        )
        agent_metadata = AgentMetadata(
            agent_path_files=[],
            agent_path_directories=["~/.codex", "~/.config/codex"],
            agent_full_name="Codex CLI",
            agent_homepage="https://example.com",
            build_local=False,
            valid_bases={"ubuntu": "ghcr.io/aicage/aicage:codex-ubuntu"},
            local_definition_dir=Path("/test-tmp/agent"),
        )
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=_ProjectConfig(path="/test-tmp/project", agents={}),
            agents={"codex": agent_metadata},
            bases={},
            extensions={},
        )

        with mock.patch(
            "aicage.runtime.docker_args.resolvers.agent_config.resolve_agent_config",
            return_value=runtime_agent_config,
        ):
            resolved = agent_config.resolve(context, "codex", _build_parsed())

        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=path) for path in host_paths]),
            resolved,
        )


def _build_parsed() -> ParsedArgs:
    return ParsedArgs(False, "", "codex", [], False, [])
