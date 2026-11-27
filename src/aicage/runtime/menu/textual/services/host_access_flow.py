from collections.abc import Awaitable, Callable

from aicage.config.run_config_draft import RunConfigDraft

from .._models import (
    BuiltInShareValue,
    CustomShareValue,
    DockerOptionValue,
    HostAccessConfirmValues,
)
from .host_access import (
    _build_confirmation_request,
    _merge_confirmed_host_access,
    apply_host_access,
)


async def confirm_and_apply_host_access(
    draft: RunConfigDraft,
    built_in_shares: list[BuiltInShareValue],
    custom_shares: list[CustomShareValue],
    docker_options: list[DockerOptionValue],
    confirm_host_access: Callable[
        [HostAccessConfirmValues], Awaitable[HostAccessConfirmValues | None]
    ],
) -> tuple[bool, list[BuiltInShareValue]]:
    confirmation_request = _build_confirmation_request(built_in_shares, docker_options)
    if (
        confirmation_request.docker_options
        or confirmation_request.git_shares
        or confirmation_request.credential_shares
        or confirmation_request.extension_shares
    ):
        confirmed = await confirm_host_access(confirmation_request)
        if confirmed is None:
            return False, built_in_shares
        built_in_shares, docker_options = _merge_confirmed_host_access(
            built_in_shares, docker_options, confirmed
        )
    apply_host_access(
        draft,
        built_in_shares,
        custom_shares,
        docker_options,
    )
    return True, built_in_shares
