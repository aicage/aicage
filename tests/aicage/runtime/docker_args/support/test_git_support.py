from pathlib import Path
from unittest import TestCase, mock

from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    _AgentMounts,
)
from aicage.runtime.docker_args.support import git_support

_MODULE = "aicage.runtime.docker_args.support.git_support"


class GitSupportTests(TestCase):
    def test_resolve_git_config_path_parses_first_file(self) -> None:
        output = (
            "file:/home/user/.gitconfig user.name=Name\nfile:/tmp/other key=value\n"
        )
        with mock.patch(f"{_MODULE}.capture_stdout", return_value=output):
            self.assertEqual(
                Path("/home/user/.gitconfig"), git_support.resolve_git_config_path()
            )

    def test_resolve_git_config_path_handles_empty(self) -> None:
        with mock.patch(f"{_MODULE}.capture_stdout", return_value=""):
            self.assertIsNone(git_support.resolve_git_config_path())

    def test_resolve_git_root_prefers_superproject(self) -> None:
        with mock.patch(f"{_MODULE}.capture_stdout", return_value="/repo\n"):
            self.assertEqual(
                Path("/repo").resolve(),
                git_support.resolve_git_root(Path("/repo/sub")),
            )

    def test_resolve_git_root_falls_back_to_toplevel(self) -> None:
        with mock.patch(f"{_MODULE}.capture_stdout", side_effect=["", "/repo\n"]):
            self.assertEqual(
                Path("/repo").resolve(),
                git_support.resolve_git_root(Path("/repo/sub")),
            )

    def test__git_support_prompt_items_only_contains_git_mounts(self) -> None:
        git_config = Path("/home/user/.gitconfig")
        git_root = Path("/repo/root")
        with (
            mock.patch(f"{_MODULE}.resolve_git_config_path", return_value=git_config),
            mock.patch(f"{_MODULE}.resolve_git_root", return_value=git_root),
            mock.patch("pathlib.Path.exists", return_value=True),
        ):
            self.assertEqual(
                [
                    (MOUNT_GITCONFIG_KEY, f"Git config (name/email): {git_config}"),
                    (MOUNT_GITROOT_KEY, f"Git root (repository access): {git_root}"),
                ],
                git_support._git_support_prompt_items(Path("/repo"), _AgentMounts()),
            )

    def test_git_mount_defaults_respects_saved_choices(self) -> None:
        with mock.patch(
            f"{_MODULE}.detected_git_mounts",
            return_value={MOUNT_GITCONFIG_KEY, MOUNT_GITROOT_KEY},
        ):
            self.assertEqual(
                {MOUNT_GITROOT_KEY},
                git_support.git_mount_defaults(
                    Path("/repo"), _AgentMounts(gitconfig=False)
                ),
            )

    def test_detected_git_mounts_ignores_mount_preferences(self) -> None:
        with mock.patch(
            f"{_MODULE}._git_support_prompt_items",
            return_value=[(MOUNT_GITCONFIG_KEY, "Git config")],
        ):
            self.assertEqual(
                {MOUNT_GITCONFIG_KEY}, git_support.detected_git_mounts(Path("/repo"))
            )
