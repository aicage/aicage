from unittest import TestCase, mock

from aicage.constants import VERSION_CHECK_IMAGE
from aicage.registry._errors import RegistryError
from aicage.registry.agent_build.agent_version import _images


class AgentVersionImagesTests(TestCase):
    def test_ensure_version_check_image_uses_shared_image_update(self) -> None:
        reporter = mock.Mock()
        with mock.patch.object(_images, "ensure_util_image") as ensure_mock:
            _images.ensure_version_check_image(VERSION_CHECK_IMAGE, reporter)

        ensure_mock.assert_called_once_with(VERSION_CHECK_IMAGE, reporter)

    def test_ensure_version_check_image_keeps_the_fallback_on_failure(self) -> None:
        with mock.patch.object(
            _images, "ensure_util_image", side_effect=RegistryError("failed")
        ):
            _images.ensure_version_check_image(VERSION_CHECK_IMAGE, mock.Mock())
