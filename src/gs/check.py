"""spec과 티켓 그래프 검사. `gs check`와 `gs go`가 같이 쓴다."""
from __future__ import annotations

import re
import shutil
from pathlib import Path
from urllib.parse import urlsplit

from . import feature as featmod
from . import config, git, graph


def is_github(url: str) -> bool:
    if "://" in url:
        try:
            return urlsplit(url).hostname == "github.com"
        except ValueError:
            return False
    # git@github.com:owner/repo.git (scp 문법). 로컬 경로 속 github.com은 호스트가 아니다.
    return re.match(r"^(?:[^/@:]+@)?github\.com:", url, re.IGNORECASE) is not None


def environment_problems(repo: Path, cfg: config.Config, feat: featmod.Feature,
                         scope: dict[str, list[str]]) -> list[featmod.Problem]:
    required = {"git", "gh"}
    for tid in scope:
        t = feat.tickets[tid]
        required.update((t.model, t.reviewer))
    problems = [featmod.Problem("오류", "", f"필요한 CLI `{name}`가 PATH에 없다")
                for name in sorted(required) if shutil.which(name) is None]
    if shutil.which("git") is not None:
        remote = git.run(repo, "remote", "get-url", cfg.git.remote, check=False)
        url = remote.stdout.strip()
        if remote.returncode == 0 and url and not is_github(url):
            problems.append(featmod.Problem("경고", "", f"원격 {url}은 GitHub가 아니다. PR·병합은 gh로만 한다"))
    return problems


def check(repo: Path, name: str, only: list[str] | None = None) -> tuple[featmod.Feature, list[str]]:
    """feature를 읽고 그래프까지 검사한다. (feature, 출력할 요약 줄) — 문제는 feature.problems에 쌓인다."""
    cfg, problems = config.load(repo)
    if cfg is None:
        return featmod.Feature(name=name, root=featmod.work_dir(repo, name), spec=None, problems=problems), []
    feat = featmod.load(repo, name)
    feat.problems[:0] = problems
    g = {t.id: t.blocked_by for t in feat.tickets.values()}

    def err(tid: str, msg: str) -> None:
        feat.problems.append(featmod.Problem("오류", featmod.rel(feat.tickets[tid].path, repo), msg))

    for tid, missing in graph.unknown_refs(g).items():
        err(tid, f"blocked_by에 없는 티켓이 있다: {', '.join(missing)}")
    for path in graph.cycles(g):
        err(path[0], "순환: " + " → ".join(path) + " (화살표는 blocked_by 방향)")

    lines: list[str] = []
    if only is not None:
        if not only:
            feat.problems.append(featmod.Problem("오류", "--only", "티켓 id가 비어 있다"))
            return feat, lines
        g, external, missing = graph.subgraph(g, only)
        if missing:
            feat.problems.append(featmod.Problem("오류", "--only", f"없는 티켓: {', '.join(missing)}"))
        lines.append("범위: " + " ".join(sorted(g)))
        if external:
            ext = ", ".join(f"{t} ← {' '.join(ds)}" for t, ds in external.items())
            lines.append(f"범위 밖 의존(끝났다고 가정): {ext}")
    feat.problems.extend(environment_problems(repo, cfg, feat, g))
    lines.append("순서: " + " ".join(graph.topo_order(g)))
    lines.append("지금 시작 가능: " + " ".join(graph.frontier(g)))
    return feat, lines
