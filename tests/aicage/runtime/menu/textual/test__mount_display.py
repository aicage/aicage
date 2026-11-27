from unittest import TestCase

from textual.widgets.selection_list import Selection

from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GNUPG_KEY,
    MOUNT_SSH_KEY,
)
from aicage.runtime.menu.textual import _mount_display
from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
)


class MountDisplayTests(TestCase):
    def test_credential_label_returns_known_label(self) -> None:
        self.assertEqual("SSH keys", _mount_display.credential_label(MOUNT_SSH_KEY))

    def test_git_support_label_returns_known_label(self) -> None:
        value = _mount_display.git_support_label(MOUNT_GITCONFIG_KEY)

        self.assertEqual("Git config", value)

    def test_git_support_config_label_returns_descriptive_label(self) -> None:
        value = _mount_display.git_support_config_label(MOUNT_GITCONFIG_KEY)

        self.assertEqual("Git configuration (identity, aliases, and settings)", value)

    def test_credential_config_label_describes_ssh_keys(self) -> None:
        value = _mount_display.credential_config_label(MOUNT_SSH_KEY)

        self.assertEqual("SSH keys : SSH socket", value)

    def test_credential_config_label_describes_gnupg_keys(self) -> None:
        value = _mount_display.credential_config_label(MOUNT_GNUPG_KEY)

        self.assertEqual("GnuPG keys : GnuPG socket", value)

    def test_extension_label_returns_prefixed_label(self) -> None:
        value = _mount_display.extension_label("gh")

        self.assertEqual("Extension gh", value)

    def test_overview_mount_list_items_returns_built_in_and_custom_items(self) -> None:
        values = _mount_display.overview_mount_list_items(
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                )
            ],
            [CustomShareValue("/test-tmp/logs:ro"), CustomShareValue("/test-tmp/data")],
        )

        self.assertEqual("SSH", values[0].prefix)
        self.assertEqual("/test-tmp/.ssh", values[0].path)
        self.assertEqual("builtin:credentials:ssh", values[0].selection_key)
        self.assertTrue(values[0].enabled)
        self.assertEqual("Read-only", values[1].prefix)
        self.assertEqual("/test-tmp/logs", values[1].path)
        self.assertEqual("custom:/test-tmp/logs:ro", values[1].selection_key)
        self.assertEqual(None, values[2].prefix)
        self.assertEqual("/test-tmp/data", values[2].path)
        self.assertEqual("custom:/test-tmp/data", values[2].selection_key)

    def test_confirm_mount_list_items_returns_confirm_items(self) -> None:
        values = _mount_display.confirm_mount_list_items(
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gh",
                    "Extension gh",
                    "/test-tmp/gh:ro",
                    None,
                    False,
                    "gh:/test-tmp/gh:ro",
                )
            ]
        )

        self.assertEqual("Extension gh", values[0].prefix)
        self.assertEqual("Read-only: /test-tmp/gh", values[0].path)
        self.assertEqual(
            "builtin:extension:gh:/test-tmp/gh:ro", values[0].selection_key
        )
        self.assertFalse(values[0].enabled)

    def test_mount_selection_rows_displays_pathless_git_support_label(self) -> None:
        rows = _mount_display.mount_selection_rows(
            _mount_display.confirm_mount_list_items(
                [
                    BuiltInShareValue(
                        BuiltInShareSource.CREDENTIALS, "ssh", "SSH", None, None, True
                    )
                ]
            )
        )

        self.assertEqual([("SSH", "builtin:credentials:ssh", True)], rows)

    def test_mount_selection_rows_aligns_prefixes(self) -> None:
        rows = _mount_display.mount_selection_rows(
            _mount_display.overview_mount_list_items(
                [
                    BuiltInShareValue(
                        BuiltInShareSource.CREDENTIALS,
                        "ssh",
                        "SSH",
                        "/test-tmp/.ssh",
                        None,
                        True,
                    )
                ],
                [CustomShareValue("/test-tmp/data")],
            )
        )

        self.assertEqual(
            [
                ("SSH: /test-tmp/.ssh", "builtin:credentials:ssh", True),
                ("   : /test-tmp/data", "custom:/test-tmp/data", True),
            ],
            rows,
        )

    def test_mount_selection_rows_disables_inherited_mounts(self) -> None:
        rows = _mount_display.mount_selection_rows(
            _mount_display.overview_mount_list_items(
                [
                    BuiltInShareValue(
                        BuiltInShareSource.GIT_SUPPORT,
                        "ssh",
                        "SSH",
                        "/test-tmp/.ssh",
                        True,
                        True,
                        inherited=True,
                    )
                ],
                [],
            )
        )

        self.assertIsInstance(rows[0], Selection)
        assert isinstance(rows[0], Selection)
        self.assertTrue(rows[0].disabled)
