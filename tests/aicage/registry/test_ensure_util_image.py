from unittest import TestCase, mock

from aicage.registry import ensure_util_image


class EnsureUtilImageTests(TestCase):
    def test_util_image_setup_action_skips_a_current_image(self) -> None:
        with (
            mock.patch.object(
                ensure_util_image,
                "get_local_repo_digest_for_repo",
                return_value="sha256:current",
            ),
            mock.patch.object(
                ensure_util_image,
                "get_remote_digest",
                return_value="sha256:current",
            ),
        ):
            action = ensure_util_image.util_image_setup_action("example/image:tag")

        self.assertIs(ensure_util_image.UtilImageSetupAction.SKIP, action)

    def test_util_image_setup_action_skips_when_remote_digest_is_unavailable(
        self,
    ) -> None:
        with (
            mock.patch.object(
                ensure_util_image,
                "get_local_repo_digest_for_repo",
                return_value="sha256:current",
            ),
            mock.patch.object(
                ensure_util_image, "get_remote_digest", return_value=None
            ),
        ):
            action = ensure_util_image.util_image_setup_action("example/image:tag")

        self.assertIs(ensure_util_image.UtilImageSetupAction.SKIP, action)

    def test_util_image_setup_action_requires_setup_for_missing_or_stale_images(
        self,
    ) -> None:
        cases = ((None, None), ("sha256:old", "sha256:current"))
        for local_digest, remote_digest in cases:
            with self.subTest(local_digest=local_digest, remote_digest=remote_digest):
                with (
                    mock.patch.object(
                        ensure_util_image,
                        "get_local_repo_digest_for_repo",
                        return_value=local_digest,
                    ),
                    mock.patch.object(
                        ensure_util_image,
                        "get_remote_digest",
                        return_value=remote_digest,
                    ),
                ):
                    action = ensure_util_image.util_image_setup_action(
                        "example/image:tag"
                    )

                self.assertIs(ensure_util_image.UtilImageSetupAction.SETUP, action)

    def test_ensure_util_image_pulls_a_missing_image(self) -> None:
        with (
            mock.patch.object(
                ensure_util_image, "get_local_repo_digest_for_repo", return_value=None
            ),
            mock.patch.object(ensure_util_image, "resolve_verified_digest"),
            mock.patch.object(ensure_util_image, "run_pull") as pull_mock,
            mock.patch.object(ensure_util_image, "cleanup_old_digest") as cleanup_mock,
        ):
            ensure_util_image.ensure_util_image("example/image:tag", mock.Mock())

        pull_mock.assert_called_once()
        cleanup_mock.assert_called_once()

    def test_ensure_util_image_uses_a_supplied_setup_action(self) -> None:
        with (
            mock.patch.object(
                ensure_util_image, "util_image_setup_action"
            ) as plan_mock,
            mock.patch.object(
                ensure_util_image, "get_local_repo_digest_for_repo", return_value=None
            ),
            mock.patch.object(ensure_util_image, "resolve_verified_digest"),
            mock.patch.object(ensure_util_image, "run_pull"),
            mock.patch.object(ensure_util_image, "cleanup_old_digest"),
        ):
            ensure_util_image.ensure_util_image(
                "example/image:tag",
                mock.Mock(),
                setup_action=ensure_util_image.UtilImageSetupAction.SETUP,
            )

        plan_mock.assert_not_called()
