"""설치 메타데이터와 플러그인 버전을 읽고 업데이트 필요 여부를 알린다."""
from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import TextIO


@dataclass(frozen=True)
class Installation:
    version: str
    commit: str | None = None
    url: str | None = None
    plugin_version: str | None = None
    local: bool = False


def installation(repo: Path) -> Installation:
    """VCS 설치만 commit·주소를 가진다. 로컬 디렉터리 설치는 출처로 쓰지 않는다."""
    from . import adapters

    gs_version = metadata.version("goldstack")
    commit = url = None
    local = False
    try:
        dist = metadata.distribution("goldstack")
        data = json.loads(dist.read_text("direct_url.json") or "null")
        if isinstance(data, dict) and isinstance(data.get("vcs_info"), dict):
            vcs = data["vcs_info"]
            if vcs.get("vcs") == "git":
                commit, url = vcs.get("commit_id"), data.get("url")
                commit = commit if isinstance(commit, str) and commit else None
                url = url if isinstance(url, str) and url else None
        elif isinstance(data, dict) and isinstance(data.get("dir_info"), dict):
            local = True
    except (OSError, ValueError, metadata.PackageNotFoundError):
        pass
    plugin_version = None
    try:
        for plugin in adapters.claude_plugins(repo):
            pid, value = plugin.get("id"), plugin.get("version")
            if isinstance(pid, str) and pid.split("@", 1)[0] == adapters.GOLDSTACK_PLUGIN:
                if isinstance(value, str) and value:
                    plugin_version = value
                    break
    except adapters.AdapterError:
        pass
    return Installation(gs_version, commit, url, plugin_version, local)


def warn(repo: Path, out: TextIO) -> None:
    """시작 때만 조회한다. 원격을 읽지 못해도 실행을 막지 않는다."""
    try:
        info = installation(repo)
    except (OSError, ValueError, metadata.PackageNotFoundError):
        return
    if info.local:
        print("경고: 설치 commit 모름(로컬 설치): 뒤처짐을 비교할 수 없다", file=out)
    if info.commit and info.url:
        try:
            env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GIT_ASKPASS="false",
                       SSH_ASKPASS="false", GCM_INTERACTIVE="Never")
            env["GIT_SSH_COMMAND"] = (env.get("GIT_SSH_COMMAND", "ssh")
                                      + " -oBatchMode=yes -oStrictHostKeyChecking=yes")
            cp = subprocess.run(["git", "ls-remote", info.url, "main"], cwd=repo,
                                capture_output=True, text=True, stdin=subprocess.DEVNULL,
                                encoding="utf-8", errors="replace", timeout=5, env=env)
            main = next((line.split()[0] for line in cp.stdout.splitlines()
                         if len(line.split()) == 2 and line.split()[1] == "refs/heads/main"), None)
            if cp.returncode == 0 and main and main != info.commit:
                print("경고: 설치본이 main보다 뒤처짐 → gs self-update", file=out)
        except (OSError, subprocess.TimeoutExpired):
            pass
    if info.plugin_version is not None and info.plugin_version != info.version:
        print(f"경고: 플러그인 {info.plugin_version} ≠ gs {info.version} → gs self-update", file=out)


def valid_requirement(value: str) -> bool:
    """최소 버전 하나만 받는다(예: >=0.1, >=0.1.0)."""
    return re.fullmatch(r">=[0-9]+(?:\.[0-9]+){0,2}", value) is not None


def requirement_error(requires: str) -> str | None:
    if not requires:
        return None
    current = metadata.version("goldstack")

    def parts(value: str) -> tuple[int, ...]:
        numbers = tuple(int(n) for n in value.split("."))
        return numbers + (0,) * (3 - len(numbers))

    if parts(current) < parts(requires[2:]):
        return f"이 레포는 goldstack {requires}가 필요하다(지금 {current}) → gs self-update"
    return None
