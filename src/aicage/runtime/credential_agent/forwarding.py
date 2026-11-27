"""Protocol-aware credential forwarding for target containers."""

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from functools import partial

from aicage.config.context import ConfigContext
from aicage.config.project_config import AgentConfig
from aicage.reporting import OperationReporter
from aicage.runtime.run_args import EnvVar, MountSpec

from ._env import _credential_agent_user
from ._gpg_forwarding import (
    _gpg_enabled,
    _gpg_forwarding,
    _GpgForwardingPlan,
    _prepare_direct_gpg_keys,
    _reload_gpg_keys,
)
from ._image import _credential_image
from ._resource_models import _CredentialProtocol, _CredentialResource, _ImageSpec
from ._resources import _ensure_resources
from ._ssh_forwarding import (
    _append_ssh_target_args,
    _prepare_ssh_forwarding,
    _reload_ssh_keys,
    _ssh_forwarding,
    _SshForwardingPlan,
)


@dataclass(frozen=True)
class CredentialSetup:
    plan: "_CredentialPlan"
    resources: list[_CredentialResource]


@dataclass(frozen=True)
class _CredentialPlan:
    mounts: list[MountSpec]
    env: list[EnvVar]
    protocols: list[_CredentialProtocol]
    gpg_plan: _GpgForwardingPlan | None
    ssh_plan: _SshForwardingPlan | None


def plan_credentials(
    context: ConfigContext,
    agent: str,
) -> _CredentialPlan:
    return _credential_plan(context, agent)


def prepare_credentials(
    plan: _CredentialPlan,
    reporter: OperationReporter,
    *,
    interactive: bool,
) -> CredentialSetup:
    return CredentialSetup(plan, _prepare_plan(plan, reporter, interactive=interactive))


@contextmanager
def credential_forwarding(
    setup: CredentialSetup,
) -> Iterator[tuple[list[MountSpec], list[EnvVar]]]:
    plan = setup.plan
    mounts = list(plan.mounts)
    env = list(plan.env)
    gpg_resource: _CredentialResource | None = None
    for resource in setup.resources:
        if resource.protocol is _CredentialProtocol.GPG:
            gpg_resource = resource
        else:
            _append_sidecar_target_args(resource, mounts, env)
    if plan.gpg_plan is None:
        yield mounts, env
        return
    if gpg_resource is None:
        if plan.gpg_plan.direct_socket is None:
            yield mounts, env
            return
        with plan.gpg_plan.direct_target_args() as direct_mounts:
            mounts.extend(direct_mounts)
            yield mounts, env
        return
    with plan.gpg_plan.sidecar_target_args(gpg_resource) as sidecar_mounts:
        mounts.extend(sidecar_mounts)
        yield mounts, env


def _credential_plan(context: ConfigContext, agent: str) -> _CredentialPlan:
    agent_cfg = context.project_cfg.agents.get(agent, AgentConfig())
    mounts: list[MountSpec] = []
    env: list[EnvVar] = []
    protocols: list[_CredentialProtocol] = []
    gpg_plan: _GpgForwardingPlan | None = None
    ssh_plan: _SshForwardingPlan | None = None
    if agent_cfg.mounts.ssh is True:
        ssh_plan = _ssh_forwarding()
        mounts.extend(ssh_plan.mounts)
        env.extend(ssh_plan.env)
        if ssh_plan.requires_sidecar:
            protocols.append(_CredentialProtocol.SSH)

    if _gpg_enabled(context, agent):
        gpg_plan = _gpg_forwarding()
        if gpg_plan is not None and gpg_plan.requires_sidecar:
            protocols.append(_CredentialProtocol.GPG)
    return _CredentialPlan(mounts, env, protocols, gpg_plan, ssh_plan)


def _prepare_plan(
    plan: _CredentialPlan, reporter: OperationReporter, *, interactive: bool
) -> list[_CredentialResource]:
    if plan.ssh_plan is not None:
        _prepare_ssh_forwarding(plan.ssh_plan, interactive=interactive)
    if plan.gpg_plan is not None and not plan.gpg_plan.requires_sidecar:
        _prepare_direct_gpg_keys(plan.gpg_plan.credential_home, interactive=interactive)
    if not plan.protocols:
        return []
    image_ref, image_id = _credential_image()
    return _ensure_resources(
        plan.protocols,
        _ImageSpec(image_ref, image_id, _credential_agent_user()),
        plan.gpg_plan.credential_home if plan.gpg_plan is not None else None,
        reconcile=partial(_reload_credentials, interactive=interactive),
    )


def _reload_credentials(
    resources: list[_CredentialResource], *, interactive: bool
) -> None:
    _reload_ssh_keys(resources, interactive=interactive)
    _reload_gpg_keys(resources, interactive=interactive)


def _append_sidecar_target_args(
    resource: _CredentialResource,
    mounts: list[MountSpec],
    env: list[EnvVar],
) -> None:
    if resource.protocol is _CredentialProtocol.SSH:
        _append_ssh_target_args(resource, mounts, env)
