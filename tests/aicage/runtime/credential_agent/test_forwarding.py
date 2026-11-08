from contextlib import nullcontext
from pathlib import Path, PurePosixPath
from unittest import TestCase, mock

from aicage.config.project_config import AgentConfig, _AgentMounts
from aicage.runtime.credential_agent import _gpg_forwarding, forwarding
from aicage.runtime.credential_agent._resource_models import (
    _CredentialProtocol,
    _resources,
)
from aicage.runtime.credential_agent._ssh_forwarding import _SshForwardingPlan
from aicage.runtime.run_args import EnvVar, VolumeMountSpec


class CredentialAgentForwardingTests(TestCase):
    def test_plan_credentials_ensures_all_requested_sidecars_once(self) -> None:
        ssh_resource, gpg_resource = _resources(
            [_CredentialProtocol.SSH, _CredentialProtocol.GPG]
        )
        context = mock.Mock()
        context.project_cfg.agents = {
            "codex": AgentConfig(mounts=_AgentMounts(ssh=True, gnupg=True))
        }
        gpg_plan = _gpg_forwarding._GpgForwardingPlan(Path("/test-tmp/gnupg"), True)
        with (
            mock.patch.object(
                forwarding,
                "_ssh_forwarding",
                return_value=_SshForwardingPlan([], [], True, None),
            ) as ssh_mock,
            mock.patch.object(forwarding, "_gpg_enabled", return_value=True),
            mock.patch.object(forwarding, "_gpg_forwarding", return_value=gpg_plan),
            mock.patch.object(
                forwarding, "_credential_image", return_value=("image", "id")
            ) as image_mock,
            mock.patch.object(
                forwarding,
                "_ensure_resources",
                return_value=[ssh_resource, gpg_resource],
            ) as resources_mock,
        ):
            plan = forwarding.plan_credentials(context, "codex")
            forwarding.prepare_credentials(plan, mock.Mock(), interactive=True)

        image_mock.assert_called_once()
        resources_mock.assert_called_once_with(
            [_CredentialProtocol.SSH, _CredentialProtocol.GPG],
            mock.ANY,
            gpg_plan.credential_home,
            reconcile=mock.ANY,
        )
        ssh_mock.assert_called_once_with()

    def test_credential_forwarding_adds_ssh_target_args(self) -> None:
        resource = _resources([_CredentialProtocol.SSH])[0]
        setup = forwarding.CredentialSetup(
            forwarding._CredentialPlan([], [], [_CredentialProtocol.SSH], None, None),
            [resource],
        )
        with forwarding.credential_forwarding(setup) as (mounts, env):
            self.assertEqual(
                [
                    VolumeMountSpec(
                        resource.volume_name,
                        PurePosixPath("/run/credential-agent"),
                        True,
                    )
                ],
                mounts,
            )
            self.assertEqual(
                [EnvVar("SSH_AUTH_SOCK", "/run/credential-agent/ssh-agent.sock")],
                env,
            )

    def test_prepare_credentials_uses_direct_ssh_without_sidecar_resources(
        self,
    ) -> None:
        context = mock.Mock()
        context.project_cfg.agents = {
            "codex": AgentConfig(mounts=_AgentMounts(ssh=True))
        }
        socket_mount = mock.Mock()
        ssh_env = EnvVar("SSH_AUTH_SOCK", "/run/credential-agent/ssh-agent.sock")
        with (
            mock.patch.object(
                forwarding,
                "_ssh_forwarding",
                return_value=_SshForwardingPlan(
                    [socket_mount], [ssh_env], False, Path("/test-tmp/ssh-agent.sock")
                ),
            ),
            mock.patch.object(forwarding, "_gpg_enabled", return_value=False),
            mock.patch.object(forwarding, "_prepare_ssh_forwarding") as ssh_prepare,
            mock.patch.object(forwarding, "_credential_image") as image_mock,
            mock.patch.object(forwarding, "_ensure_resources") as resources_mock,
        ):
            plan = forwarding.plan_credentials(context, "codex")
            setup = forwarding.prepare_credentials(plan, mock.Mock(), interactive=False)

        self.assertEqual([socket_mount], setup.plan.mounts)
        self.assertEqual([ssh_env], setup.plan.env)
        self.assertEqual([], setup.resources)
        image_mock.assert_not_called()
        resources_mock.assert_not_called()
        ssh_prepare.assert_called_once()

    def test_credential_forwarding_uses_direct_gpg_target_args(self) -> None:
        gpg_plan = _gpg_forwarding._GpgForwardingPlan(
            Path("/test-tmp/gnupg"), False, Path("/test-tmp/gnupg/S.gpg-agent")
        )
        setup = forwarding.CredentialSetup(
            forwarding._CredentialPlan([], [], [], gpg_plan, None), []
        )
        with mock.patch.object(
            gpg_plan, "direct_target_args", return_value=nullcontext([])
        ):
            with forwarding.credential_forwarding(setup) as (mounts, env):
                self.assertEqual([], mounts)
                self.assertEqual([], env)
