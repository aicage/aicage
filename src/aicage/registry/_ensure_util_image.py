"""Utility-image update operations."""

from enum import Enum

from aicage.constants import IMAGE_REGISTRY
from aicage.docker.pull import run_pull
from aicage.docker.query import cleanup_old_digest, get_local_repo_digest_for_repo
from aicage.registry._logs import pull_log_path
from aicage.registry._signature import resolve_verified_digest
from aicage.registry.digest.remote_digest import get_remote_digest
from aicage.reporting import OperationReporter


class _UtilImageSetupAction(Enum):
    SKIP = "skip"
    SETUP = "setup"


def _util_image_setup_action(image_ref: str) -> _UtilImageSetupAction:
    repository = _repository(image_ref)
    local_digest = get_local_repo_digest_for_repo(image_ref, repository)
    if local_digest is not None:
        remote_digest = get_remote_digest(image_ref)
        if remote_digest is None or remote_digest == local_digest:
            return _UtilImageSetupAction.SKIP
    return _UtilImageSetupAction.SETUP


def ensure_util_image(
    image_ref: str,
    reporter: OperationReporter,
    *,
    setup_action: _UtilImageSetupAction | None = None,
) -> None:
    action = setup_action or _util_image_setup_action(image_ref)
    if action is _UtilImageSetupAction.SKIP:
        return
    repository = _repository(image_ref)
    local_digest = get_local_repo_digest_for_repo(image_ref, repository)
    resolve_verified_digest(image_ref, reporter=reporter)
    run_pull(image_ref, pull_log_path(image_ref), reporter=reporter)
    cleanup_old_digest(repository, local_digest, image_ref)


def _repository(image_ref: str) -> str:
    name = image_ref.split("@", 1)[0]
    last_colon = name.rfind(":")
    if last_colon > name.rfind("/"):
        name = name[:last_colon]
    parts = name.split("/", 1)
    if len(parts) == 1:
        return f"{IMAGE_REGISTRY}/{name}"
    registry, remainder = parts
    if "." in registry or ":" in registry or registry == "localhost":
        return f"{registry}/{remainder}"
    return f"{IMAGE_REGISTRY}/{name}"
