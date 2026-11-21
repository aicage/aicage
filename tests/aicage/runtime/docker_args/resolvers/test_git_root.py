from pathlib import Path
from unittest import TestCase, mock

from aicage.config.project_config import AgentConfig, _AgentMounts
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import git_root

from ._fixtures import build_context, build_parsed

_MODULE = "aicage.runtime.docker_args.resolvers.git_root"


class GitRootTests(TestCase):
    def test_resolve_git_root_mount_skips_without_git_root(self) -> None:
        agent_cfg = AgentConfig()
        context = build_context(agent_cfg)
        with (mock.patch(f"{_MODULE}.resolve_git_root", return_value=None),):
            resolved = git_root.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_git_root_mount_skips_for_project_root(self) -> None:
        agent_cfg = AgentConfig()
        context = build_context(agent_cfg)
        with (
            mock.patch(
                f"{_MODULE}.resolve_git_root", return_value=Path("/test-tmp/project")
            ),
        ):
            resolved = git_root.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_git_root_mount_respects_pref(self) -> None:
        root_path = Path("/test-tmp/root")
        agent_cfg = AgentConfig(mounts=_AgentMounts(gitroot=False))
        context = build_context(agent_cfg)
        with mock.patch(
            f"{_MODULE}.resolve_git_root",
            return_value=root_path,
        ):
            resolved = git_root.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_git_root_mount_uses_preference(self) -> None:
        root_path = Path("/test-tmp/root")
        agent_cfg = AgentConfig(mounts=_AgentMounts(gitroot=True))
        context = build_context(agent_cfg)
        with mock.patch(
            f"{_MODULE}.resolve_git_root",
            return_value=root_path,
        ):
            resolved = git_root.resolve(context, "codex", build_parsed())
        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=root_path)]),
            resolved,
        )
