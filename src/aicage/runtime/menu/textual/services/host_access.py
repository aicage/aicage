from aicage.config.run_config_draft import RunConfigDraft

from .._ids import built_in_identity, built_in_selection_key, docker_selection_key
from .._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
    DockerOptionValue,
    HostAccessConfirmValues,
)


def built_in_selection_value(item: BuiltInShareValue) -> str:
    return built_in_selection_key(item.source, item.row_key or item.key)


def current_built_in_shares(
    selected: set[str],
    built_in_shares: list[BuiltInShareValue],
) -> list[BuiltInShareValue]:
    enabled_groups = {
        built_in_identity(item.source, item.key)
        for item in built_in_shares
        if built_in_selection_value(item) in selected
    }
    return [
        BuiltInShareValue(
            source=item.source,
            key=item.key,
            label=item.label,
            path=item.path,
            persisted=item.persisted,
            enabled=built_in_identity(item.source, item.key) in enabled_groups,
            row_key=item.row_key,
            inherited=item.inherited,
        )
        for item in built_in_shares
    ]


def built_in_group_selection_values(
    selection_value: str, built_in_shares: list[BuiltInShareValue]
) -> list[str]:
    selected_item = next(
        (
            item
            for item in built_in_shares
            if built_in_selection_value(item) == selection_value
        ),
        None,
    )
    if selected_item is None or selected_item.source != BuiltInShareSource.EXTENSION:
        return []
    group_identity = built_in_identity(selected_item.source, selected_item.key)
    return [
        built_in_selection_value(item)
        for item in built_in_shares
        if built_in_identity(item.source, item.key) == group_identity
    ]


def current_docker_option(
    selected: set[str], persisted: bool | None, inherited: bool = False
) -> DockerOptionValue:
    return DockerOptionValue(
        key="docker",
        label="Docker socket",
        description=None,
        persisted=persisted,
        enabled=docker_selection_key("socket") in selected,
        requires_confirmation=True,
        inherited=inherited,
    )


def _build_confirmation_request(
    built_in_shares: list[BuiltInShareValue],
    docker_options: list[DockerOptionValue],
) -> HostAccessConfirmValues:
    return HostAccessConfirmValues(
        docker_options=[
            option
            for option in docker_options
            if (
                option.enabled
                and option.persisted is not True
                and option.requires_confirmation
            )
        ],
        git_shares=[
            item
            for item in built_in_shares
            if item.source == BuiltInShareSource.GIT_SUPPORT
            and item.enabled
            and item.persisted is not True
        ],
        credential_shares=[
            item
            for item in built_in_shares
            if item.source == BuiltInShareSource.CREDENTIALS
            and item.enabled
            and item.persisted is not True
        ],
        extension_shares=[
            item
            for item in built_in_shares
            if item.source == BuiltInShareSource.EXTENSION
            and item.enabled
            and item.persisted is not True
        ],
    )


def _merge_confirmed_host_access(
    built_in_shares: list[BuiltInShareValue],
    docker_options: list[DockerOptionValue],
    confirmed: HostAccessConfirmValues,
) -> tuple[list[BuiltInShareValue], list[DockerOptionValue]]:
    confirmed_by_key = {
        built_in_identity(item.source, item.key): item.enabled
        for item in [
            *confirmed.git_shares,
            *confirmed.credential_shares,
            *confirmed.extension_shares,
        ]
    }
    merged_shares = [
        (
            BuiltInShareValue(
                source=item.source,
                key=item.key,
                label=item.label,
                path=item.path,
                persisted=item.persisted,
                enabled=confirmed_by_key.get(
                    built_in_identity(item.source, item.key), item.enabled
                ),
                row_key=item.row_key,
                inherited=item.inherited,
            )
            if built_in_identity(item.source, item.key) in confirmed_by_key
            else item
        )
        for item in built_in_shares
    ]
    confirmed_docker_by_key = {
        item.key: item.enabled for item in confirmed.docker_options
    }
    return (
        merged_shares,
        [
            DockerOptionValue(
                key=option.key,
                label=option.label,
                description=option.description,
                persisted=option.persisted,
                enabled=confirmed_docker_by_key.get(option.key, option.enabled),
                inherited=option.inherited,
            )
            for option in docker_options
        ],
    )


def apply_host_access(
    draft: RunConfigDraft,
    built_in_shares: list[BuiltInShareValue],
    custom_shares: list[CustomShareValue],
    docker_options: list[DockerOptionValue],
) -> None:
    draft.agent_cfg.shares = [
        item.value for item in custom_shares if not item.inherited
    ]
    for item in built_in_shares:
        if item.inherited:
            continue
        if item.source in {
            BuiltInShareSource.GIT_SUPPORT,
            BuiltInShareSource.CREDENTIALS,
        }:
            setattr(draft.agent_cfg.mounts, item.key, item.enabled)
        elif item.source == BuiltInShareSource.EXTENSION:
            draft.agent_cfg.extension_mounts[item.key] = item.enabled
    for option in docker_options:
        if option.inherited:
            continue
        if option.key == "docker":
            draft.agent_cfg.mounts.docker = option.enabled


def _apply_confirmed_host_access(
    draft: RunConfigDraft,
    built_in_shares: list[BuiltInShareValue],
    custom_shares: list[CustomShareValue],
    docker_options: list[DockerOptionValue],
) -> None:
    apply_host_access(draft, built_in_shares, custom_shares, docker_options)
