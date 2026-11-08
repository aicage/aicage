from unittest import IsolatedAsyncioTestCase, TestCase, mock

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import Button, SelectionList, Static

from aicage.cli_types import ParsedArgs
from aicage.config.project_config import AgentConfig
from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
)
from aicage.runtime.menu.textual._state import OverviewState
from aicage.runtime.menu.textual.views.overview._selection_list import (
    _OverviewSelectionList,
)
from aicage.runtime.menu.textual.views.overview.view import Overview

from ...._test_support import _build_context, _build_draft


class OverviewTests(TestCase):
    def test_section_label_dims_summary(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )

        value = overview._section_label("Extensions", "none")

        self.assertEqual("Extensions\nnone", str(value))
        self.assertEqual("bold", str(value.spans[0].style))
        self.assertEqual("dim not bold", str(value.spans[1].style))

    def test_compose_builds_widgets(self) -> None:
        widgets = list(
            Overview(
                "codex", "/test-tmp/project", OverviewState(None, [], [], False)
            ).compose()
        )

        self.assertEqual(1, len(widgets))

    def test_compose_includes_project_path_row(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )

        self.assertEqual("/test-tmp/project", overview._project_path)

    def test_compose_formats_agent_and_project_context(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )

        self.assertEqual("codex", overview._agent)
        self.assertEqual("/test-tmp/project", overview._project_path)
        self.assertEqual("Agent:   codex", overview._context_line("Agent:", "codex"))
        self.assertEqual(
            "Project: /test-tmp/project",
            overview._context_line("Project:", "/test-tmp/project"),
        )

    def test__scope_banner_returns_global_configuration_message(self) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(None, [], [], False),
            "global configuration",
        )

        banner = overview._scope_banner()

        self.assertIsInstance(banner, Static)
        assert banner is not None
        self.assertIn("GLOBAL CONFIGURATION", str(banner.render()))
        self.assertIn("every project", str(banner.render()))

    def test__scope_banner_returns_tree_configuration_message(self) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(None, [], [], False),
            "directory tree configuration",
        )

        banner = overview._scope_banner()

        self.assertIsInstance(banner, Static)
        assert banner is not None
        self.assertIn("DIRECTORY TREE CONFIGURATION", str(banner.render()))
        self.assertIn("descendant directories/projects", str(banner.render()))

    def test__scope_banner_skips_project_configuration(self) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(None, [], [], False),
        )

        self.assertIsNone(overview._scope_banner())

    def test_on_button_pressed_posts_accept_message(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        event = mock.Mock()
        event.button.id = "ok"

        with mock.patch.object(overview, "post_message") as post_message_mock:
            overview.on_button_pressed(event)

        self.assertIsInstance(
            post_message_mock.call_args.args[0], Overview.AcceptRequested
        )

    def test_on_button_pressed_cycles_credential_value(self) -> None:
        state = OverviewState(None, [], [], False, credential_values={"ssh": None})
        overview = Overview("codex", "/test-tmp/project", state, scope="global")
        event = mock.Mock()
        event.button.id = "credential_mount_ssh"

        with mock.patch.object(overview, "post_message") as post_message_mock:
            overview.on_button_pressed(event)

        self.assertTrue(state.credential_values["ssh"])
        self.assertEqual("On\u00a0\u00a0", event.button.label)
        self.assertIsInstance(
            post_message_mock.call_args.args[0], Overview.HostAccessChanged
        )

    def test_on_selection_list_selected_changed_updates_built_in_shares(self) -> None:
        state = OverviewState(
            None,
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
            [],
            False,
        )
        overview = Overview("codex", "/test-tmp/project", state)
        event = mock.Mock()
        event.selection_list.id = "shares_overview_list"
        event.selection_list.selected = []

        overview.on_selection_list_selected_changed(event)

        self.assertFalse(state.built_in_shares[0].enabled)

    def test_on_selection_list_selection_toggled_posts_custom_share_message(
        self,
    ) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        event = mock.Mock()
        event.selection_list.id = "shares_overview_list"
        event.selection.value = "custom:/test-tmp/logs"

        with mock.patch.object(overview, "post_message") as post_message_mock:
            overview.on_selection_list_selection_toggled(event)

        event.selection_list.select.assert_called_once_with("custom:/test-tmp/logs")
        self.assertIsInstance(
            post_message_mock.call_args.args[0], Overview.EditCustomShareRequested
        )

    def test_on_selection_list_selection_toggled_syncs_extension_group_rows(
        self,
    ) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(
                None,
                [
                    BuiltInShareValue(
                        BuiltInShareSource.EXTENSION,
                        "gcloud",
                        "Extension gcloud",
                        "/test-tmp/gcloud",
                        None,
                        True,
                        "gcloud:/test-tmp/gcloud",
                    ),
                    BuiltInShareValue(
                        BuiltInShareSource.EXTENSION,
                        "gcloud",
                        "Extension gcloud",
                        "/test-tmp/boto",
                        None,
                        True,
                        "gcloud:/test-tmp/boto",
                    ),
                ],
                [],
                False,
            ),
        )
        event = mock.Mock()
        event.selection_list.id = "shares_overview_list"
        event.selection.value = "builtin:extension:gcloud:/test-tmp/gcloud"
        event.selection_list.selected = ["builtin:extension:gcloud:/test-tmp/gcloud"]

        overview.on_selection_list_selection_toggled(event)

        event.selection_list.select.assert_any_call(
            "builtin:extension:gcloud:/test-tmp/gcloud"
        )
        event.selection_list.select.assert_any_call(
            "builtin:extension:gcloud:/test-tmp/boto"
        )

    def test_overview_selection_list_focus_sets_initial_highlight(self) -> None:
        selection_list = _OverviewSelectionList(
            ("Docker socket", "docker:socket", True)
        )
        focus_event = events.Focus()

        with mock.patch.object(SelectionList, "_on_focus") as parent_on_focus_mock:
            selection_list._on_focus(focus_event)

        parent_on_focus_mock.assert_called_once_with(focus_event)
        self.assertEqual(0, selection_list.highlighted)

    def test_on_selection_list_selected_changed_updates_docker_state(self) -> None:
        state = OverviewState(None, [], [], False)
        overview = Overview("codex", "/test-tmp/project", state)
        event = mock.Mock()
        event.selection_list.id = "docker_overview_list"
        event.selection_list.selected = ["docker:socket"]

        with mock.patch.object(overview, "apply_shell_width"):
            overview.on_selection_list_selected_changed(event)

        self.assertTrue(state.docker_socket_enabled)

    def test_on_selection_list_selection_toggled_requests_global_scope(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        event = mock.Mock()
        event.selection_list.id = "scope_overview_list"
        event.selection.value = "global"
        event.selection_list.selected = ["global"]

        with mock.patch.object(overview, "post_message") as post_message_mock:
            overview.on_selection_list_selection_toggled(event)

        self.assertIsInstance(
            post_message_mock.call_args.args[0], Overview.ScopeChangeRequested
        )
        self.assertEqual("global", post_message_mock.call_args.args[0].scope)

    def test_on_selection_list_selection_toggled_requests_project_scope(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        event = mock.Mock()
        event.selection_list.id = "scope_overview_list"
        event.selection.value = "global"
        event.selection_list.selected = []

        with mock.patch.object(overview, "post_message") as post_message_mock:
            overview.on_selection_list_selection_toggled(event)

        self.assertEqual("project", post_message_mock.call_args.args[0].scope)

    def test_refresh_scope_updates_scope_selection(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        selection_list = mock.Mock()

        with mock.patch.object(overview, "query_one", return_value=selection_list):
            overview.refresh_scope("global")

        self.assertEqual("global", overview._scope)
        selection_list.clear_options.assert_called_once_with()
        selection_list.add_options.assert_called_once()

    def test_refresh_from_updates_overview_widgets(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        shell = mock.Mock()
        shell.styles = mock.Mock()
        base_button = mock.Mock()
        extensions_button = mock.Mock()
        extras_button = mock.Mock()
        shares_overview = mock.Mock()
        shares_overview.display = True
        shares_title = mock.Mock()
        shares_list = mock.Mock()
        shares_list.highlighted = None
        docker_title = mock.Mock()
        docker_list = mock.Mock()
        docker_list.highlighted = None

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            return {
                "#shell": shell,
                "#base": base_button,
                "#extensions": extensions_button,
                "#extras": extras_button,
                "#shares_overview": shares_overview,
                "#shares_overview_title": shares_title,
                "#shares_overview_list": shares_list,
                "#docker_overview_title": docker_title,
                "#docker_overview_list": docker_list,
            }[selector]

        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(False, "", "codex", [], False, []),
        )

        with (
            mock.patch.object(
                type(overview),
                "size",
                new_callable=mock.PropertyMock,
                return_value=mock.Mock(width=120),
            ),
            mock.patch.object(overview, "query_one", side_effect=query_one_side_effect),
            mock.patch(
                "aicage.runtime.menu.textual.views.overview.view.shares_values"
            ) as shares_values,
        ):
            shares_values.return_value = mock.Mock(
                built_in_shares=[
                    BuiltInShareValue(
                        BuiltInShareSource.CREDENTIALS,
                        "ssh",
                        "SSH",
                        "/test-tmp/.ssh",
                        None,
                        True,
                    )
                ]
            )
            overview.refresh_from(draft, _build_context())

        self.assertEqual("Base\nubuntu", str(base_button.label))
        self.assertEqual("Extensions\nnone", str(extensions_button.label))
        self.assertEqual("Docker Args\nnone", str(extras_button.label))
        self.assertEqual(None, shares_list.highlighted)
        self.assertEqual(None, docker_list.highlighted)

    def test_refresh_from_hides_host_access_mounts_for_global_configuration(
        self,
    ) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(None, [], [], False),
            scope="global",
        )
        shell = mock.Mock()
        shell.styles = mock.Mock()
        base_button = mock.Mock()
        extensions_button = mock.Mock()
        extras_button = mock.Mock()
        git_support_buttons = {
            f"#git_mount_{key}": mock.Mock() for key in ("gitconfig", "gitroot")
        }
        git_support_buttons["#credential_mount_ssh"] = mock.Mock()
        git_support_buttons["#credential_mount_gnupg"] = mock.Mock()
        shares_overview = mock.Mock()
        shares_overview.display = True
        shares_title = mock.Mock()
        shares_list = mock.Mock()
        shares_list.highlighted = None
        docker_title = mock.Mock()
        docker_list = mock.Mock()
        docker_list.highlighted = None

        def query_one_side_effect(selector: str, _expected_type: object) -> mock.Mock:
            values = {
                "#shell": shell,
                "#base": base_button,
                "#extensions": extensions_button,
                "#extras": extras_button,
                "#shares_overview": shares_overview,
                "#shares_overview_title": shares_title,
                "#shares_overview_list": shares_list,
                "#docker_overview_title": docker_title,
                "#docker_overview_list": docker_list,
            }
            if selector in values:
                return values[selector]
            return git_support_buttons[selector]

        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(False, "", "codex", [], False, []),
        )

        with (
            mock.patch.object(
                type(overview),
                "size",
                new_callable=mock.PropertyMock,
                return_value=mock.Mock(width=120),
            ),
            mock.patch.object(overview, "query_one", side_effect=query_one_side_effect),
            mock.patch(
                "aicage.runtime.menu.textual.views.overview.view.shares_values"
            ) as shares_values,
        ):
            shares_values.return_value = mock.Mock(
                built_in_shares=[
                    BuiltInShareValue(
                        BuiltInShareSource.GIT_SUPPORT,
                        "gitconfig",
                        "Git config",
                        "/test-tmp/gitconfig",
                        None,
                        True,
                    ),
                    BuiltInShareValue(
                        BuiltInShareSource.CREDENTIALS,
                        "ssh",
                        "SSH",
                        "/test-tmp/.ssh",
                        None,
                        True,
                    ),
                ]
            )
            overview.refresh_from(draft, _build_context())

        self.assertEqual([], overview._state.built_in_shares)

    def test_apply_shell_width_sets_fixed_width(self) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(
                None,
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
                [CustomShareValue("/test-tmp/logs")],
                False,
            ),
        )
        shell = mock.Mock()
        shell.styles = mock.Mock()

        with mock.patch.object(overview, "query_one", return_value=shell):
            overview.apply_shell_width(120)

        self.assertEqual(shell.styles.width, shell.styles.min_width)
        self.assertEqual(shell.styles.width, shell.styles.max_width)

    def test_focus_default_focuses_ok_button(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        button = mock.Mock(spec=Button)

        with mock.patch.object(overview, "query_one", return_value=button):
            overview.focus_default()

        button.focus.assert_called_once_with()

    def test_focus_section_focuses_section_button(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        button = mock.Mock(spec=Button)

        with mock.patch.object(overview, "query_one", return_value=button):
            overview.focus_section("base")

        button.focus.assert_called_once_with()

    def test_hide_shell_hides_shell(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        shell = mock.Mock()

        with mock.patch.object(overview, "query_one", return_value=shell):
            overview.hide_shell()

        self.assertFalse(shell.display)

    def test_show_shell_shows_shell(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        shell = mock.Mock()

        with mock.patch.object(overview, "query_one", return_value=shell):
            overview.show_shell()

        self.assertTrue(shell.display)

    def test_current_built_in_shares_returns_selected_state(self) -> None:
        overview = Overview(
            "codex",
            "/test-tmp/project",
            OverviewState(
                None,
                [
                    BuiltInShareValue(
                        BuiltInShareSource.CREDENTIALS,
                        "ssh",
                        "SSH",
                        "/test-tmp/.ssh",
                        None,
                        False,
                    )
                ],
                [],
                False,
            ),
        )
        selection_list = mock.Mock(spec=SelectionList)
        selection_list.selected = ["builtin:credentials:ssh"]

        with mock.patch.object(overview, "query_one", return_value=selection_list):
            values = overview.current_built_in_shares()

        self.assertTrue(values[0].enabled)

    def test_current_custom_shares_returns_copy(self) -> None:
        state = OverviewState(None, [], [CustomShareValue("/test-tmp/logs")], False)
        overview = Overview("codex", "/test-tmp/project", state)

        values = overview.current_custom_shares()

        self.assertEqual(state.custom_shares, values)
        self.assertIsNot(state.custom_shares, values)

    def test_current_host_options_returns_selected_state(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        selection_list = mock.Mock(spec=SelectionList)
        selection_list.selected = ["docker:socket"]

        with mock.patch.object(overview, "query_one", return_value=selection_list):
            values = overview.current_host_options(False)

        self.assertEqual(["docker"], [item.key for item in values])
        self.assertEqual([True], [item.enabled for item in values])


class OverviewAsyncTests(IsolatedAsyncioTestCase):
    async def test_on_mount_orders_sections_extensions_extras_base(self) -> None:
        class _TestApp(App[None]):
            def compose(self) -> ComposeResult:
                yield Overview(
                    "codex",
                    "/test-tmp/project",
                    OverviewState(None, [], [], False),
                )

        app = _TestApp()

        async with app.run_test():
            sections = app.query_one("#sections", Horizontal)

            self.assertEqual(
                ["extensions", "extras", "base"],
                [child.id for child in sections.children],
            )

    async def test_on_button_pressed_posts_section_message(self) -> None:
        overview = Overview(
            "codex", "/test-tmp/project", OverviewState(None, [], [], False)
        )
        event = mock.Mock()
        event.button.id = "base"

        with mock.patch.object(overview, "post_message") as post_message_mock:
            overview.on_button_pressed(event)

        self.assertIsInstance(
            post_message_mock.call_args.args[0], Overview.EditSectionRequested
        )
