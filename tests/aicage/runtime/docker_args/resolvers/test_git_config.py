import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.config.project_config import AgentConfig
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import git_config

from ._fixtures import build_context, build_parsed


class GitConfigTests(TestCase):
    def test_resolve_git_config_mount_skips_without_config(self) -> None:
        agent_cfg = AgentConfig()
        context = build_context(agent_cfg)
        with mock.patch(
            "aicage.runtime.docker_args.resolvers.git_config.resolve_git_config_path",
            return_value=None,
        ):
            resolved = git_config.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_git_config_mount_respects_pref(self) -> None:
        agent_cfg = AgentConfig()
        agent_cfg.mounts.gitconfig = True
        context = build_context(agent_cfg)
        with tempfile.TemporaryDirectory() as tmp_dir:
            gitconfig = Path(tmp_dir) / ".gitconfig"
            gitconfig.write_text("user.name = tester", encoding="utf-8")
            with mock.patch(
                "aicage.runtime.docker_args.resolvers.git_config.resolve_git_config_path",
                return_value=gitconfig,
            ):
                resolved = git_config.resolve(context, "codex", build_parsed())
        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=gitconfig)]),
            resolved,
        )
