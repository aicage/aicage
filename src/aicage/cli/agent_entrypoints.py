import sys

from aicage.cli.entrypoint import main


def amp() -> int:
    return _run_agent("amp")


def claude() -> int:
    return _run_agent("claude")


def codex() -> int:
    return _run_agent("codex")


def _run_agent(agent: str) -> int:
    return main(["--acp-wsl", agent, *sys.argv[1:]])
