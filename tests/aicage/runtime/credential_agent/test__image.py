from unittest import TestCase, mock

from aicage import constants
from aicage.runtime.credential_agent import _image


class CredentialAgentImageTests(TestCase):
    def test_credential_image_returns_the_local_image_id(self) -> None:
        with mock.patch.object(_image, "get_local_image_id", return_value="image-id"):
            image = _image._credential_image()

        self.assertEqual((constants.CREDENTIAL_AGENT_IMAGE, "image-id"), image)
