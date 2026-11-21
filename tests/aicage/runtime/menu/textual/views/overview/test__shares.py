from unittest import TestCase, mock

from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
)
from aicage.runtime.menu.textual._state import OverviewState
from aicage.runtime.menu.textual.views.overview import _shares


class SharesOverviewTests(TestCase):
    def test_is_git_support_button_identifies_git_support_button(self) -> None:
        self.assertTrue(_shares.is_git_support_button("git_mount_ssh"))
        self.assertFalse(_shares.is_git_support_button("add_share"))

    def test_git_support_key_returns_mount_key(self) -> None:
        self.assertEqual("ssh", _shares.git_support_key("git_mount_ssh"))

    def test_next_git_support_value_cycles_auto_on_off(self) -> None:
        self.assertTrue(_shares.next_git_support_value(None))
        self.assertFalse(_shares.next_git_support_value(True))
        self.assertIsNone(_shares.next_git_support_value(False))

    def test_share_widgets_builds_widgets(self) -> None:
        widgets = _shares.share_widgets(OverviewState(None, [], [], False))

        self.assertEqual(2, len(widgets))

    def test_refresh_shares_updates_visible_widgets(self) -> None:
        container = mock.Mock()
        overview = mock.Mock()
        title = mock.Mock()
        selection_list = mock.Mock()

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            return {
                "#shares_overview": overview,
                "#shares_overview_title": title,
                "#shares_overview_list": selection_list,
            }[selector]

        container.query_one.side_effect = query_one_side_effect
        state = OverviewState(
            None,
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                )
            ],
            [CustomShareValue("/test-tmp/logs")],
            False,
        )

        _shares.refresh_shares(container, state)

        self.assertTrue(overview.display)
        title.update.assert_called_once_with("Bind Mounts")
        selection_list.clear_options.assert_called_once_with()

    def test_refresh_shares_formats_read_only_mounts(self) -> None:
        container = mock.Mock()
        overview = mock.Mock()
        title = mock.Mock()
        selection_list = mock.Mock()

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            return {
                "#shares_overview": overview,
                "#shares_overview_title": title,
                "#shares_overview_list": selection_list,
            }[selector]

        container.query_one.side_effect = query_one_side_effect
        state = OverviewState(None, [], [CustomShareValue("/test-tmp/logs:ro")], False)

        _shares.refresh_shares(container, state)

        selection_list.add_options.assert_called_once_with(
            [("Read-only: /test-tmp/logs", "custom:/test-tmp/logs:ro", True)]
        )

    def test_refresh_shares_aligns_prefixless_mounts_with_built_in_items(self) -> None:
        container = mock.Mock()
        overview = mock.Mock()
        title = mock.Mock()
        selection_list = mock.Mock()

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            return {
                "#shares_overview": overview,
                "#shares_overview_title": title,
                "#shares_overview_list": selection_list,
            }[selector]

        container.query_one.side_effect = query_one_side_effect
        state = OverviewState(
            None,
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                )
            ],
            [CustomShareValue("/test-tmp/logs")],
            False,
        )

        _shares.refresh_shares(container, state)

        selection_list.add_options.assert_called_once_with(
            [
                ("SSH: /test-tmp/.ssh", "builtin:git_support:ssh", True),
                ("   : /test-tmp/logs", "custom:/test-tmp/logs", True),
            ]
        )

    def test_merge_built_in_shares_preserves_current_enabled_state(self) -> None:
        values = _shares.merge_built_in_shares(
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    False,
                )
            ],
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                )
            ],
        )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                )
            ],
            values,
        )

    def test_merge_built_in_shares_preserves_pending_confirmation(self) -> None:
        values = _shares.merge_built_in_shares(
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "gnupg",
                    "GnuPG",
                    "/test-tmp/gnupg",
                    True,
                    True,
                )
            ],
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "gnupg",
                    "GnuPG",
                    "/test-tmp/gnupg",
                    None,
                    True,
                )
            ],
        )

        self.assertIsNone(values[0].persisted)

    def test_current_custom_shares_returns_copy(self) -> None:
        state = OverviewState(None, [], [CustomShareValue("/test-tmp/logs")], False)

        values = _shares.current_custom_shares(state)

        self.assertEqual([CustomShareValue("/test-tmp/logs")], values)
        self.assertIsNot(values, state.custom_shares)
