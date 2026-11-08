from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import Button, Header, SelectionList, Static

from .._models import BuiltInShareValue, DockerOptionValue, HostAccessConfirmValues
from .._mount_display import confirm_mount_list_items, mount_selection_rows
from ..services.host_access import (
    built_in_group_selection_values,
    current_built_in_shares,
)
from ._cancelable_screen import CancelableScreen


class HostAccessConfirmScreen(CancelableScreen[HostAccessConfirmValues | None]):
    def __init__(
        self,
        docker_options: list[DockerOptionValue],
        git_shares: list[BuiltInShareValue],
        extension_shares: list[BuiltInShareValue],
        credential_shares: list[BuiltInShareValue] | str | None = None,
        scope: str = "project",
    ) -> None:
        super().__init__()
        self._docker_options = docker_options
        self._git_shares = git_shares
        if isinstance(credential_shares, str):
            scope = credential_shares
            credential_shares = None
        self._credential_shares = credential_shares or []
        self._extension_shares = extension_shares
        self._scope = scope

    def compose(self) -> ComposeResult:
        docker_section = self._docker_section()
        git_section = self._git_section()
        credential_section = self._credential_section()
        extension_section = self._extension_section()
        yield Container(
            Container(
                Header(show_clock=False, classes="app_header"),
                Static("Confirm Host Access", classes="screen_title"),
                Static(
                    "Review and persist host access settings that expose sensitive resources.",
                    classes="screen_hint",
                ),
                *(docker_section if docker_section is not None else []),
                *(git_section if git_section is not None else []),
                *(credential_section if credential_section is not None else []),
                *(extension_section if extension_section is not None else []),
                Horizontal(
                    Button("Cancel", id="cancel", variant="default"),
                    Button("OK", id="ok", variant="primary"),
                    classes="screen_actions",
                ),
                classes="confirm_shell",
            ),
            classes="screen_frame",
        )

    def on_mount(self) -> None:
        self.query_one("#ok", Button).focus()
        self._clear_initial_highlight("#docker_confirm_list")
        self._clear_initial_highlight("#git_confirm_list")
        self._clear_initial_highlight("#credential_confirm_list")
        self._clear_initial_highlight("#extension_confirm_list")

    def action_accept(self) -> None:
        confirmed_docker_options: list[DockerOptionValue] = []
        if self._docker_options:
            selected = set(
                self.query_one("#docker_confirm_list", SelectionList).selected
            )
            for option in self._docker_options:
                confirmed_docker_options.append(
                    DockerOptionValue(
                        key=option.key,
                        label=option.label,
                        description=option.description,
                        persisted=option.persisted,
                        enabled=option.key in selected,
                    )
                )
        confirmed_git_shares = []
        if self._git_shares:
            confirmed_git_shares = current_built_in_shares(
                set(self.query_one("#git_confirm_list", SelectionList).selected),
                self._git_shares,
            )
        confirmed_credential_shares = []
        if self._credential_shares:
            confirmed_credential_shares = current_built_in_shares(
                set(self.query_one("#credential_confirm_list", SelectionList).selected),
                self._credential_shares,
            )
        confirmed_extension_shares = []
        if self._extension_shares:
            confirmed_extension_shares = current_built_in_shares(
                set(self.query_one("#extension_confirm_list", SelectionList).selected),
                self._extension_shares,
            )
        self.dismiss(
            HostAccessConfirmValues(
                docker_options=confirmed_docker_options,
                git_shares=confirmed_git_shares,
                credential_shares=confirmed_credential_shares,
                extension_shares=confirmed_extension_shares,
            )
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        if event.button.id == "ok":
            self.action_accept()
        elif event.button.id == "cancel":
            self.action_cancel()

    def on_selection_list_selection_toggled(
        self, event: SelectionList.SelectionToggled
    ) -> None:
        if event.selection_list.id != "extension_confirm_list":
            return
        selection_value = event.selection.value
        if not isinstance(selection_value, str):
            return
        related_values = built_in_group_selection_values(
            selection_value, self._extension_shares
        )
        if not related_values:
            return
        selected_values = set(event.selection_list.selected)
        if selection_value in selected_values:
            for related_value in related_values:
                event.selection_list.select(related_value)
            return
        for related_value in related_values:
            event.selection_list.deselect(related_value)

    def _docker_section(self) -> list[Static | Vertical] | None:
        if not self._docker_options:
            return None
        return [
            Static("Host integration", classes="screen_subtitle"),
            Static(
                "Persists container access to host services such as Docker.",
                classes="screen_hint confirm_hint",
            ),
            Vertical(
                self._docker_selection_list(),
                *self._docker_option_details(),
                classes="checkbox_group confirm_section",
            ),
        ]

    def _git_section(self) -> list[Static | Vertical] | None:
        if not self._git_shares:
            return None
        return [
            Static("Git", classes="screen_subtitle"),
            Static(
                self._git_hint(),
                classes="screen_hint confirm_hint",
            ),
            Vertical(
                self._git_selection_list(),
                classes="checkbox_group confirm_section",
            ),
        ]

    def _git_hint(self) -> str:
        if self._scope == "global":
            return "Persists Git settings for every project."
        if self._scope == "tree":
            return "Persists Git settings for this directory and its descendants."
        return "Bind mounts host files used by Git."

    def _credential_section(self) -> list[Static | Vertical] | None:
        if not self._credential_shares:
            return None
        return [
            Static("Credentials", classes="screen_subtitle"),
            Static(
                self._credential_hint(),
                classes="screen_hint confirm_hint",
            ),
            Vertical(
                self._credential_selection_list(),
                classes="checkbox_group confirm_section",
            ),
        ]

    def _credential_hint(self) -> str:
        if self._scope == "global":
            return "Persists SSH and GnuPG settings for every project."
        if self._scope == "tree":
            return "Persists SSH and GnuPG settings for this directory and its descendants."
        return "Lets the container use SSH and GnuPG keys without private-key mounts."

    def _extension_section(self) -> list[Static | Vertical] | None:
        if not self._extension_shares:
            return None
        return [
            Static("Extension bind mounts", classes="screen_subtitle"),
            Static(
                "Bind mounts declared by selected extensions.",
                classes="screen_hint confirm_hint",
            ),
            Vertical(
                self._extension_selection_list(),
                classes="checkbox_group confirm_section",
            ),
        ]

    def _docker_selection_list(self) -> SelectionList:
        return SelectionList(
            *[
                (
                    option.label,
                    option.key,
                    option.enabled,
                )
                for option in self._docker_options
            ],
            id="docker_confirm_list",
            compact=True,
        )

    def _docker_option_details(self) -> list[Static]:
        details: list[Static] = []
        for option in self._docker_options:
            if option.description is None:
                continue
            details.append(
                Static(
                    f"{option.label}: {option.description}",
                    classes="screen_hint confirm_hint",
                )
            )
        return details

    def _git_selection_list(self) -> SelectionList:
        return SelectionList(
            *mount_selection_rows(confirm_mount_list_items(self._git_shares)),
            id="git_confirm_list",
            compact=True,
        )

    def _credential_selection_list(self) -> SelectionList:
        return SelectionList(
            *mount_selection_rows(confirm_mount_list_items(self._credential_shares)),
            id="credential_confirm_list",
            compact=True,
        )

    def _extension_selection_list(self) -> SelectionList:
        return SelectionList(
            *mount_selection_rows(confirm_mount_list_items(self._extension_shares)),
            id="extension_confirm_list",
            compact=True,
        )

    def _clear_initial_highlight(self, selector: str) -> None:
        try:
            selection_list = self.query_one(selector, SelectionList)
        except NoMatches:
            return
        selection_list.highlighted = None
