from aicage.config.extended_images import (
    ExtendedImageConfig,
    extended_image_config_path,
    write_extended_image_config,
)
from aicage.config.extensions.order import canonical_extensions
from aicage.config.image_refs import default_extended_image_ref, extended_image_name

from ..interaction import ExtensionChoiceOption, _SelectionInteraction
from ..models import ImageSelection
from .context import ExtensionSelectionContext
from .refs import agent_image_ref


def handle_extension_selection(
    selection: ExtensionSelectionContext,
    selection_interaction: _SelectionInteraction,
) -> ImageSelection:
    agent_cfg = selection.agent_cfg
    agent_cfg.base = selection.base
    extension_options = [
        ExtensionChoiceOption(
            name=ext.extension_id,
            description=f"{ext.name}: {ext.description}",
            has_dockerfile=ext.dockerfile_path is not None,
        )
        for ext in canonical_extensions(list(selection.extensions.values()))
    ]
    selected_extensions = (
        selection_interaction.choose_extensions(extension_options)
        if extension_options
        else []
    )
    if selected_extensions:
        image_ref = default_extended_image_ref(
            selection.agent,
            selection.base,
            selected_extensions,
            selection.extensions,
        )
        agent_cfg.extensions = list(selected_extensions)
        agent_cfg.image_ref = image_ref
        write_extended_image_config(
            ExtendedImageConfig(
                name=extended_image_name(image_ref),
                agent=selection.agent,
                base=selection.base,
                extensions=list(selected_extensions),
                image_ref=image_ref,
                path=extended_image_config_path(extended_image_name(image_ref)),
            )
        )
    else:
        agent_cfg.extensions = []
        agent_cfg.image_ref = agent_image_ref(
            selection.agent_metadata,
            selection.agent,
            selection.base,
            selection.context,
        )
    return ImageSelection(
        image_ref=agent_cfg.image_ref or "",
        base=selection.base,
        extensions=list(agent_cfg.extensions),
        agent_image_ref=agent_image_ref(
            selection.agent_metadata,
            selection.agent,
            selection.base,
            selection.context,
        ),
    )
