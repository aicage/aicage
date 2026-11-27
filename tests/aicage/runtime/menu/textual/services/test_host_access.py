from unittest import TestCase

from aicage.cli_types import ParsedArgs
from aicage.config.project_config import AgentConfig
from aicage.runtime.menu.textual._models import (
    BuiltInShareSource,
    BuiltInShareValue,
    CustomShareValue,
    DockerOptionValue,
    HostAccessConfirmValues,
)
from aicage.runtime.menu.textual.services import host_access

from ..._test_support import _build_draft


class HostAccessTests(TestCase):
    def test_built_in_selection_value_returns_row_key_when_present(self) -> None:
        value = host_access.built_in_selection_value(
            BuiltInShareValue(
                BuiltInShareSource.EXTENSION,
                "gcloud",
                "Extension gcloud",
                "/test-tmp/gcloud",
                None,
                True,
                "gcloud:/test-tmp/gcloud",
            )
        )

        self.assertEqual("builtin:extension:gcloud:/test-tmp/gcloud", value)

    def test_current_built_in_shares_updates_enabled_state(self) -> None:
        values = host_access.current_built_in_shares(
            {"builtin:credentials:ssh"},
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    False,
                )
            ],
        )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                )
            ],
            values,
        )

    def test_current_built_in_shares_updates_all_extension_rows_in_group(self) -> None:
        values = host_access.current_built_in_shares(
            {"builtin:extension:gcloud:/test-tmp/gcloud"},
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/test-tmp/gcloud",
                    None,
                    False,
                    "gcloud:/test-tmp/gcloud",
                ),
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/test-tmp/boto",
                    None,
                    False,
                    "gcloud:/test-tmp/boto",
                ),
            ],
        )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/test-tmp/gcloud",
                    None,
                    True,
                    "gcloud:/test-tmp/gcloud",
                ),
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/test-tmp/boto",
                    None,
                    True,
                    "gcloud:/test-tmp/boto",
                ),
            ],
            values,
        )

    def test_current_docker_option_updates_enabled_state(self) -> None:
        value = host_access.current_docker_option({"docker:socket"}, None)

        self.assertEqual(
            DockerOptionValue("docker", "Docker socket", None, None, True), value
        )

    def test_built_in_group_selection_values_returns_extension_group_rows(self) -> None:
        values = host_access.built_in_group_selection_values(
            "builtin:extension:gcloud:/test-tmp/gcloud",
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/test-tmp/gcloud",
                    None,
                    True,
                    "gcloud:/test-tmp/gcloud",
                ),
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    "/test-tmp/boto",
                    None,
                    True,
                    "gcloud:/test-tmp/boto",
                ),
            ],
        )

        self.assertEqual(
            [
                "builtin:extension:gcloud:/test-tmp/gcloud",
                "builtin:extension:gcloud:/test-tmp/boto",
            ],
            values,
        )

    def test_build_confirmation_request_filters_newly_enabled_values(self) -> None:
        built_in_shares = [
            BuiltInShareValue(
                BuiltInShareSource.CREDENTIALS,
                "ssh",
                "SSH",
                "/test-tmp/.ssh",
                None,
                True,
            ),
            BuiltInShareValue(
                BuiltInShareSource.EXTENSION,
                "gh",
                "Extension gh",
                "/test-tmp/.config/gh",
                False,
                True,
            ),
        ]
        docker_options = [
            DockerOptionValue("docker", "Docker socket", None, True, True),
        ]

        values = host_access._build_confirmation_request(
            built_in_shares, docker_options
        )

        self.assertEqual([], values.docker_options)
        self.assertEqual([], values.git_shares)
        self.assertEqual([built_in_shares[0]], values.credential_shares)
        self.assertEqual([built_in_shares[1]], values.extension_shares)

    def test_merge_confirmed_host_access_applies_confirmed_values(self) -> None:
        built_in_shares = [
            BuiltInShareValue(
                BuiltInShareSource.CREDENTIALS,
                "ssh",
                "SSH",
                "/test-tmp/.ssh",
                None,
                True,
            )
        ]
        docker_options = [
            DockerOptionValue("docker", "Docker socket", None, None, True),
        ]
        confirmed = HostAccessConfirmValues(
            docker_options=[
                DockerOptionValue("docker", "Docker socket", None, None, False),
            ],
            git_shares=[],
            credential_shares=[
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    False,
                )
            ],
            extension_shares=[],
        )

        merged_shares, merged_docker = host_access._merge_confirmed_host_access(
            built_in_shares,
            docker_options,
            confirmed,
        )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    False,
                )
            ],
            merged_shares,
        )
        self.assertEqual(
            [
                DockerOptionValue("docker", "Docker socket", None, None, False),
            ],
            merged_docker,
        )

    def test_apply_host_access_persists_values(self) -> None:
        draft = _build_draft(
            AgentConfig(base="ubuntu"),
            ParsedArgs(False, "", "codex", [], False, []),
        )

        host_access.apply_host_access(
            draft,
            [
                BuiltInShareValue(
                    BuiltInShareSource.CREDENTIALS,
                    "ssh",
                    "SSH",
                    "/test-tmp/.ssh",
                    None,
                    True,
                ),
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gh",
                    "Extension gh",
                    "/test-tmp/.config/gh",
                    None,
                    False,
                ),
            ],
            [CustomShareValue("/test-tmp/logs")],
            [
                DockerOptionValue("docker", "Docker socket", None, None, True),
            ],
        )

        self.assertEqual(["/test-tmp/logs"], draft.agent_cfg.shares)
        self.assertTrue(draft.agent_cfg.mounts.ssh)
        self.assertEqual({"gh": False}, draft.agent_cfg.extension_mounts)
        self.assertTrue(draft.agent_cfg.mounts.docker)
