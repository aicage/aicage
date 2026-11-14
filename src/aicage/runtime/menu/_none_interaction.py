from aicage.cli_types import ConfigUpdateArgs
from aicage.config.context import ConfigContext
from aicage.config.run_config import RunConfig
from aicage.config.run_config_draft import RunConfigDraft
from aicage.registry.ensure_image import ensure_image
from aicage.registry.image_selection.interaction import (
    BaseChoiceRequest,
    ExtensionChoiceOption,
)
from aicage.registry.image_selection.selection import select_agent_image
from aicage.reporting import OperationReporter
from aicage.runtime.docker_args.mount_preferences import (
    apply_extension_mount_defaults,
    apply_git_mount_defaults,
    apply_mount_preferences,
    disable_git_mounts,
)
from aicage.runtime.menu._interaction_types import ConfigSelectionResult


class _NoneInteraction:
    def __init__(self, reporter: OperationReporter) -> None:
        self.reporter = reporter

    def configure_run(
        self,
        draft: RunConfigDraft,
        context: ConfigContext,
        agent: str,
    ) -> ConfigSelectionResult:
        draft.apply_cli_base()
        draft.apply_cli_extensions()
        configured_extensions = context.project_cfg.agents.get(agent)
        selected_extensions = (
            draft.parsed.extensions
            if draft.parsed is not None and draft.parsed.extensions
            else (
                list(configured_extensions.extensions)
                if configured_extensions is not None
                else []
            )
        )
        selection = select_agent_image(
            agent,
            context,
            _NonInteractiveSelectionInteraction(selected_extensions),
        )
        draft.apply_selection(selection)
        draft.merge_shares()
        if draft.parsed is not None and draft.parsed.git is not None:
            if draft.parsed.git:
                apply_git_mount_defaults(context, draft.agent_cfg)
            else:
                disable_git_mounts(draft.agent_cfg)
        if isinstance(draft.parsed, ConfigUpdateArgs):
            apply_extension_mount_defaults(context, draft.agent_cfg)
        else:
            apply_mount_preferences(
                context,
                agent,
                draft.parsed,
                _select_all_mounts,
                _always_confirm,
            )
        return ConfigSelectionResult(
            selection=selection,
            project_docker_args=draft.existing_project_docker_args,
        )

    def confirm_aicage_update(
        self,
        installed_version: str,
        latest_version: str,
    ) -> bool:
        del installed_version, latest_version
        return True

    def confirm_image_update(self, image_ref: str) -> bool:
        del image_ref
        return True

    def execute_image_setup(
        self,
        run_config: RunConfig,
        update_approved: bool,
    ) -> None:
        ensure_image(
            run_config,
            update_approved=update_approved,
            reporter=self.reporter,
        )


class _NonInteractiveSelectionInteraction:
    def __init__(self, extensions: list[str] | None = None) -> None:
        self._extensions = extensions or []

    def choose_base(self, request: BaseChoiceRequest) -> str:
        return request.default_base

    def choose_extensions(
        self,
        options: list[ExtensionChoiceOption],
    ) -> list[str]:
        del options
        return list(self._extensions)

    def choose_image_ref(self, default_ref: str) -> str:
        return default_ref


def _always_confirm(*args: object) -> bool:
    del args
    return True


def _select_all_mounts(
    git_items: list[tuple[str, str]],
    extension_items: list[tuple[str, str]],
) -> list[str]:
    return [item[0] for item in [*git_items, *extension_items]]
