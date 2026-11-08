from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from textual.containers import Horizontal, HorizontalGroup, Vertical, VerticalGroup
from textual.widgets import Button, SelectionList, Static
from textual.widgets.selection_list import Selection

from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    MOUNT_GNUPG_KEY,
    MOUNT_SSH_KEY,
)

from ..._ids import built_in_identity
from ..._models import BuiltInShareSource, BuiltInShareValue, CustomShareValue
from ..._mount_display import (
    credential_config_label,
    git_support_config_label,
    mount_selection_rows,
    overview_mount_list_items,
)
from ..._state import OverviewState
from ._selection_list import _OverviewSelectionList

_GIT_MOUNT_KEYS: tuple[str, ...] = (MOUNT_GITCONFIG_KEY, MOUNT_GITROOT_KEY)
_CREDENTIAL_MOUNT_KEYS: tuple[str, ...] = (MOUNT_SSH_KEY, MOUNT_GNUPG_KEY)
_GIT_BUTTON_PREFIX = "git_mount_"
_CREDENTIAL_BUTTON_PREFIX = "credential_mount_"


@dataclass(frozen=True)
class _MountSection:
    title: str
    keys: tuple[str, ...]
    values: dict[str, bool | None]
    button_id: Callable[[str], str]
    label: Callable[[str], str]
    section_id: str


def share_widgets(
    state: OverviewState,
    include_host_access: bool = False,
) -> list[Horizontal | SelectionList | VerticalGroup]:
    return [
        Horizontal(
            Static("Bind Mounts", id="shares_overview_title"),
            Button("+", id="add_share", variant="default"),
            id="shares_overview_header",
        ),
        *(_host_access_widgets(state) if include_host_access else []),
        _OverviewSelectionList(
            *_share_selection_items(state.built_in_shares, state.custom_shares),
            id="shares_overview_list",
            compact=True,
        ),
    ]


def refresh_shares(
    container: Any,
    state: OverviewState,
    include_host_access: bool = False,
) -> None:
    overview = container.query_one("#shares_overview", Vertical)
    if (
        not state.built_in_shares
        and not state.custom_shares
        and not include_host_access
    ):
        overview.display = False
        return
    overview.display = True
    container.query_one("#shares_overview_title", Static).update("Bind Mounts")
    selection_list = container.query_one("#shares_overview_list", SelectionList)
    selection_list.clear_options()
    selection_list.add_options(
        _share_selection_items(state.built_in_shares, state.custom_shares)
    )
    if include_host_access:
        for key in _GIT_MOUNT_KEYS:
            container.query_one(f"#{_git_button_id(key)}", Button).label = (
                _mount_value_label(state.git_values.get(key))
            )
        for key in _CREDENTIAL_MOUNT_KEYS:
            container.query_one(f"#{_credential_button_id(key)}", Button).label = (
                _mount_value_label(state.credential_values.get(key))
            )


def merge_built_in_shares(
    fresh_items: list[BuiltInShareValue],
    current_items: list[BuiltInShareValue],
) -> list[BuiltInShareValue]:
    current_by_identity = {
        built_in_identity(item.source, item.key): item for item in current_items
    }
    return [
        BuiltInShareValue(
            source=item.source,
            key=item.key,
            label=item.label,
            path=item.path,
            persisted=_persisted_value(item, current_by_identity),
            enabled=_enabled_value(item, current_by_identity),
            row_key=item.row_key,
            inherited=item.inherited,
        )
        for item in fresh_items
    ]


def _persisted_value(
    item: BuiltInShareValue,
    current_by_identity: dict[str, BuiltInShareValue],
) -> bool | None:
    current = current_by_identity.get(built_in_identity(item.source, item.key))
    if current is not None and current.persisted is None:
        return None
    return item.persisted


def _enabled_value(
    item: BuiltInShareValue,
    current_by_identity: dict[str, BuiltInShareValue],
) -> bool:
    current = current_by_identity.get(built_in_identity(item.source, item.key))
    return current.enabled if current is not None else item.enabled


def current_custom_shares(state: OverviewState) -> list[CustomShareValue]:
    return list(state.custom_shares)


def host_access_button_key(
    button_id: str | None,
) -> tuple[BuiltInShareSource, str] | None:
    if button_id is None:
        return None
    if button_id.startswith(_GIT_BUTTON_PREFIX):
        return BuiltInShareSource.GIT_SUPPORT, button_id.removeprefix(
            _GIT_BUTTON_PREFIX
        )
    if button_id.startswith(_CREDENTIAL_BUTTON_PREFIX):
        return BuiltInShareSource.CREDENTIALS, button_id.removeprefix(
            _CREDENTIAL_BUTTON_PREFIX
        )
    return None


def next_mount_value(value: bool | None) -> bool | None:
    if value is None:
        return True
    if value:
        return False
    return None


def _host_access_widgets(state: OverviewState) -> list[VerticalGroup]:
    return [
        _mount_widgets(
            _MountSection(
                "Git",
                _GIT_MOUNT_KEYS,
                state.git_values,
                _git_button_id,
                git_support_config_label,
                "git_support",
            )
        ),
        _mount_widgets(
            _MountSection(
                "Credentials",
                _CREDENTIAL_MOUNT_KEYS,
                state.credential_values,
                _credential_button_id,
                credential_config_label,
                "credentials",
            )
        ),
    ]


def _mount_widgets(section: _MountSection) -> VerticalGroup:
    return VerticalGroup(
        Static(section.title, classes="host_access_title"),
        VerticalGroup(
            *[
                HorizontalGroup(
                    Button(
                        _mount_value_label(section.values.get(key)),
                        id=section.button_id(key),
                        classes="host_access_control",
                    ),
                    Static(section.label(key), classes="host_access_label"),
                    classes="host_access_row",
                )
                for key in section.keys
            ],
            id=f"{section.section_id}_overview",
        ),
    )


def _git_button_id(key: str) -> str:
    return f"{_GIT_BUTTON_PREFIX}{key}"


def _credential_button_id(key: str) -> str:
    return f"{_CREDENTIAL_BUTTON_PREFIX}{key}"


def _mount_value_label(value: bool | None) -> str:
    if value is None:
        return "Auto"
    if value:
        return "On\u00a0\u00a0"
    return "Off\u00a0"


def _share_selection_items(
    built_in_shares: list[BuiltInShareValue],
    custom_shares: list[CustomShareValue],
) -> list[Selection[str] | tuple[str, str, bool]]:
    return mount_selection_rows(
        overview_mount_list_items(built_in_shares, custom_shares)
    )
