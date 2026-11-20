import os
import stat
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from aicage.config.agent.models import AgentMetadata
from aicage.constants import VERSION_CHECK_IMAGE
from aicage.docker.query import local_image_exists
from aicage.registry.agent_build.agent_version.checker import AgentVersionChecker

from ._helpers import require_integration

pytestmark = pytest.mark.integration


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    current = path.stat().st_mode
    path.chmod(current | stat.S_IEXEC)


def _write_npm_shim(bin_dir: Path) -> None:
    shim = "\n".join(
        [
            "#!/bin/bash",
            "set -euo pipefail",
            "echo 'npm: command not found' >&2",
            "exit 127",
        ]
    )
    _write_executable(bin_dir / "npm", shim)


def test_version_check_falls_back_to_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    require_integration()
    home_dir = tmp_path / "home"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    with tempfile.TemporaryDirectory(dir=Path.cwd()) as temp_dir:
        temp_path = Path(temp_dir)
        bin_dir = temp_path / "bin"
        bin_dir.mkdir()
        _write_npm_shim(bin_dir)
        original_path = os.environ.get("PATH", "")
        monkeypatch.setenv("PATH", f"{bin_dir}:{original_path}")

        agent_dir = temp_path / "agent"
        agent_dir.mkdir()
        version_sh = "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "npm --version",
            ]
        )
        _write_executable(agent_dir / "version.sh", version_sh)

        checker = AgentVersionChecker()
        result = checker.get_version(
            "npm-agent",
            AgentMetadata(
                agent_path_files=[],
                agent_path_directories=["~/.npm-agent"],
                agent_full_name="Npm Agent",
                agent_homepage="https://example.com",
                build_local=True,
                valid_bases={},
                local_definition_dir=agent_dir,
            ),
            agent_dir,
            reporter=mock.Mock(),
        )

        assert result
        assert local_image_exists(VERSION_CHECK_IMAGE)
