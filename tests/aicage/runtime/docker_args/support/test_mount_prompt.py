import tempfile
from pathlib import Path
from unittest import TestCase, mock

from aicage.config.extensions.loader import ExtensionMetadata
from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    MOUNT_GNUPG_KEY,
    AgentConfig,
    _AgentMounts,
)
from aicage.runtime.docker_args.support import mount_prompt as mount_prompt_module

_MODULE = "aicage.runtime.docker_args.support.mount_prompt"


class MountPromptTests(TestCase):
    def test_select_all_mounts_returns_all_group_keys(self) -> None:
        request = mount_prompt_module._MountSelectionRequest(
            git_items=[mount_prompt_module._MountPromptItem("git", "Git")],
            extension_items=[mount_prompt_module._MountPromptItem("gh", "GitHub CLI")],
        )

        self.assertEqual(
            ["git", "gh"],
            mount_prompt_module.select_all_mounts(request),
        )

    def test_resolve_mount_prompt_prefs_returns_relevant_git_prefs(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts())
        project_path = Path("/repo")
        git_items = [
            (MOUNT_GITCONFIG_KEY, "Git config (name/email): /test-tmp/gitconfig"),
            (MOUNT_GITROOT_KEY, "Git root (repository access): /test-tmp/root"),
            (MOUNT_GNUPG_KEY, "GnuPG keys (for Git signing): /test-tmp/gnupg"),
        ]

        with (
            mock.patch(f"{_MODULE}._git_support_prompt_items", return_value=git_items),
        ):
            prefs = mount_prompt_module.resolve_mount_prompt_prefs(
                project_path,
                agent_cfg,
                {},
                lambda _request: [
                    MOUNT_GITCONFIG_KEY,
                    MOUNT_GITROOT_KEY,
                    MOUNT_GNUPG_KEY,
                ],
            )

        assert prefs is not None
        self.assertEqual(
            {MOUNT_GITCONFIG_KEY, MOUNT_GITROOT_KEY, MOUNT_GNUPG_KEY}, prefs.git_mounts
        )
        self.assertEqual({}, prefs.extension_mounts)

    def test_resolve_mount_prompt_prefs_skips_when_no_items(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts())

        select_mounts = mock.Mock()
        with mock.patch(f"{_MODULE}._git_support_prompt_items", return_value=[]):
            prefs = mount_prompt_module.resolve_mount_prompt_prefs(
                Path("/repo"), agent_cfg, {}, select_mounts
            )

        self.assertIsNone(prefs)
        select_mounts.assert_not_called()

    def test_resolve_mount_prompt_prefs_appends_extension_group_items(self) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(), extensions=["gh"])
        project_path = Path("/repo")
        extension = ExtensionMetadata(
            extension_id="gh",
            name="GitHub CLI",
            description="Desc",
            shares=["~/.config/gh", "~/.cache/gh:ro"],
            directory=Path("/test-tmp/ext"),
            scripts_dir=Path("/test-tmp/ext/scripts"),
            dockerfile_path=None,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            git_items = [
                (
                    MOUNT_GITCONFIG_KEY,
                    f"Git config (name/email): {Path(tmp_dir) / '.gitconfig'}",
                )
            ]
            with (
                mock.patch(
                    f"{_MODULE}._git_support_prompt_items", return_value=git_items
                ),
            ):
                select_mounts = mock.Mock(return_value=[MOUNT_GITCONFIG_KEY, "gh"])
                prefs = mount_prompt_module.resolve_mount_prompt_prefs(
                    project_path,
                    agent_cfg,
                    {"gh": extension},
                    select_mounts,
                )

        assert prefs is not None
        request = select_mounts.call_args.args[0]
        self.assertEqual(MOUNT_GITCONFIG_KEY, request.git_items[0].key)
        self.assertEqual("gh", request.extension_items[0].key)
        self.assertIn("Extension gh shares:", request.extension_items[0].description)
        self.assertEqual({MOUNT_GITCONFIG_KEY}, prefs.git_mounts)
        self.assertEqual({"gh": True}, prefs.extension_mounts)

    def test_resolve_mount_prompt_prefs_returns_unselected_extension_group_false(
        self,
    ) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(), extensions=["gh"])
        extension = ExtensionMetadata(
            extension_id="gh",
            name="GitHub CLI",
            description="Desc",
            shares=["~/.config/gh"],
            directory=Path("/test-tmp/ext"),
            scripts_dir=Path("/test-tmp/ext/scripts"),
            dockerfile_path=None,
        )

        with mock.patch(f"{_MODULE}._git_support_prompt_items", return_value=[]):
            prefs = mount_prompt_module.resolve_mount_prompt_prefs(
                Path("/repo"), agent_cfg, {"gh": extension}, lambda _request: []
            )

        assert prefs is not None
        self.assertEqual(set(), prefs.git_mounts)
        self.assertEqual({"gh": False}, prefs.extension_mounts)

    def test_extension_mount_defaults_enables_unconfigured_extensions(self) -> None:
        agent_cfg = AgentConfig(
            mounts=_AgentMounts(),
            extensions=["gh", "configured"],
            extension_mounts={"configured": False},
        )
        extension = ExtensionMetadata(
            extension_id="gh",
            name="GitHub CLI",
            description="Desc",
            shares=["~/.config/gh"],
            directory=Path("/test-tmp/ext"),
            scripts_dir=Path("/test-tmp/ext/scripts"),
            dockerfile_path=None,
        )

        defaults = mount_prompt_module.extension_mount_defaults(
            Path("/repo"), agent_cfg, {"gh": extension}
        )

        self.assertEqual({"gh": True}, defaults)

    def test_resolve_mount_prompt_prefs_skips_extensions_with_stored_choice(
        self,
    ) -> None:
        agent_cfg = AgentConfig(
            mounts=_AgentMounts(),
            extensions=["gh", "sample"],
            extension_mounts={"gh": True},
        )
        extension = ExtensionMetadata(
            extension_id="sample",
            name="Sample",
            description="Desc",
            shares=["~/.sample"],
            directory=Path("/test-tmp/ext"),
            scripts_dir=Path("/test-tmp/ext/scripts"),
            dockerfile_path=None,
        )

        select_mounts = mock.Mock(return_value=["sample"])
        with mock.patch(f"{_MODULE}._git_support_prompt_items", return_value=[]):
            prefs = mount_prompt_module.resolve_mount_prompt_prefs(
                Path("/repo"), agent_cfg, {"sample": extension}, select_mounts
            )

        assert prefs is not None
        self.assertEqual(
            [
                mount_prompt_module._MountPromptItem(
                    "sample",
                    f"Extension sample shares: {Path.home().resolve() / '.sample'}",
                )
            ],
            select_mounts.call_args.args[0].extension_items,
        )
        self.assertEqual({"sample": True}, prefs.extension_mounts)

    def test_resolve_mount_prompt_prefs_skips_missing_or_shareless_extensions(
        self,
    ) -> None:
        agent_cfg = AgentConfig(mounts=_AgentMounts(), extensions=["missing", "empty"])
        extension = ExtensionMetadata(
            extension_id="empty",
            name="Empty",
            description="Desc",
            shares=[],
            directory=Path("/test-tmp/ext"),
            scripts_dir=Path("/test-tmp/ext/scripts"),
            dockerfile_path=None,
        )

        select_mounts = mock.Mock()
        with mock.patch(f"{_MODULE}._git_support_prompt_items", return_value=[]):
            prefs = mount_prompt_module.resolve_mount_prompt_prefs(
                Path("/repo"), agent_cfg, {"empty": extension}, select_mounts
            )

        self.assertIsNone(prefs)
        select_mounts.assert_not_called()
