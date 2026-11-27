"""Credential utility-image preparation."""

from aicage.constants import CREDENTIAL_AGENT_IMAGE
from aicage.registry.ensure_util_image import (
    UtilImageSetupAction,
    ensure_util_image,
    util_image_setup_action,
)
from aicage.runtime.menu.interaction import RuntimeInteraction

from .forwarding import _CredentialPlan


def prepare_credential_image(
    plan: _CredentialPlan, interaction: RuntimeInteraction
) -> None:
    if not plan.protocols:
        return
    setup_action = util_image_setup_action(CREDENTIAL_AGENT_IMAGE)
    if setup_action is UtilImageSetupAction.SKIP:
        return
    interaction.execute_operation(
        lambda reporter: ensure_util_image(
            CREDENTIAL_AGENT_IMAGE,
            reporter,
            setup_action=setup_action,
        )
    )
