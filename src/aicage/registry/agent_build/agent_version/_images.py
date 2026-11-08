from aicage._logging import get_logger
from aicage.registry._errors import RegistryError
from aicage.registry._logs import pull_log_path
from aicage.registry.ensure_util_image import ensure_util_image
from aicage.reporting import OperationReporter


def ensure_version_check_image(image_ref: str, reporter: OperationReporter) -> None:
    logger = get_logger()
    try:
        ensure_util_image(image_ref, reporter)
    except RegistryError:
        logger.warning(
            "Version check image pull failed; using local image (logs: %s).",
            pull_log_path(image_ref),
        )
