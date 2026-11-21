from dataclasses import replace
from typing import TypeVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen

from aicage.config.context import ConfigContext
from aicage.config.extensions.order import canonical_extensions
from aicage.config.overview_selection import resolve_overview_selection
from aicage.config.project_config import (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    MOUNT_GNUPG_KEY,
    MOUNT_SSH_KEY,
    AgentConfig,
)
from aicage.config.run_config_draft import RunConfigDraft
from aicage.registry.image_selection.interaction import ExtensionChoiceOption
from aicage.runtime.docker_args.mount_preferences import disable_git_mounts
from aicage.runtime.docker_args.support.git_support import detected_git_mounts
from aicage.runtime.menu._interaction_types import ConfigSelectionResult
from aicage.runtime.menu.scope_change import ConfigScopeChange

from ._ids import ROW_BASE, ROW_EXTENSIONS, ROW_EXTRAS
from ._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
    HostAccessConfirmValues,
)
from ._mount_display import git_support_config_label
from ._state import OverviewState
from ._textual_app import TextualApp
from .services.base_support import base_metadata_for_draft, ensure_base_default
from .services.custom_share_flow import add_custom_share, update_custom_share
from .services.host_access import apply_host_access
from .services.host_access_flow import confirm_and_apply_host_access
from .services.summary import extras_values, shares_values
from .views.base_screen import BaseScreen
from .views.docker_args_screen import DockerArgsScreen
from .views.extensions_screen import ExtensionsScreen
from .views.host_access_confirm_screen import HostAccessConfirmScreen
from .views.overview.view import Overview
from .views.scope_change_confirm_screen import ScopeChangeConfirmScreen
from .views.share_editor_screen import ShareEditorScreen

_ScreenResultT = TypeVar("_ScreenResultT")
_GIT_MOUNT_KEYS: tuple[str, ...] = (
    MOUNT_GITCONFIG_KEY,
    MOUNT_GITROOT_KEY,
    MOUNT_GNUPG_KEY,
    MOUNT_SSH_KEY,
)


class ConfigApp(TextualApp[ConfigSelectionResult | ConfigScopeChange | None]):
    BINDINGS = [
        Binding("enter", "accept", "OK"),
        Binding("escape", "cancel", "Cancel"),
        *TextualApp.BINDINGS,
    ]

    def __init__(self, draft: RunConfigDraft, context: ConfigContext) -> None:
        super().__init__(draft.scope_title)
        self._draft = draft
        self._config_context = context
        self._apply_git_cli_preference()
        self._mark_new_config_auto_git_mounts_pending()
        self._state = self._initial_state()

    def compose(self) -> ComposeResult:
        yield Overview(
            self._draft.agent,
            self._draft.project_cfg.path,
            self._state,
            self._draft.scope_title,
            self._draft.scope,
        )

    def on_mount(self) -> None:
        ensure_base_default(self._draft, self._config_context)
        self._apply_shell_width()
        self._refresh_sections()
        overview = self._overview()
        overview.refresh_scope(self._draft.scope)
        overview.focus_default()

    def action_accept(self) -> None:
        self._accept()

    def action_cancel(self) -> None:
        self._finish(None)

    @work(exclusive=True)
    async def _accept(self) -> None:
        accepted = await self._confirm_undecided_built_in_shares()
        if not accepted:
            return
        self._finish(
            ConfigSelectionResult(
                selection=resolve_overview_selection(
                    self._draft,
                    self._config_context,
                ),
                project_docker_args=self._draft.effective_agent_cfg.docker_args,
            )
        )

    @work(exclusive=True)
    async def _edit_section(self, section_id: str) -> None:
        self._state.last_section_id = section_id
        if section_id == ROW_BASE:
            await self._edit_base()
        elif section_id == ROW_EXTENSIONS:
            await self._edit_extensions()
        elif section_id == ROW_EXTRAS:
            await self._edit_extras()
        self._refresh_sections()

    def on_overview_accept_requested(self, _: Overview.AcceptRequested) -> None:
        self.action_accept()

    def on_overview_cancel_requested(self, _: Overview.CancelRequested) -> None:
        self.action_cancel()

    def on_overview_add_share_requested(self, _: Overview.AddShareRequested) -> None:
        self._add_share()

    def on_overview_edit_section_requested(
        self, message: Overview.EditSectionRequested
    ) -> None:
        self._edit_section(message.section_id)

    def on_overview_edit_custom_share_requested(
        self, message: Overview.EditCustomShareRequested
    ) -> None:
        self._edit_custom_share(message.current_value)

    def on_overview_scope_change_requested(
        self, message: Overview.ScopeChangeRequested
    ) -> None:
        self._change_scope(message.scope)

    def on_overview_git_support_changed(
        self, message: Overview.GitSupportChanged
    ) -> None:
        previous_value = getattr(self._draft.effective_agent_cfg.mounts, message.key)
        setattr(self._draft.agent_cfg.mounts, message.key, message.value)
        if message.value is not False and (
            message.value is None or previous_value is not True
        ):
            self._draft.pending_git_mounts.add(message.key)
        else:
            self._draft.pending_git_mounts.discard(message.key)

    async def _edit_base(self) -> None:
        selected = await self._push_view(
            BaseScreen(
                base_metadata_for_draft(self._draft, self._config_context),
                self._draft.agent_cfg.base or "",
            )
        )
        if selected is not None and selected != self._draft.agent_cfg.base:
            self._draft.agent_cfg.base = selected
            self._draft.reset_extension_image()

    @work(exclusive=True)
    async def _change_scope(self, scope: str) -> None:
        if scope == self._draft.scope:
            return
        if self._draft.scope_config_exists.get(scope, False):
            accepted = await self._push_view(
                ScopeChangeConfirmScreen(_scope_label(scope))
            )
            if accepted is not True:
                self._overview().refresh_scope(self._draft.scope)
                return
        self._apply_current_host_access()
        self._finish(ConfigScopeChange(scope))

    async def _edit_extensions(self) -> None:
        selected = await self._push_view(
            ExtensionsScreen(
                [
                    ExtensionChoiceOption(
                        name=extension.extension_id,
                        description=f"{extension.name} - {extension.description}",
                        has_dockerfile=extension.dockerfile_path is not None,
                    )
                    for extension in canonical_extensions(
                        list(self._config_context.extensions.values())
                    )
                ],
                list(self._draft.agent_cfg.extensions),
                list(
                    self._draft.inherited_project_cfg.agents.get(
                        self._draft.agent, AgentConfig()
                    ).extensions
                ),
            )
        )
        if selected is not None and selected != self._draft.agent_cfg.extensions:
            self._draft.agent_cfg.extensions = selected
            self._draft.reset_extension_image()

    async def _edit_extras(self) -> None:
        selected = await self._push_view(DockerArgsScreen(extras_values(self._draft)))
        if selected is None:
            return
        self._draft.agent_cfg.docker_args = selected.docker_args

    @work(exclusive=True)
    async def _add_share(self) -> None:
        result = await self._push_view(ShareEditorScreen())
        if result is None or result.share is None:
            return
        if not add_custom_share(self._state, self._draft, result.share):
            return
        self._apply_shell_width()
        self._refresh_sections()

    @work(exclusive=True)
    async def _edit_custom_share(self, current_value: str) -> None:
        result = await self._push_view(
            ShareEditorScreen(current_value, allow_remove=True)
        )
        if result is None:
            return
        if not update_custom_share(
            self._state,
            self._draft,
            current_value,
            result,
        ):
            return
        self._apply_shell_width()
        self._refresh_sections()

    async def _push_view(self, screen: Screen[_ScreenResultT]) -> _ScreenResultT:
        overview = self._overview()
        overview.hide_shell()
        try:
            return await self.push_screen_wait(screen)
        finally:
            overview.show_shell()
            overview.refresh_scope(self._draft.scope)
            self._focus_last_section()

    def _finish(self, result: ConfigSelectionResult | ConfigScopeChange | None) -> None:
        self.exit(result)

    def _focus_last_section(self) -> None:
        if self._state.last_section_id is None:
            self._overview().focus_default()
            return
        self._overview().focus_section(self._state.last_section_id)

    def _apply_shell_width(self) -> None:
        self._overview().apply_shell_width(self.size.width)

    def _refresh_sections(self) -> None:
        self._overview().refresh_from(self._draft, self._config_context)

    async def _confirm_undecided_built_in_shares(self) -> bool:
        overview = self._overview()
        self._state.custom_shares = overview.current_custom_shares()
        pending_auto_git_mounts = {
            key
            for key in self._draft.pending_git_mounts
            if getattr(self._draft.agent_cfg.mounts, key) is None
        }
        accepted, built_in_shares = await confirm_and_apply_host_access(
            self._draft,
            self._current_built_in_shares(overview),
            self._state.custom_shares,
            overview.current_host_options(
                self._docker_socket_value_for_confirmation(),
                self._draft.agent_cfg.mounts.docker is None
                and self._draft.inherited_project_cfg.agents.get(self._draft.agent)
                is not None
                and self._draft.inherited_project_cfg.agents[
                    self._draft.agent
                ].mounts.docker
                is True,
            ),
            self._confirm_host_access,
        )
        self._restore_confirmed_auto_git_mounts(
            pending_auto_git_mounts, built_in_shares
        )
        self._state.built_in_shares = [
            item for item in built_in_shares if item.path is not None
        ]
        return accepted

    def _restore_confirmed_auto_git_mounts(
        self,
        pending_auto_git_mounts: set[str],
        built_in_shares: list[BuiltInShareValue],
    ) -> None:
        for item in built_in_shares:
            if item.key in pending_auto_git_mounts and item.enabled:
                setattr(self._draft.agent_cfg.mounts, item.key, None)

    def _apply_current_host_access(self) -> None:
        overview = self._overview()
        self._state.custom_shares = overview.current_custom_shares()
        current_built_in_shares = self._current_built_in_shares(overview)
        pending_git_mounts = {
            item.key
            for item in current_built_in_shares
            if item.source is BuiltInShareSource.GIT_SUPPORT
            and item.enabled
            and item.persisted is not True
        }
        if self._uses_git_support_screen():
            self._draft.pending_git_mounts.update(pending_git_mounts)
        else:
            self._draft.pending_git_mounts = pending_git_mounts
        self._draft.pending_extension_mounts = {
            item.key
            for item in current_built_in_shares
            if item.source is BuiltInShareSource.EXTENSION
            and item.enabled
            and item.persisted is not True
        }
        self._draft.pending_docker_socket = any(
            option.enabled and option.persisted is not True
            for option in overview.current_host_options(
                self._docker_socket_value_for_confirmation(),
                self._state.docker_socket_inherited,
            )
        )
        apply_host_access(
            self._draft,
            current_built_in_shares,
            self._state.custom_shares,
            overview.current_host_options(
                self._docker_socket_value_for_confirmation(),
                self._state.docker_socket_inherited,
            ),
        )

    def _overview(self) -> Overview:
        return self.query_one(Overview)

    async def _confirm_host_access(
        self,
        values: HostAccessConfirmValues,
    ) -> HostAccessConfirmValues | None:
        return await self._push_view(
            HostAccessConfirmScreen(
                values.docker_options,
                values.git_support_shares,
                values.extension_shares,
                self._draft.scope,
            )
        )

    def _initial_state(self) -> OverviewState:
        built_in_shares = self._built_in_shares()
        if self._draft.parsed is not None and self._draft.parsed.git:
            detected_mounts = detected_git_mounts(self._draft.project_path)
            built_in_shares = [
                (
                    replace(item, enabled=True)
                    if item.source is BuiltInShareSource.GIT_SUPPORT
                    and item.key in detected_mounts
                    else item
                )
                for item in built_in_shares
            ]
        return OverviewState(
            last_section_id=None,
            built_in_shares=built_in_shares,
            custom_shares=[
                CustomShareValue(share, inherited=True)
                for share in self._draft.inherited_project_cfg.agents.get(
                    self._draft.agent, AgentConfig()
                ).shares
            ]
            + [CustomShareValue(share) for share in self._draft.agent_cfg.shares],
            docker_socket_enabled=bool(self._draft.effective_agent_cfg.mounts.docker),
            docker_socket_inherited=(
                self._draft.agent_cfg.mounts.docker is None
                and self._draft.inherited_project_cfg.agents.get(self._draft.agent)
                is not None
                and self._draft.inherited_project_cfg.agents[
                    self._draft.agent
                ].mounts.docker
                is True
            ),
            git_support_values=(
                self._git_support_values() if self._uses_git_support_screen() else {}
            ),
        )

    def _built_in_shares(self) -> list[BuiltInShareValue]:
        return [
            (
                replace(item, persisted=None)
                if (
                    item.source is BuiltInShareSource.GIT_SUPPORT
                    and item.key in self._draft.pending_git_mounts
                )
                or (
                    item.source is BuiltInShareSource.EXTENSION
                    and item.key in self._draft.pending_extension_mounts
                )
                else item
            )
            for item in shares_values(self._draft, self._config_context).built_in_shares
            if not (
                self._uses_git_support_screen()
                and item.source is BuiltInShareSource.GIT_SUPPORT
            )
        ]

    def _current_built_in_shares(self, overview: Overview) -> list[BuiltInShareValue]:
        return [
            *overview.current_built_in_shares(),
            *self._pending_git_support_shares(),
        ]

    def _pending_git_support_shares(self) -> list[BuiltInShareValue]:
        return [
            BuiltInShareValue(
                source=BuiltInShareSource.GIT_SUPPORT,
                key=key,
                label=(
                    f"(Auto) {git_support_config_label(key)}"
                    if getattr(self._draft.agent_cfg.mounts, key) is None
                    else git_support_config_label(key)
                ),
                path=None,
                persisted=None,
                enabled=True,
            )
            for key in _GIT_MOUNT_KEYS
            if key in self._draft.pending_git_mounts
            and getattr(self._draft.agent_cfg.mounts, key) is not False
        ]

    def _git_support_values(self) -> dict[str, bool | None]:
        return {
            key: getattr(self._draft.agent_cfg.mounts, key) for key in _GIT_MOUNT_KEYS
        }

    def _apply_git_cli_preference(self) -> None:
        if self._draft.parsed is None or self._draft.parsed.git is None:
            return
        if self._draft.parsed.git is False:
            disable_git_mounts(self._draft.agent_cfg)
            return
        if not self._uses_git_support_screen():
            return
        for key in detected_git_mounts(self._draft.project_path):
            if getattr(self._draft.agent_cfg.mounts, key) is None:
                setattr(self._draft.agent_cfg.mounts, key, True)
                self._draft.pending_git_mounts.add(key)

    def _mark_new_config_auto_git_mounts_pending(self) -> None:
        if not self._uses_git_support_screen() or self._draft.scope_config_exists.get(
            self._draft.scope, True
        ):
            return
        self._draft.pending_git_mounts.update(
            key
            for key in _GIT_MOUNT_KEYS
            if getattr(self._draft.agent_cfg.mounts, key) is None
        )

    def _uses_git_support_screen(self) -> bool:
        return self._draft.scope in {"global", "tree"}

    def _docker_socket_value_for_confirmation(self) -> bool | None:
        if self._draft.pending_docker_socket:
            return None
        return self._draft.effective_agent_cfg.mounts.docker


def _scope_label(scope: str) -> str:
    if scope == "global":
        return "global"
    if scope == "tree":
        return "directory tree"
    return "project"
