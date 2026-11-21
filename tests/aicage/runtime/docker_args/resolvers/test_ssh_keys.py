import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.config.project_config import AgentConfig, _AgentMounts
from aicage.runtime.docker_args.resolve.resolver_types import MountRequest, ResolvedArgs
from aicage.runtime.docker_args.resolvers import ssh_keys

from ._fixtures import build_context, build_parsed

_MODULE = "aicage.runtime.docker_args.resolvers.ssh_keys"


class SshKeyTests(TestCase):
    def test_resolve_ssh_mount_skips_when_not_needed(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(ssh=True))
        context = build_context(agent_cfg)
        with (
            mock.patch(f"{_MODULE}.is_commit_signing_enabled", return_value=False),
            mock.patch(f"{_MODULE}.uses_ssh_remotes", return_value=False),
        ):
            resolved = ssh_keys.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_ssh_mount_skips_for_non_ssh_format(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(ssh=True))
        context = build_context(agent_cfg)
        with (
            mock.patch(
                f"{_MODULE}.is_commit_signing_enabled",
                return_value=True,
            ),
            mock.patch(
                f"{_MODULE}.resolve_signing_format",
                return_value="gpg",
            ),
            mock.patch(f"{_MODULE}.uses_ssh_remotes", return_value=False),
        ):
            resolved = ssh_keys.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_ssh_mount_respects_pref(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(ssh=False))
        context = build_context(agent_cfg)
        ssh_dir = Path("/test-tmp/ssh")
        with (
            mock.patch(f"{_MODULE}.is_commit_signing_enabled", return_value=True),
            mock.patch(f"{_MODULE}.resolve_signing_format", return_value="ssh"),
            mock.patch(f"{_MODULE}.uses_ssh_remotes", return_value=False),
            mock.patch(f"{_MODULE}.resolve_ssh_dir", return_value=ssh_dir),
        ):
            resolved = ssh_keys.resolve(context, "codex", build_parsed())
        self.assertEqual(ResolvedArgs(), resolved)

    def test_resolve_ssh_mount_uses_preference(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(ssh=True))
        context = build_context(agent_cfg)
        with tempfile.TemporaryDirectory() as tmp_dir:
            ssh_dir = Path(tmp_dir) / "ssh"
            ssh_dir.mkdir()
            with (
                mock.patch(f"{_MODULE}.is_commit_signing_enabled", return_value=True),
                mock.patch(f"{_MODULE}.resolve_signing_format", return_value="ssh"),
                mock.patch(f"{_MODULE}.uses_ssh_remotes", return_value=False),
                mock.patch(f"{_MODULE}.resolve_ssh_dir", return_value=ssh_dir),
            ):
                resolved = ssh_keys.resolve(context, "codex", build_parsed())
        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=ssh_dir)]),
            resolved,
        )

    def test_resolve_ssh_mount_uses_ssh_remotes(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(ssh=True))
        context = build_context(agent_cfg)
        with tempfile.TemporaryDirectory() as tmp_dir:
            ssh_dir = Path(tmp_dir) / "ssh"
            ssh_dir.mkdir()
            with (
                mock.patch(f"{_MODULE}.is_commit_signing_enabled", return_value=False),
                mock.patch(f"{_MODULE}.uses_ssh_remotes", return_value=True),
                mock.patch(f"{_MODULE}.resolve_ssh_dir", return_value=ssh_dir),
            ):
                resolved = ssh_keys.resolve(context, "codex", build_parsed())
        self.assertEqual(
            ResolvedArgs(mounts=[MountRequest(host_path=ssh_dir)]),
            resolved,
        )
