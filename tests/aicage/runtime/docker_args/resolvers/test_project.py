from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import _ProjectConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import project


class ProjectResolverTests(TestCase):
    def test_resolve_returns_project_mount(self) -> None:
        project_path = Path("/test-tmp/project")
        context = ConfigContext(
            store=mock.Mock(),
            project_cfg=_ProjectConfig(path=str(project_path), agents={}),
            agents={},
            bases={},
            extensions={},
        )

        resolved = project.resolve(context, "codex", _build_parsed())

        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=project_path.resolve())]),
            resolved,
        )


def _build_parsed() -> ParsedArgs:
    return ParsedArgs(False, "", "codex", [], False, [])
