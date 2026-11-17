from aicage.config.context import ConfigContext
from aicage.config.image_refs import default_extended_image_ref
from aicage.config.project_config import AgentConfig
from aicage.constants import DEFAULT_EXTENDED_IMAGE_NAME

from ._fresh_selection import fresh_selection
from ._metadata import require_agent_metadata, validate_base
from .extensions.context import ExtensionSelectionContext
from .extensions.handler import handle_extension_selection
from .extensions.refs import agent_image_ref
from .interaction import _SelectionInteraction
from .models import ImageSelection


def select_agent_image(
    agent: str,
    context: ConfigContext,
    selection_interaction: _SelectionInteraction,
) -> ImageSelection:
    extensions = context.extensions
    agent_cfg = context.project_cfg.agents.setdefault(agent, AgentConfig())
    agent_metadata = require_agent_metadata(agent, context)
    base = agent_cfg.base

    _clear_stale_extended_image_ref(agent_cfg)
    _resolve_extended_image_ref(agent, base, agent_cfg, context)

    if agent_cfg.image_ref:
        if base is None:
            return fresh_selection(agent, context, extensions, selection_interaction)
        validate_base(agent, base, context)
        return ImageSelection(
            image_ref=agent_cfg.image_ref,
            base=base,
            extensions=list(agent_cfg.extensions),
            agent_image_ref=agent_image_ref(agent_metadata, agent, base, context),
        )

    if not base:
        return fresh_selection(agent, context, extensions, selection_interaction)

    validate_base(agent, base, context)
    return handle_extension_selection(
        ExtensionSelectionContext(
            agent=agent,
            base=base,
            agent_cfg=agent_cfg,
            agent_metadata=agent_metadata,
            extensions=extensions,
            context=context,
        ),
        selection_interaction,
    )


def _clear_stale_extended_image_ref(agent_cfg: AgentConfig) -> None:
    if agent_cfg.extensions or not agent_cfg.image_ref:
        return
    if agent_cfg.image_ref.startswith(f"{DEFAULT_EXTENDED_IMAGE_NAME}:"):
        agent_cfg.image_ref = None


def _resolve_extended_image_ref(
    agent: str,
    base: str | None,
    agent_cfg: AgentConfig,
    context: ConfigContext,
) -> None:
    if not agent_cfg.extensions or base is None:
        return
    agent_cfg.image_ref = default_extended_image_ref(
        agent,
        base,
        agent_cfg.extensions,
        context.extensions,
    )
