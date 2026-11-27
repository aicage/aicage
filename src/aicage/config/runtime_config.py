from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path

from aicage._logging import get_logger
from aicage.cli_types import ParsedArgs
from aicage.config._inheritance import (
    load_effective_project_config,
    merge_project_configs,
    rebase_agent_config,
)
from aicage.config.agent.loader import load_agents
from aicage.config.agent.models import AgentMetadata
from aicage.config.base.loader import load_bases
from aicage.config.base.models import BaseMetadata
from aicage.config.config_store import SettingsStore
from aicage.config.context import ConfigContext
from aicage.config.extensions.loader import ExtensionMetadata, load_extensions
from aicage.config.image_refs import default_extended_image_ref
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.config.run_config import RunConfig
from aicage.config.run_config_draft import RunConfigDraft, _create_run_config_draft
from aicage.registry.errors import RegistryError
from aicage.runtime.docker_args.resolve.resolver import resolve_docker_args
from aicage.runtime.menu.interaction import RuntimeInteraction
from aicage.runtime.menu.scope_change import ConfigScopeChange


@dataclass(frozen=True)
class _ConfigScopeContext:
    store: SettingsStore
    directory_path: Path
    agent: str
    interaction: RuntimeInteraction
    bases: dict[str, BaseMetadata]
    agents: dict[str, AgentMetadata]
    extensions: dict[str, ExtensionMetadata]


def load_run_config(
    agent: str,
    interaction: RuntimeInteraction,
    parsed: ParsedArgs | None = None,
) -> RunConfig | None:
    store = SettingsStore()
    project_path = Path.cwd().resolve()
    bases = load_bases()
    agents = load_agents(bases)
    _require_known_agent(agent, agents)
    local_project_cfg = store.load_project(project_path)
    inherited_project_cfg = load_effective_project_config(
        store, project_path, _ProjectConfig(path=str(project_path))
    )
    draft = _create_run_config_draft(
        project_path, agent, local_project_cfg, parsed, inherited_project_cfg
    )
    draft.scope_config_exists = _scope_config_exists(store, project_path, agent)
    extensions = load_extensions()
    _remove_missing_extensions(agent, draft.project_cfg, extensions)
    context = ConfigContext(
        store=store,
        project_cfg=load_effective_project_config(
            store, project_path, local_project_cfg
        ),
        agents=agents,
        bases=bases,
        extensions=extensions,
    )
    _remove_missing_extensions(agent, context.project_cfg, context.extensions)
    initial_effective_agent_cfg = deepcopy(
        context.project_cfg.agents.get(agent, AgentConfig())
    )
    result = interaction.configure_run(draft, context, agent)
    if isinstance(result, ConfigScopeChange):
        _configure_scope(
            _ConfigScopeContext(
                store,
                project_path,
                agent,
                interaction,
                bases,
                agents,
                extensions,
            ),
            result.scope,
            draft,
        )
        return None
    runtime_effective_agent_cfg = context.project_cfg.agents.get(agent, AgentConfig())
    context.project_cfg = load_effective_project_config(
        store, project_path, draft.project_cfg
    )
    _apply_runtime_mount_preferences(
        context.project_cfg.agents.setdefault(agent, AgentConfig()),
        initial_effective_agent_cfg,
        runtime_effective_agent_cfg,
    )
    mounts, env = resolve_docker_args(context, agent, parsed)
    if parsed is None or parsed.menu != "none":
        store.save_project(project_path, draft.project_cfg)

    return RunConfig(
        project_path=project_path,
        agent=agent,
        context=context,
        selection=result.selection,
        project_docker_args=result.project_docker_args,
        mounts=mounts,
        env=env,
    )


def configure_inherited_config(
    scope: str,
    agent: str,
    interaction: RuntimeInteraction,
    parsed: ParsedArgs | None = None,
) -> None:
    store = SettingsStore()
    directory_path = Path.cwd().resolve()
    bases = load_bases()
    agents = load_agents(bases)
    _require_known_agent(agent, agents)
    _configure_scope(
        _ConfigScopeContext(
            store,
            directory_path,
            agent,
            interaction,
            bases,
            agents,
            load_extensions(),
        ),
        scope,
        parsed=parsed,
    )


def _configure_scope(
    scope_context: _ConfigScopeContext,
    scope: str,
    source_draft: RunConfigDraft | None = None,
    parsed: ParsedArgs | None = None,
) -> None:
    current_source = source_draft
    current_parsed = parsed
    while True:
        config, inherited, title = _scope_config(
            scope_context.store, scope_context.directory_path, scope
        )
        source = current_source
        if source is not None:
            config.agents[scope_context.agent] = rebase_agent_config(
                source.effective_agent_cfg,
                inherited.agents.get(scope_context.agent),
            )
            current_source = None
        draft = _create_run_config_draft(
            scope_context.directory_path,
            scope_context.agent,
            config,
            current_parsed,
            inherited,
        )
        if source is not None:
            draft.pending_git_mounts = source.pending_git_mounts
            draft.pending_credential_mounts = source.pending_credential_mounts
            draft.pending_extension_mounts = source.pending_extension_mounts
            draft.pending_docker_socket = source.pending_docker_socket
        draft.scope = scope
        draft.scope_title = title
        draft.scope_config_exists = _scope_config_exists(
            scope_context.store, scope_context.directory_path, scope_context.agent
        )
        if current_parsed is not None:
            draft.prefill_for_overview()
        context = ConfigContext(
            store=scope_context.store,
            project_cfg=merge_project_configs(
                [inherited, config], scope_context.directory_path
            ),
            agents=scope_context.agents,
            bases=scope_context.bases,
            extensions=scope_context.extensions,
        )
        result = scope_context.interaction.configure_run(
            draft, context, scope_context.agent
        )
        if not isinstance(result, ConfigScopeChange):
            _save_scope_config(
                scope_context.store,
                scope_context.directory_path,
                scope,
                draft.project_cfg,
            )
            return
        current_source = draft
        current_parsed = None
        scope = result.scope


def _scope_config(
    store: SettingsStore,
    directory_path: Path,
    scope: str,
) -> tuple[_ProjectConfig, _ProjectConfig, str]:
    if scope == "global":
        config = store.load_global()
        return config, _ProjectConfig(path=config.path), "global configuration"
    if scope == "tree":
        config = store.load_tree(directory_path)
        inherited = merge_project_configs(
            [
                store.load_global(),
                *(store.load_tree(path) for path in reversed(directory_path.parents)),
            ],
            directory_path,
        )
        return config, inherited, "directory tree configuration"
    config = store.load_project(directory_path)
    inherited = load_effective_project_config(
        store,
        directory_path,
        _ProjectConfig(path=str(directory_path)),
    )
    return config, inherited, "container config"


def _scope_config_exists(
    store: SettingsStore,
    directory_path: Path,
    agent: str,
) -> dict[str, bool]:
    return {
        "project": agent in store.load_project(directory_path).agents,
        "global": agent in store.load_global().agents,
        "tree": agent in store.load_tree(directory_path).agents,
    }


def _save_scope_config(
    store: SettingsStore,
    directory_path: Path,
    scope: str,
    config: _ProjectConfig,
) -> None:
    if scope == "global":
        store.save_global(config)
    elif scope == "tree":
        store.save_tree(directory_path, config)
    else:
        store.save_project(directory_path, config)


def _apply_runtime_mount_preferences(
    target: AgentConfig,
    initial: AgentConfig,
    runtime: AgentConfig,
) -> None:
    for name in ("gitconfig", "gitroot", "gnupg", "ssh", "docker"):
        if getattr(runtime.mounts, name) != getattr(initial.mounts, name):
            setattr(target.mounts, name, getattr(runtime.mounts, name))
    target.extension_mounts.update(
        {
            name: value
            for name, value in runtime.extension_mounts.items()
            if initial.extension_mounts.get(name) != value
        }
    )


def _require_known_agent(agent: str, agents: dict[str, AgentMetadata]) -> None:
    if agent in agents:
        return
    if agent == "config":
        raise RegistryError(
            _unknown_agent_message(
                "Unknown agent 'config'. Use '--config' for config commands.",
                agents,
            )
        )
    raise RegistryError(_unknown_agent_message(f"Unknown agent '{agent}'.", agents))


def _unknown_agent_message(
    message: str,
    agents: dict[str, AgentMetadata],
) -> str:
    if not agents:
        return message
    agent_list = ", ".join(sorted(agents))
    return f"{message} Available agents: {agent_list}."


def _remove_missing_extensions(
    agent: str,
    project_cfg: _ProjectConfig,
    extensions: dict[str, ExtensionMetadata],
) -> None:
    agent_cfg = project_cfg.agents.get(agent)
    if not agent_cfg:
        return
    missing = [ext for ext in agent_cfg.extensions if ext not in extensions]
    if not missing:
        return
    get_logger().warning(
        "Removing unavailable extensions for agent %s: %s",
        agent,
        ", ".join(sorted(missing)),
    )
    _prune_agent_extensions(agent, agent_cfg, extensions)


def _prune_agent_extensions(
    agent: str,
    agent_cfg: AgentConfig,
    extensions: dict[str, ExtensionMetadata],
) -> None:
    remaining_extensions = [
        extension for extension in agent_cfg.extensions if extension in extensions
    ]
    agent_cfg.extensions = remaining_extensions
    agent_cfg.extension_mounts = {
        key: value
        for key, value in agent_cfg.extension_mounts.items()
        if key in remaining_extensions
    }
    if remaining_extensions and agent_cfg.base:
        agent_cfg.image_ref = default_extended_image_ref(
            agent,
            agent_cfg.base,
            remaining_extensions,
            extensions,
        )
        return
    agent_cfg.image_ref = None
