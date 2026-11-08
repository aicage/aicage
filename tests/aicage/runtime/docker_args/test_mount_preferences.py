from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.context import ConfigContext
from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GNUPG_KEY,
    AgentConfig,
    _AgentMounts,
    _ProjectConfig,
)
from aicage.runtime.docker_args.mount_preferences import (
    apply_cli_credential_mount_preferences,
    apply_credential_mount_defaults,
    apply_extension_mount_defaults,
    apply_git_mount_defaults,
    apply_mount_preferences,
    disable_git_mounts,
)

_MODULE = "aicage.runtime.docker_args.mount_preferences"


class MountPreferencesTests(TestCase):
    def test_apply_mount_preferences_persists_git_mount_choices(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts())
        context = _build_context(agent_cfg)

        with mock.patch(
            f"{_MODULE}.resolve_mount_prompt_prefs",
            return_value=mock.Mock(
                git_mounts={MOUNT_GITCONFIG_KEY},
                credential_mounts={MOUNT_GNUPG_KEY},
                extension_mounts={"marker": True},
            ),
        ):
            apply_mount_preferences(
                context,
                "codex",
                _build_parsed(),
                mock.Mock(),
                mock.Mock(),
            )

        self.assertTrue(agent_cfg.mounts.gitconfig)
        self.assertFalse(agent_cfg.mounts.gitroot)
        self.assertTrue(agent_cfg.mounts.gnupg)
        self.assertFalse(agent_cfg.mounts.ssh)
        self.assertEqual({"marker": True}, agent_cfg.extension_mounts)

    def test_apply_mount_preferences_persists_docker_socket_preference(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts())
        context = _build_context(agent_cfg)

        confirm_persist = mock.Mock(return_value=True)

        with mock.patch(f"{_MODULE}.resolve_mount_prompt_prefs", return_value=None):
            apply_mount_preferences(
                context,
                "codex",
                _build_parsed(docker_socket=True),
                mock.Mock(),
                confirm_persist,
            )

        self.assertTrue(agent_cfg.mounts.docker)

    def test_apply_mount_preferences_skips_docker_prompt_when_already_decided(
        self,
    ) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(docker=False))
        context = _build_context(agent_cfg)

        confirm_persist = mock.Mock()

        with mock.patch(f"{_MODULE}.resolve_mount_prompt_prefs", return_value=None):
            apply_mount_preferences(
                context,
                "codex",
                _build_parsed(docker_socket=True),
                mock.Mock(),
                confirm_persist,
            )

        confirm_persist.assert_not_called()

    def test_apply_extension_mount_defaults_persists_extension_defaults(self) -> None:
        agent_cfg = AgentConfig(extensions=["gh"])
        context = _build_context(agent_cfg)

        with mock.patch(
            f"{_MODULE}.extension_mount_defaults", return_value={"gh": True}
        ):
            apply_extension_mount_defaults(context, agent_cfg)

        self.assertEqual({"gh": True}, agent_cfg.extension_mounts)

    def test_apply_git_mount_defaults_persists_detected_mounts(self) -> None:
        agent_cfg = AgentConfig()
        context = _build_context(agent_cfg)

        with mock.patch(
            f"{_MODULE}.git_mount_defaults", return_value={MOUNT_GITCONFIG_KEY}
        ) as defaults_mock:
            apply_git_mount_defaults(context, agent_cfg)

        self.assertTrue(agent_cfg.mounts.gitconfig)
        self.assertIsNone(agent_cfg.mounts.ssh)
        defaults_mock.assert_called_once_with(
            mock.ANY, agent_cfg.mounts, override_existing=True
        )

    def test_apply_git_mount_defaults_overrides_a_saved_disabled_mount(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(gitconfig=False, gitroot=False))
        context = _build_context(agent_cfg)

        with mock.patch(
            f"{_MODULE}.git_mount_defaults",
            return_value={MOUNT_GITCONFIG_KEY, "gitroot"},
        ):
            apply_git_mount_defaults(context, agent_cfg)

        self.assertTrue(agent_cfg.mounts.gitconfig)
        self.assertTrue(agent_cfg.mounts.gitroot)

    def test_apply_credential_mount_defaults_enables_ssh_independently(self) -> None:
        agent_cfg = AgentConfig()

        with (
            mock.patch(f"{_MODULE}._has_ssh_keys", return_value=True),
            mock.patch(f"{_MODULE}.has_gpg_keys", return_value=False),
        ):
            apply_credential_mount_defaults(agent_cfg)

        self.assertTrue(agent_cfg.mounts.ssh)
        self.assertIsNone(agent_cfg.mounts.gnupg)

    def test_apply_credential_mount_defaults_enables_gnupg_independently(self) -> None:
        agent_cfg = AgentConfig()

        with (
            mock.patch(f"{_MODULE}._has_ssh_keys", return_value=False),
            mock.patch(f"{_MODULE}.has_gpg_keys", return_value=True),
            mock.patch(f"{_MODULE}.resolve_gpg_home", return_value=mock.Mock()),
        ):
            apply_credential_mount_defaults(agent_cfg)

        self.assertIsNone(agent_cfg.mounts.ssh)
        self.assertTrue(agent_cfg.mounts.gnupg)

    def test_apply_cli_credential_mount_preferences_overrides_both_values(self) -> None:
        agent_cfg = AgentConfig()
        parsed = _build_parsed(ssh=False, gpg=True)

        apply_cli_credential_mount_preferences(agent_cfg, parsed)

        self.assertFalse(agent_cfg.mounts.ssh)
        self.assertTrue(agent_cfg.mounts.gnupg)

    def test_apply_cli_credential_mount_preferences_leaves_unspecified_values(
        self,
    ) -> None:
        agent_cfg = AgentConfig()

        apply_cli_credential_mount_preferences(agent_cfg, _build_parsed())

        self.assertIsNone(agent_cfg.mounts.ssh)
        self.assertIsNone(agent_cfg.mounts.gnupg)

    def test_disable_git_mounts_disables_all_git_mounts(self) -> None:
        agent_cfg = AgentConfig()

        disable_git_mounts(agent_cfg)

        self.assertFalse(agent_cfg.mounts.gitconfig)
        self.assertFalse(agent_cfg.mounts.gitroot)
        self.assertIsNone(agent_cfg.mounts.gnupg)
        self.assertIsNone(agent_cfg.mounts.ssh)


def _build_context(agent_cfg: AgentConfig) -> ConfigContext:
    project_cfg = _ProjectConfig(path="/test-tmp/project", agents={"codex": agent_cfg})
    return ConfigContext(
        store=mock.Mock(),
        project_cfg=project_cfg,
        agents={},
        bases={},
        extensions={},
    )


def _build_parsed(
    docker_socket: bool = False,
    ssh: bool | None = None,
    gpg: bool | None = None,
) -> ParsedArgs:
    return ParsedArgs(False, "", "codex", [], docker_socket, [], ssh=ssh, gpg=gpg)
