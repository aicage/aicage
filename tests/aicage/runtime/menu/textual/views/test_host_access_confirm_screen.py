from unittest import TestCase, mock

from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    DockerOptionValue,
    HostAccessConfirmValues,
)
from aicage.runtime.menu.textual.views import host_access_confirm_screen


class BuiltInShareConfirmScreenTests(TestCase):
    def test_compose_builds_screen_widgets(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [_docker_option()], [], [], [_share()]
        )

        widgets = list(screen.compose())

        self.assertEqual(1, len(widgets))

    def test_on_mount_focuses_ok_button(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [_docker_option()], [_share()], []
        )
        ok_button = mock.Mock()

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            if selector == "#ok":
                return ok_button
            if selector in {
                "#docker_confirm_list",
                "#git_confirm_list",
                "#credential_confirm_list",
                "#extension_confirm_list",
            }:
                raise host_access_confirm_screen.NoMatches("not present")
            raise AssertionError(f"Unexpected selector: {selector}")

        with mock.patch.object(screen, "query_one", side_effect=query_one_side_effect):
            screen.on_mount()

        ok_button.focus.assert_called_once_with()

    def test_on_mount_clears_initial_highlight_for_present_selection_lists(
        self,
    ) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [_docker_option()],
            [_extension_share()],
            [_share()],
        )
        ok_button = mock.Mock()
        docker_selection_list = mock.Mock()
        git_support_selection_list = mock.Mock()
        credential_selection_list = mock.Mock()
        extension_selection_list = mock.Mock()

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            if selector == "#ok":
                return ok_button
            if selector == "#docker_confirm_list":
                return docker_selection_list
            if selector == "#git_confirm_list":
                return git_support_selection_list
            if selector == "#credential_confirm_list":
                return credential_selection_list
            if selector == "#extension_confirm_list":
                return extension_selection_list
            self.fail(f"Unexpected selector: {selector}")

        with mock.patch.object(screen, "query_one", side_effect=query_one_side_effect):
            screen.on_mount()

        self.assertEqual(None, docker_selection_list.highlighted)
        self.assertEqual(None, git_support_selection_list.highlighted)
        self.assertEqual(None, credential_selection_list.highlighted)
        self.assertEqual(None, extension_selection_list.highlighted)

    def test_action_accept_dismisses_selected_host_access_values(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [_docker_option()],
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "gitconfig",
                    "Git config",
                    "/home/user/.gitconfig",
                    None,
                    True,
                ),
            ],
            [_extension_share()],
            [_share()],
        )
        docker_selection_list = mock.Mock()
        docker_selection_list.selected = ["docker"]
        git_support_selection_list = mock.Mock()
        git_support_selection_list.selected = []
        credential_selection_list = mock.Mock()
        credential_selection_list.selected = ["builtin:credentials:ssh"]
        extension_selection_list = mock.Mock()
        extension_selection_list.selected = ["builtin:extension:gh"]

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            if selector == "#docker_confirm_list":
                return docker_selection_list
            if selector == "#git_confirm_list":
                return git_support_selection_list
            if selector == "#credential_confirm_list":
                return credential_selection_list
            if selector == "#extension_confirm_list":
                return extension_selection_list
            self.fail(f"Unexpected selector: {selector}")

        with (
            mock.patch.object(screen, "query_one", side_effect=query_one_side_effect),
            mock.patch.object(screen, "dismiss") as dismiss_mock,
        ):
            screen.action_accept()

        dismiss_mock.assert_called_once_with(
            HostAccessConfirmValues(
                docker_options=[
                    DockerOptionValue("docker", "Docker socket", None, None, True),
                ],
                git_shares=[
                    BuiltInShareValue(
                        BuiltInShareSource.GIT_SUPPORT,
                        "gitconfig",
                        "Git config",
                        "/home/user/.gitconfig",
                        None,
                        False,
                    ),
                ],
                credential_shares=[
                    BuiltInShareValue(
                        BuiltInShareSource.CREDENTIALS,
                        "ssh",
                        "SSH",
                        "/home/user/.ssh",
                        None,
                        True,
                    )
                ],
                extension_shares=[
                    BuiltInShareValue(
                        BuiltInShareSource.EXTENSION,
                        "gh",
                        "Extension gh",
                        "/home/user/.config/gh",
                        None,
                        True,
                    )
                ],
            )
        )

    def test_compose_formats_mount_lists_with_aligned_prefixes(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [],
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "gitconfig",
                    "Git config",
                    "/home/user/.gitconfig",
                    None,
                    False,
                ),
            ],
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gh",
                    "Extension gh",
                    "/home/user/.config/gh:ro",
                    None,
                    True,
                )
            ],
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/home/user/.ssh",
                    None,
                    True,
                )
            ],
        )

        git_rows = list(screen._git_selection_list()._options)
        extension_rows = list(screen._extension_selection_list()._options)

        credential_rows = list(screen._credential_selection_list()._options)
        self.assertEqual("Git config: /home/user/.gitconfig", git_rows[0].prompt)
        self.assertEqual("SSH: /home/user/.ssh", credential_rows[0].prompt)
        self.assertEqual(
            "Extension gh: Read-only: /home/user/.config/gh", extension_rows[0].prompt
        )

    def test_compose_formats_pathless_git_support_setting(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [],
            [],
            [],
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS, "ssh", "SSH", None, None, True
                )
            ],
        )

        git_rows = list(screen._credential_selection_list()._options)

        self.assertEqual("SSH", git_rows[0].prompt)

    def test__git_hint_describes_global_scope(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [], [], [], "global"
        )

        hint = screen._git_hint()

        self.assertEqual("Persists Git settings for every project.", hint)

    def test_docker_selection_list_includes_docker_option(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [_docker_option()],
            [],
            [],
        )

        rows = list(screen._docker_selection_list()._options)
        details = screen._docker_option_details()

        self.assertEqual(
            "Docker socket",
            rows[0].prompt,
        )
        self.assertEqual([], details)

    def test_on_selection_list_selection_toggled_syncs_extension_group_rows(
        self,
    ) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [],
            [],
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/home/user/.config/gcloud",
                    None,
                    True,
                    "gcloud:/home/user/.config/gcloud",
                ),
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/home/user/.boto",
                    None,
                    True,
                    "gcloud:/home/user/.boto",
                ),
            ],
        )
        event = mock.Mock()
        event.selection_list.id = "extension_confirm_list"
        event.selection.value = "builtin:extension:gcloud:/home/user/.config/gcloud"
        event.selection_list.selected = [
            "builtin:extension:gcloud:/home/user/.config/gcloud"
        ]

        screen.on_selection_list_selection_toggled(event)

        event.selection_list.select.assert_any_call(
            "builtin:extension:gcloud:/home/user/.config/gcloud"
        )
        event.selection_list.select.assert_any_call(
            "builtin:extension:gcloud:/home/user/.boto"
        )

    def test_on_button_pressed_dispatches_ok(self) -> None:
        screen = host_access_confirm_screen.HostAccessConfirmScreen(
            [_docker_option()], [_share()], []
        )
        event = mock.Mock()
        event.button.id = "ok"

        with mock.patch.object(screen, "action_accept") as accept_mock:
            screen.on_button_pressed(event)

        event.stop.assert_called_once_with()
        accept_mock.assert_called_once_with()


def _share() -> BuiltInShareValue:
    return BuiltInShareValue(
        BuiltInShareSource.CREDENTIALS, "ssh", "SSH", "/home/user/.ssh", None, True
    )


def _extension_share() -> BuiltInShareValue:
    return BuiltInShareValue(
        BuiltInShareSource.EXTENSION,
        "gh",
        "Extension gh",
        "/home/user/.config/gh",
        None,
        True,
    )


def _docker_option() -> DockerOptionValue:
    return DockerOptionValue("docker", "Docker socket", None, None, True)
