from rich.text import Text
from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.message import Message
from textual.widgets import Button, Header, SelectionList, Static
from textual.widgets.selection_list import Selection

from aicage.config.context import ConfigContext
from aicage.config.run_config_draft import RunConfigDraft

from ..._ids import (
    ROW_BASE,
    ROW_EXTENSIONS,
    ROW_EXTRAS,
    SECTION_IDS,
    docker_selection_key,
)
from ..._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
    DockerOptionValue,
)
from ..._state import OverviewState
from ...services.host_access import (
    built_in_group_selection_values,
    current_built_in_shares,
    current_docker_option,
)
from ...services.summary import (
    extensions_summary,
    extras_summary,
    extras_values,
    shares_values,
)
from ._layout import shell_width
from ._selection_list import _OverviewSelectionList
from ._shares import (
    current_custom_shares,
    git_support_key,
    is_git_support_button,
    merge_built_in_shares,
    next_git_support_value,
    refresh_shares,
    share_widgets,
)


class Overview(Container):
    _CONTEXT_LABEL_WIDTH = 8
    _GLOBAL_SCOPE_TITLE = "global configuration"
    _TREE_SCOPE_TITLE = "directory tree configuration"

    class AcceptRequested(Message):
        pass

    class CancelRequested(Message):
        pass

    class AddShareRequested(Message):
        pass

    class EditSectionRequested(Message):
        def __init__(self, section_id: str) -> None:
            self.section_id = section_id
            super().__init__()

    class EditCustomShareRequested(Message):
        def __init__(self, current_value: str) -> None:
            self.current_value = current_value
            super().__init__()

    class ScopeChangeRequested(Message):
        def __init__(self, scope: str) -> None:
            self.scope = scope
            super().__init__()

    class GitSupportChanged(Message):
        def __init__(self, key: str, value: bool | None) -> None:
            self.key = key
            self.value = value
            super().__init__()

    def __init__(
        self,
        agent: str,
        project_path: str,
        state: OverviewState,
        scope_title: str = "container config",
        scope: str = "project",
    ) -> None:
        super().__init__(id="overview_root")
        self._agent = agent
        self._project_path = project_path
        self._state = state
        self._scope_title = scope_title
        self._scope = scope

    def compose(self) -> ComposeResult:
        scope_banner = self._scope_banner()
        yield Container(
            Container(
                Header(show_clock=False, classes="app_header"),
                *([scope_banner] if scope_banner is not None else []),
                Static(self._context_line("Agent:", self._agent), id="title"),
                Static(
                    self._context_line("Project:", self._project_path), id="context"
                ),
                Static("Configuration Scope", id="scope_title"),
                SelectionList(
                    id="scope_overview_list",
                    compact=True,
                ),
                Horizontal(
                    Button(id=ROW_EXTENSIONS, classes="section"),
                    Button(id=ROW_EXTRAS, classes="section"),
                    Button(id=ROW_BASE, classes="section"),
                    id="sections",
                ),
                Vertical(
                    Vertical(
                        *share_widgets(
                            self._state,
                            self._scope in {"global", "tree"},
                        ),
                        id="shares_overview",
                    ),
                    Vertical(*self._docker_widgets(), id="docker_overview"),
                    id="access_overview",
                ),
                Horizontal(
                    Button("Cancel", id="cancel", variant="default"),
                    Button("OK", id="ok", variant="primary"),
                    id="actions",
                ),
                id="shell",
            ),
            id="overview_frame",
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if is_git_support_button(event.button.id):
            self._change_git_support(event.button)
            return
        if event.button.id == "ok":
            self.post_message(self.AcceptRequested())
        elif event.button.id == "cancel":
            self.post_message(self.CancelRequested())
        elif event.button.id == "add_share":
            self.post_message(self.AddShareRequested())
        elif event.button.id in SECTION_IDS:
            self.post_message(self.EditSectionRequested(event.button.id))

    def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged
    ) -> None:
        if event.selection_list.id == "shares_overview_list":
            self._state.built_in_shares = current_built_in_shares(
                set(event.selection_list.selected),
                self._state.built_in_shares,
            )
            return
        if event.selection_list.id == "docker_overview_list":
            self._state.docker_socket_enabled = (
                docker_selection_key("socket") in event.selection_list.selected
            )
            self.apply_shell_width(self.size.width)

    def on_selection_list_selection_toggled(
        self, event: SelectionList.SelectionToggled
    ) -> None:
        if event.selection_list.id == "scope_overview_list":
            selection_value = event.selection.value
            if not isinstance(selection_value, str):
                return
            scope = (
                selection_value
                if selection_value in event.selection_list.selected
                else "project"
            )
            self.post_message(self.ScopeChangeRequested(scope))
            return
        if event.selection_list.id != "shares_overview_list":
            return
        selection_value = event.selection.value
        if not isinstance(selection_value, str) or not selection_value.startswith(
            "custom:"
        ):
            if isinstance(selection_value, str):
                self._sync_built_in_share_group_selection(
                    event.selection_list, selection_value
                )
            return
        if any(
            share.value == selection_value.removeprefix("custom:") and share.inherited
            for share in self._state.custom_shares
        ):
            event.selection_list.select(selection_value)
            return
        event.selection_list.select(selection_value)
        self.post_message(
            self.EditCustomShareRequested(selection_value.removeprefix("custom:"))
        )

    def refresh_from(self, draft: RunConfigDraft, context: ConfigContext) -> None:
        effective_agent_cfg = draft.effective_agent_cfg
        built_in_shares = shares_values(draft, context).built_in_shares
        if self._scope in {"global", "tree"}:
            built_in_shares = [
                item
                for item in built_in_shares
                if item.source is not BuiltInShareSource.GIT_SUPPORT
            ]
        self._state.built_in_shares = merge_built_in_shares(
            built_in_shares,
            self._state.built_in_shares,
        )
        self.apply_shell_width(self.size.width)
        self._section_button(ROW_BASE).label = self._section_label(
            "Base", effective_agent_cfg.base or ""
        )
        self._section_button(ROW_EXTENSIONS).label = self._section_label(
            "Extensions",
            extensions_summary(effective_agent_cfg.extensions),
        )
        self._section_button(ROW_EXTRAS).label = self._section_label(
            "Docker Args",
            extras_summary(extras_values(draft)),
        )
        refresh_shares(self, self._state, self._scope in {"global", "tree"})
        self._refresh_docker()

    def apply_shell_width(self, viewport_width: int) -> None:
        width = shell_width(
            self._state.built_in_shares, self._state.custom_shares, viewport_width
        )
        shell = self.query_one("#shell", Container)
        shell.styles.width = width
        shell.styles.min_width = width
        shell.styles.max_width = width
        shell.refresh(layout=True)

    def focus_default(self) -> None:
        self.query_one("#ok", Button).focus()

    def focus_section(self, section_id: str) -> None:
        self._section_button(section_id).focus()

    def hide_shell(self) -> None:
        self.query_one("#shell", Container).display = False

    def show_shell(self) -> None:
        self.query_one("#shell", Container).display = True

    def current_built_in_shares(self) -> list[BuiltInShareValue]:
        return current_built_in_shares(
            set(self.query_one("#shares_overview_list", SelectionList).selected),
            self._state.built_in_shares,
        )

    def current_custom_shares(self) -> list[CustomShareValue]:
        return current_custom_shares(self._state)

    def current_host_options(
        self,
        docker_socket_value: bool | None,
        docker_socket_inherited: bool = False,
    ) -> list[DockerOptionValue]:
        selected = set(self.query_one("#docker_overview_list", SelectionList).selected)
        return [
            current_docker_option(
                selected, docker_socket_value, docker_socket_inherited
            )
        ]

    def refresh_scope(self, scope: str) -> None:
        self._scope = scope
        selection_list = self.query_one("#scope_overview_list", SelectionList)
        selection_list.clear_options()
        selection_list.add_options(
            [
                Selection("Global", "global", scope == "global"),
                Selection("Directory tree", "tree", scope == "tree"),
            ]
        )

    def _section_button(self, section_id: str) -> Button:
        return self.query_one(f"#{section_id}", Button)

    def _scope_banner(self) -> Static | None:
        if self._scope_title == self._GLOBAL_SCOPE_TITLE:
            return Static(
                "GLOBAL CONFIGURATION\nChanges apply to every project.",
                classes="scope_banner",
            )
        if self._scope_title == self._TREE_SCOPE_TITLE:
            return Static(
                "DIRECTORY TREE CONFIGURATION\n"
                "Changes apply to this directory and all descendant directories/projects.",
                classes="scope_banner",
            )
        return None

    def _sync_built_in_share_group_selection(
        self, selection_list: SelectionList, selection_value: str
    ) -> None:
        related_values = built_in_group_selection_values(
            selection_value, self._state.built_in_shares
        )
        if not related_values:
            return
        selected_values = set(selection_list.selected)
        if selection_value in selected_values:
            for related_value in related_values:
                selection_list.select(related_value)
            return
        for related_value in related_values:
            selection_list.deselect(related_value)

    def _change_git_support(self, button: Button) -> None:
        if button.id is None:
            return
        key = git_support_key(button.id)
        value = next_git_support_value(self._state.git_support_values.get(key))
        self._state.git_support_values[key] = value
        button.label = (
            "Auto" if value is None else "On\u00a0\u00a0" if value else "Off\u00a0"
        )
        self.post_message(self.GitSupportChanged(key, value))

    def _docker_widgets(self) -> list[Static | SelectionList]:
        selections = [
            Selection(
                "Docker socket",
                docker_selection_key("socket"),
                self._state.docker_socket_enabled,
                disabled=self._state.docker_socket_inherited,
            )
        ]
        return [
            Static("Host Integration", id="docker_overview_title"),
            _OverviewSelectionList(
                *selections,
                id="docker_overview_list",
                compact=True,
            ),
        ]

    def _refresh_docker(self) -> None:
        self.query_one("#docker_overview_title", Static).update("Host Integration")
        selection_list = self.query_one("#docker_overview_list", SelectionList)
        selection_list.clear_options()
        options = [
            Selection(
                "Docker socket",
                docker_selection_key("socket"),
                self._state.docker_socket_enabled,
                disabled=self._state.docker_socket_inherited,
            )
        ]
        selection_list.add_options(options)

    def _section_label(self, title: str, summary: str) -> Text:
        return Text.assemble(
            (title, "bold"),
            "\n",
            (self._truncate_summary(summary), "dim not bold"),
        )

    @classmethod
    def _context_line(cls, label: str, value: str) -> str:
        return f"{label:<{cls._CONTEXT_LABEL_WIDTH}} {value}"

    @staticmethod
    def _truncate_summary(summary: str, limit: int = 34) -> str:
        if len(summary) <= limit:
            return summary
        return f"{summary[: limit - 1]}..."
