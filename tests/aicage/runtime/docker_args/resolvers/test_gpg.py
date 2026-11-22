import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.config.project_config import AgentConfig, _AgentMounts
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import gpg

from ._fixtures import build_context, build_parsed


class GpgHomeTests(TestCase):
    def test_resolve_gpg_mount_skips_when_signing_disabled(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(gnupg=True))
        context = build_context(agent_cfg)
        with mock.patch(
            "aicage.runtime.docker_args.resolvers.gpg.is_commit_signing_enabled",
            return_value=False,
        ):
            resolved = gpg.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_gpg_mount_skips_for_ssh_format(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(gnupg=True))
        context = build_context(agent_cfg)
        with (
            mock.patch(
                "aicage.runtime.docker_args.resolvers.gpg.is_commit_signing_enabled",
                return_value=True,
            ),
            mock.patch(
                "aicage.runtime.docker_args.resolvers.gpg.resolve_signing_format",
                return_value="ssh",
            ),
        ):
            resolved = gpg.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_gpg_mount_respects_pref(self) -> None:
        gpg_home = Path("/test-tmp/gpg")
        agent_cfg = AgentConfig(mounts=_AgentMounts(gnupg=False))
        context = build_context(agent_cfg)
        with (
            mock.patch(
                "aicage.runtime.docker_args.resolvers.gpg.is_commit_signing_enabled",
                return_value=True,
            ),
            mock.patch(
                "aicage.runtime.docker_args.resolvers.gpg.resolve_signing_format",
                return_value="gpg",
            ),
            mock.patch(
                "aicage.runtime.docker_args.resolvers.gpg.resolve_gpg_home",
                return_value=gpg_home,
            ),
        ):
            resolved = gpg.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_gpg_mount_uses_preference(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(gnupg=True))
        context = build_context(agent_cfg)
        with tempfile.TemporaryDirectory() as tmp_dir:
            gpg_home = Path(tmp_dir) / "gnupg"
            gpg_home.mkdir()
            with (
                mock.patch(
                    "aicage.runtime.docker_args.resolvers.gpg.is_commit_signing_enabled",
                    return_value=True,
                ),
                mock.patch(
                    "aicage.runtime.docker_args.resolvers.gpg.resolve_signing_format",
                    return_value="gpg",
                ),
                mock.patch(
                    "aicage.runtime.docker_args.resolvers.gpg.resolve_gpg_home",
                    return_value=gpg_home,
                ),
            ):
                resolved = gpg.resolve(context, "codex", build_parsed())
        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=gpg_home)]),
            resolved,
        )
