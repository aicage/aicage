import json
import subprocess
from unittest import TestCase, mock

from aicage import constants
from aicage.registry import _signature
from aicage.registry._errors import RegistryError

_AGENT_IMAGE_REF = f"{constants.IMAGE_REGISTRY}/{constants.IMAGE_REPOSITORY}:agent"
_AGENT_DIGEST_REF = (
    f"{constants.IMAGE_REGISTRY}/{constants.IMAGE_REPOSITORY}@sha256:abc"
)
_UTIL_DIGEST_REF = (
    f"{constants.IMAGE_REGISTRY}/{constants.IMAGE_UTIL_REPOSITORY}@sha256:abc"
)


class SignatureVerificationTests(TestCase):
    def test_resolve_verified_digest_returns_digest_ref_on_valid_signature(
        self,
    ) -> None:
        image_ref = _AGENT_IMAGE_REF
        reporter = mock.Mock()
        with (
            mock.patch(
                "aicage.registry._signature.get_remote_digest",
                return_value="sha256:abc",
            ),
            mock.patch(
                "aicage.registry._signature.get_local_repo_digest_for_repo",
                return_value=None,
            ),
            mock.patch(
                "aicage.registry._signature.local_image_exists",
                return_value=True,
            ),
            mock.patch(
                "aicage.registry._signature._run_cosign_verify",
                return_value=subprocess.CompletedProcess(
                    args=["cosign"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ) as cosign_mock,
            mock.patch(
                "aicage.registry._signature._verify_manifest_annotations"
            ) as annotation_mock,
        ):
            digest_ref = _signature.resolve_verified_digest(
                image_ref, reporter=reporter
            )
        self.assertEqual(_AGENT_DIGEST_REF, digest_ref)
        cosign_mock.assert_called_once_with(_AGENT_DIGEST_REF)
        annotation_mock.assert_called_once_with(
            _AGENT_DIGEST_REF, expected_image_ref=image_ref
        )

    def test_resolve_verified_digest_raises_on_invalid_signature(self) -> None:
        image_ref = _AGENT_IMAGE_REF
        reporter = mock.Mock()
        with (
            mock.patch(
                "aicage.registry._signature.get_remote_digest",
                return_value="sha256:abc",
            ),
            mock.patch(
                "aicage.registry._signature.get_local_repo_digest_for_repo",
                return_value=None,
            ),
            mock.patch(
                "aicage.registry._signature.local_image_exists",
                return_value=True,
            ),
            mock.patch(
                "aicage.registry._signature._run_cosign_verify",
                return_value=subprocess.CompletedProcess(
                    args=["cosign"],
                    returncode=1,
                    stdout="",
                    stderr="no signatures found",
                ),
            ),
            mock.patch(
                "aicage.registry._signature._verify_manifest_annotations"
            ) as annotation_mock,
        ):
            with self.assertRaises(RegistryError):
                _signature.resolve_verified_digest(image_ref, reporter=reporter)
        annotation_mock.assert_not_called()

    def test_resolve_verified_digest_raises_on_unknown_error(self) -> None:
        image_ref = _AGENT_IMAGE_REF
        reporter = mock.Mock()
        with (
            mock.patch(
                "aicage.registry._signature.get_remote_digest",
                return_value="sha256:abc",
            ),
            mock.patch(
                "aicage.registry._signature.get_local_repo_digest_for_repo",
                return_value=None,
            ),
            mock.patch(
                "aicage.registry._signature.local_image_exists",
                return_value=True,
            ),
            mock.patch(
                "aicage.registry._signature._run_cosign_verify",
                return_value=subprocess.CompletedProcess(
                    args=["cosign"],
                    returncode=2,
                    stdout="unexpected failure",
                    stderr="",
                ),
            ),
            mock.patch(
                "aicage.registry._signature._verify_manifest_annotations"
            ) as annotation_mock,
        ):
            with self.assertRaises(RegistryError):
                _signature.resolve_verified_digest(image_ref, reporter=reporter)
        annotation_mock.assert_not_called()

    def test_resolve_verified_digest_raises_when_digest_missing(self) -> None:
        image_ref = _AGENT_IMAGE_REF
        reporter = mock.Mock()
        with (
            mock.patch(
                "aicage.registry._signature.get_remote_digest",
                return_value=None,
            ) as digest_mock,
            mock.patch(
                "aicage.registry._signature.get_local_repo_digest_for_repo",
                return_value=None,
            ),
            mock.patch("aicage.registry._signature._run_cosign_verify") as cosign_mock,
        ):
            with self.assertRaises(RegistryError):
                _signature.resolve_verified_digest(image_ref, reporter=reporter)
        digest_mock.assert_called_once_with(image_ref)
        cosign_mock.assert_not_called()

    @staticmethod
    def test_resolve_verified_digest_pulls_cosign_image_when_missing() -> None:
        image_ref = _AGENT_IMAGE_REF
        reporter = mock.Mock()
        with (
            mock.patch(
                "aicage.registry._signature.get_remote_digest",
                return_value="sha256:abc",
            ),
            mock.patch(
                "aicage.registry._signature.get_local_repo_digest_for_repo",
                return_value=None,
            ),
            mock.patch(
                "aicage.registry._signature.local_image_exists",
                return_value=False,
            ),
            mock.patch(
                "aicage.registry._signature.pull_log_path",
                return_value=mock.Mock(),
            ) as log_mock,
            mock.patch("aicage.registry._signature.run_pull") as pull_mock,
            mock.patch("aicage.registry._signature.cleanup_old_digest") as cleanup_mock,
            mock.patch(
                "aicage.registry._signature._run_cosign_verify",
                return_value=subprocess.CompletedProcess(
                    args=["cosign"],
                    returncode=0,
                    stdout="",
                    stderr="",
                ),
            ),
            mock.patch("aicage.registry._signature._verify_manifest_annotations"),
        ):
            _signature.resolve_verified_digest(image_ref, reporter=reporter)
        log_mock.assert_called_once_with(constants.COSIGN_IMAGE_REF)
        pull_mock.assert_called_once_with(
            constants.COSIGN_IMAGE_REF, log_mock.return_value, reporter=reporter
        )
        cleanup_mock.assert_called_once_with(
            constants.COSIGN_IMAGE_REF.partition("@")[0],
            None,
            constants.COSIGN_IMAGE_REF,
        )

    def test__verify_manifest_annotations_skips_non_aicage_repository(self) -> None:
        image_ref = "ghcr.io/other/test@sha256:abc"
        with mock.patch(
            "aicage.registry._signature._manifest_annotations"
        ) as annotations_mock:
            _signature._verify_manifest_annotations(image_ref)
        annotations_mock.assert_not_called()

    def test__verify_manifest_annotations_accepts_expected_official_annotations(
        self,
    ) -> None:
        image_ref = _UTIL_DIGEST_REF
        annotations = {
            "org.opencontainers.image.source": constants.IMAGE_UTIL_SOURCE_URL,
            "org.opencontainers.image.title": "aicage-image-util",
        }
        with mock.patch(
            "aicage.registry._signature._manifest_annotations",
            return_value=annotations,
        ):
            _signature._verify_manifest_annotations(image_ref)

    def test__verify_manifest_annotations_accepts_credential_agent_annotations(
        self,
    ) -> None:
        annotations = {
            "org.opencontainers.image.source": constants.IMAGE_UTIL_SOURCE_URL,
            "org.opencontainers.image.title": "aicage-image-util credential agent",
        }
        with mock.patch(
            "aicage.registry._signature._manifest_annotations",
            return_value=annotations,
        ):
            _signature._verify_manifest_annotations(
                _UTIL_DIGEST_REF,
                expected_image_ref=constants.CREDENTIAL_AGENT_IMAGE,
            )

    def test__verify_manifest_annotations_raises_when_expected_annotation_mismatches(
        self,
    ) -> None:
        annotations = {
            "org.opencontainers.image.source": "https://github.com/example/wrong",
            "org.opencontainers.image.title": "aicage",
        }
        image_ref = _AGENT_DIGEST_REF
        with mock.patch(
            "aicage.registry._signature._manifest_annotations",
            return_value=annotations,
        ):
            with self.assertRaises(RegistryError) as raised:
                _signature._verify_manifest_annotations(image_ref)
        self.assertIn("org.opencontainers.image.source mismatch", str(raised.exception))

    def test__manifest_annotations_returns_annotation_map(self) -> None:
        image_ref = _AGENT_DIGEST_REF
        with mock.patch(
            "aicage.registry._signature.run_docker_command_capture",
            return_value=subprocess.CompletedProcess(
                args=["docker"],
                returncode=0,
                stdout=json.dumps(
                    {
                        "annotations": {
                            "org.opencontainers.image.source": constants.IMAGE_SOURCE_URL,
                            "org.opencontainers.image.title": "aicage",
                        }
                    }
                ),
                stderr="",
            ),
        ) as docker_mock:
            annotations = _signature._manifest_annotations(image_ref)
        self.assertEqual(
            {
                "org.opencontainers.image.source": constants.IMAGE_SOURCE_URL,
                "org.opencontainers.image.title": "aicage",
            },
            annotations,
        )
        docker_mock.assert_called_once_with(
            [
                "docker",
                "buildx",
                "imagetools",
                "inspect",
                "--raw",
                image_ref,
            ],
            check=False,
            text=True,
        )

    def test__manifest_annotations_raises_when_inspect_fails(self) -> None:
        image_ref = _AGENT_DIGEST_REF
        with mock.patch(
            "aicage.registry._signature.run_docker_command_capture",
            return_value=subprocess.CompletedProcess(
                args=["docker"],
                returncode=1,
                stdout="",
                stderr="boom",
            ),
        ):
            with self.assertRaises(RegistryError) as raised:
                _signature._manifest_annotations(image_ref)
        self.assertIn("Failed to inspect image manifest", str(raised.exception))

    def test__manifest_annotations_raises_when_json_is_invalid(self) -> None:
        image_ref = _AGENT_DIGEST_REF
        with mock.patch(
            "aicage.registry._signature.run_docker_command_capture",
            return_value=subprocess.CompletedProcess(
                args=["docker"],
                returncode=0,
                stdout="{not json",
                stderr="",
            ),
        ):
            with self.assertRaises(RegistryError) as raised:
                _signature._manifest_annotations(image_ref)
        self.assertIn("Invalid manifest JSON", str(raised.exception))

    def test__manifest_annotations_raises_when_annotations_missing(self) -> None:
        image_ref = _AGENT_DIGEST_REF
        with mock.patch(
            "aicage.registry._signature.run_docker_command_capture",
            return_value=subprocess.CompletedProcess(
                args=["docker"],
                returncode=0,
                stdout="{}",
                stderr="",
            ),
        ):
            with self.assertRaises(RegistryError) as raised:
                _signature._manifest_annotations(image_ref)
        self.assertIn("missing annotations", str(raised.exception))
