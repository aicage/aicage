from pathlib import Path
from unittest import TestCase, mock

from aicage.cli_types import ParsedArgs
from aicage.config.project_config import AgentConfig, _ProjectConfig
from aicage.config.run_config_draft import _create_run_config_draft
from aicage.runtime.menu.textual._models import BuiltInShareSource, BuiltInShareValue
from aicage.runtime.menu.textual.services import _share_support

from ..._test_support import _build_context, _build_draft


class ShareSupportTests(TestCase):
    def test_is_inherited_mount_locks_only_enabled_mounts(self) -> None:
        self.assertTrue(_share_support._is_inherited_mount(None, True))
        self.assertFalse(_share_support._is_inherited_mount(None, False))

    def test_built_in_share_values_allows_enabling_inherited_disabled_extension(
        self,
    ) -> None:
        project_path = Path.cwd()
        draft = _create_run_config_draft(
            project_path,
            "codex",
            _ProjectConfig(path=str(project_path), agents={}),
            ParsedArgs(False, "", "codex", [], False, []),
            _ProjectConfig(
                path=str(project_path),
                agents={
                    "codex": AgentConfig(
                        extensions=["gh"], extension_mounts={"gh": False}
                    )
                },
            ),
        )

        values = _share_support.built_in_share_values(
            draft, _build_context().extensions
        )

        extension_value = next(value for value in values if value.key == "gh")
        self.assertFalse(extension_value.enabled)
        self.assertFalse(extension_value.inherited)

    def test_normalize_shares_from_editor_returns_normalized_values(self) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu"),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )

        values = _share_support.normalize_shares_from_editor(draft, ["logs:ro"])

        self.assertEqual([f"{Path.cwd() / 'logs'}:ro"], values)

    def test_built_in_share_values_returns_only_relevant_items(self) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu"),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )
        with (
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_git_config_path",
                return_value=Path("/test-tmp/gitconfig"),
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_git_root",
                return_value=Path("/repo"),
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support._has_ssh_keys",
                return_value=False,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.has_gpg_keys",
                return_value=False,
            ),
            mock.patch("pathlib.Path.exists", return_value=True),
        ):
            values = _share_support.built_in_share_values(
                draft, _build_context().extensions
            )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "gitconfig",
                    "Git config",
                    str(Path("/test-tmp/gitconfig")),
                    None,
                    True,
                ),
                BuiltInShareValue(
                    BuiltInShareSource.GIT_SUPPORT,
                    "gitroot",
                    "Git root",
                    str(Path("/repo")),
                    None,
                    True,
                ),
            ],
            values,
        )

    def test_built_in_share_values_include_selected_extension_shares(self) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu", extensions=["gh"]),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )

        values = _share_support.built_in_share_values(
            draft, _build_context().extensions
        )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gh",
                    "Extension gh",
                    str(Path.home().resolve() / ".config/gh"),
                    None,
                    True,
                )
            ],
            [item for item in values if item.source == BuiltInShareSource.EXTENSION],
        )

    def test_built_in_share_values_split_multiple_extension_shares_into_rows(
        self,
    ) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu", extensions=["gcloud"]),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )

        values = _share_support.built_in_share_values(
            draft, _build_context().extensions
        )

        self.assertEqual(
            [
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    str(Path.home().resolve() / ".config/gcloud"),
                    None,
                    True,
                    f"gcloud:{Path.home().resolve() / '.config/gcloud'}",
                ),
                BuiltInShareValue(
                    BuiltInShareSource.EXTENSION,
                    "gcloud",
                    "Extension gcloud",
                    str(Path.home().resolve() / ".boto"),
                    None,
                    True,
                    f"gcloud:{Path.home().resolve() / '.boto'}",
                ),
            ],
            [item for item in values if item.source == BuiltInShareSource.EXTENSION],
        )

    def test_built_in_share_values_includes_ssh_mount_when_keys_are_available(
        self,
    ) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu"),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )
        with (
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_git_config_path",
                return_value=None,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_git_root",
                return_value=None,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support._has_ssh_keys",
                return_value=True,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.has_gpg_keys",
                return_value=False,
            ),
        ):
            values = _share_support.built_in_share_values(
                draft, _build_context().extensions
            )

        self.assertIn(
            BuiltInShareValue(
                BuiltInShareSource.CREDENTIALS,
                "ssh",
                "SSH keys",
                "SSH socket",
                None,
                True,
            ),
            values,
        )

    def test_built_in_share_values_includes_gnupg_mount_when_keys_are_available(
        self,
    ) -> None:
        draft = _build_draft(
            agent_cfg=AgentConfig(base="ubuntu"),
            parsed=ParsedArgs(False, "", "codex", [], False, []),
            project_path=Path.cwd(),
        )
        with (
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_git_config_path",
                return_value=None,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_git_root",
                return_value=None,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support._has_ssh_keys",
                return_value=False,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.has_gpg_keys",
                return_value=True,
            ),
            mock.patch(
                "aicage.runtime.menu.textual.services._share_support.resolve_gpg_home",
                return_value=Path("/test-tmp/gnupg"),
            ),
        ):
            values = _share_support.built_in_share_values(
                draft, _build_context().extensions
            )

        self.assertIn(
            BuiltInShareValue(
                BuiltInShareSource.CREDENTIALS,
                "gnupg",
                "GnuPG keys",
                "GnuPG socket",
                None,
                True,
            ),
            values,
        )
