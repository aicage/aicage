from unittest import TestCase, mock

from aicage.runtime.credential_agent import forwarding, image_setup
from aicage.runtime.credential_agent._resource_models import _CredentialProtocol


class CredentialImageSetupTests(TestCase):
    def test_prepare_credential_image_skips_when_credentials_are_disabled(self) -> None:
        interaction = mock.Mock()
        plan = forwarding._CredentialPlan([], [], [], None, None)

        with mock.patch.object(image_setup, "util_image_setup_action") as plan_mock:
            image_setup.prepare_credential_image(plan, interaction)

        plan_mock.assert_not_called()
        interaction.execute_operation.assert_not_called()

    def test_prepare_credential_image_skips_a_current_image(self) -> None:
        interaction = mock.Mock()
        plan = forwarding._CredentialPlan([], [], [_CredentialProtocol.SSH], None, None)

        with mock.patch.object(
            image_setup,
            "util_image_setup_action",
            return_value=image_setup.UtilImageSetupAction.SKIP,
        ):
            image_setup.prepare_credential_image(plan, interaction)

        interaction.execute_operation.assert_not_called()

    def test_prepare_credential_image_executes_required_setup(self) -> None:
        interaction = mock.Mock()
        plan = forwarding._CredentialPlan([], [], [_CredentialProtocol.GPG], None, None)
        reporter = mock.Mock()
        interaction.execute_operation.side_effect = lambda operation: operation(
            reporter
        )

        with (
            mock.patch.object(
                image_setup,
                "util_image_setup_action",
                return_value=image_setup.UtilImageSetupAction.SETUP,
            ),
            mock.patch.object(image_setup, "ensure_util_image") as ensure_mock,
        ):
            image_setup.prepare_credential_image(plan, interaction)

        ensure_mock.assert_called_once_with(
            image_setup.CREDENTIAL_AGENT_IMAGE,
            reporter,
            setup_action=image_setup.UtilImageSetupAction.SETUP,
        )
