"""gs가 worker hook 밖에서 실행하는 worktree 준비 명령.

준비에 성공하면 산출물과 함께 그때의 HEAD를 git 관리 디렉터리에 남긴다(remember). config `[worktree] setup_when`이
있으면 integration은 그 커밋과 검증할 트리를 대조해(stale) 걸리는 파일이 다르면 준비를 다시 한다(go._merge_stage).
"""
from __future__ import annotations

import fnmatch
import json
import subprocess
from collections.abc import Sequence
from pathlib import Path

from . import git, verify

WARNING = "경고: setup이 추적 파일을 바꿨다 → 되돌림: "


def warnings(logs) -> list[str]:
    """지난 시도도 포함해 로그의 복구 경고를 보고서에 보존한다."""
    return list(dict.fromkeys(line for log in sorted(logs)
                              for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                              if line.startswith(WARNING)))


def _restore_tracked(wt: Path) -> str:
    entries = iter(git.run(wt, "status", "--porcelain", "-z").stdout.split("\0"))
    paths = []
    for entry in entries:
        if not entry or entry.startswith("?? "):
            continue
        paths.append(entry[3:])
        if "R" in entry[:2] or "C" in entry[:2]:
            paths.append(next(entries))  # -z의 rename은 새 경로, 이전 경로 순서다.
    paths = list(dict.fromkeys(paths))
    if not paths:
        return ""
    original = set(git.run(wt, "ls-tree", "-r", "--name-only", "-z", "HEAD").stdout.split("\0"))
    # setup이 stage까지 했더라도 되돌린다. 새 설치 파일은 untracked로 남긴다.
    git.run(wt, "--literal-pathspecs", "reset", "-q", "HEAD", "--", *paths)
    tracked = [p for p in paths if p in original]
    if not tracked:
        return ""
    git.run(wt, "--literal-pathspecs", "checkout", "--", *tracked)
    names = [json.dumps(p, ensure_ascii=False) if any(c in p for c in "\r\n\t") else p for p in tracked]
    return WARNING + ", ".join(names)


def marker(wt: Path) -> Path:
    """worktree별 git 관리 디렉터리에 둔다. reset·clean에도 남고 새 worktree에는 없다."""
    return Path(git.out(wt, "rev-parse", "--absolute-git-dir")) / "gs-setup-done"


def _prepared(wt: Path) -> Path:
    """마지막으로 준비에 성공한 커밋. 표지 옆에 따로 둔다: 옛 gs의 표지는 그대로 읽힌다."""
    return marker(wt).with_name("gs-setup-head")


def remember(wt: Path) -> None:
    """준비 성공과 산출물을 함께 저장한다. gitignore에 없는 설치 파일도 clean으로 지우지 않는다. 준비한 커밋(HEAD)도 남긴다."""
    paths = git.run(wt, "ls-files", "--others", "--exclude-standard", "-z").stdout.split("\0")
    marker(wt).write_text(json.dumps([p for p in paths if p]), encoding="utf-8")
    _prepared(wt).write_text(git.out(wt, "rev-parse", "HEAD"), encoding="utf-8")


def matches(globs: Sequence[str], path: str) -> bool:
    """레포 루트 기준 경로가 glob 하나에라도 걸리나. `*`·`?`·`[...]`는 `/`를 넘지 않고, `**` 한 칸은 0단계 이상이다."""
    parts = path.split("/")
    return any(_match(glob.split("/"), parts) for glob in globs)


def _match(pattern: list[str], parts: list[str]) -> bool:
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(_match(pattern[1:], parts[i:]) for i in range(len(parts) + 1))
    return bool(parts) and fnmatch.fnmatchcase(parts[0], pattern[0]) and _match(pattern[1:], parts[1:])


def stale(wt: Path, globs: Sequence[str], tree: str) -> str:
    """마지막 준비 뒤 tree까지 globs에 걸리는 파일이 바뀌었으면 그 이유(걸린 파일), 그대로면 빈 문자열. globs가 비면 늘 빈 문자열이다.

    준비한 커밋의 기록이 없거나(옛 gs가 준비했다, 준비가 실패했거나 중간에 끝났다) 그 커밋을 읽지 못하면 환경이 tree에 맞는지 모른다. 그것도 이유다.
    """
    if not globs:
        return ""
    try:
        head = _prepared(wt).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        head = ""
    if not head:
        return "준비한 커밋 기록 없음"
    res = git.run(wt, "diff-tree", "-r", "--no-renames", "--name-only", "-z", head, tree, check=False)
    if res.returncode:
        return f"준비한 커밋 {head[:8]}을 읽지 못함"
    return ", ".join(path for path in res.stdout.split("\0") if path and matches(globs, path))


def _artifacts(wt: Path) -> list[str]:
    try:
        return json.loads(marker(wt).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []


def clean(wt: Path, *options: str) -> None:
    excludes = []
    for path in _artifacts(wt):
        # gitignore 패턴 문자를 이스케이프해 준비 때 있었던 정확한 파일만 보호한다.
        literal = "".join("\\" + c if c in "\\*?[]" else c for c in path)
        excludes.extend(("-e", "/" + literal))
    git.run(wt, "clean", *options, *excludes)


def discard_artifacts(wt: Path) -> None:
    """worktree 제거 전에 기억한 untracked 산출물만 지운다. 새 변경은 git이 지킨다."""
    if paths := _artifacts(wt):
        git.run(wt, "--literal-pathspecs", "clean", "-f", "--", *paths)


def is_clean(wt: Path, *, staged_ok: bool = False) -> bool:
    """staged_ok: 미완 병합의 트리를 볼 때. index의 변경은 괜찮고, index와 다른 파일·untracked만 더럽다고 본다."""
    artifacts = set(_artifacts(wt))
    # --no-renames: -z의 이름 변경 항목은 옛 이름이 따로 붙어 항목을 하나씩 읽을 수 없다
    entries = git.run(wt, "status", "--porcelain", "--no-renames", "--untracked-files=all", "-z").stdout.split("\0")
    return all(not entry or (entry.startswith("?? ") and entry[3:] in artifacts) or (staged_ok and entry[1] == " ")
               for entry in entries)


def run(cfg, wt: Path, log: Path, *, note: str = "") -> verify.Result:
    """bash -c로 준비하고 verify와 같은 방식으로 시간 초과·중단 시 자손까지 끝낸다.

    note가 있으면 log를 덮지 않고 그 줄로 시작해 이어 쓴다: 같은 시도 디렉터리의 앞 준비 기록(티켓 worktree의 준비)을 남긴다.
    명령이 뜨면 준비한 커밋의 기록을 지운다. 성공해 remember가 다시 쓰기 전에는 환경이 어느 커밋의 것인지 모른다(stale).
    """
    seconds = cfg.timeouts.setup_minutes * 60
    limit = verify.minutes(seconds)
    if not cfg.worktree.setup.strip():
        return verify.Result(0, False, limit)
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a" if note else "w", encoding="utf-8") as stream:
        if note:
            stream.write(f"\n{note}\n")
            stream.flush()  # 준비 명령이 같은 파일에 이어 쓴다
        try:
            p = subprocess.Popen(["bash", "-c", cfg.worktree.setup], cwd=wt, stdin=subprocess.DEVNULL,
                                 stdout=stream, stderr=subprocess.STDOUT, env=verify.env(), start_new_session=True)
        except OSError as e:
            stream.write(f"준비 명령 실행 실패: {e}\n")
            return verify.Result(1, False, limit)
        try:
            _prepared(wt).unlink(missing_ok=True)
            result = verify.Result(p.wait(timeout=seconds), False, limit)
        except subprocess.TimeoutExpired:
            result = verify.Result(verify.stop(p), True, limit)
            stream.write(f"\n시간 초과: {limit}분\n")
        except BaseException:
            verify.stop(p)
            raise
        finally:
            if warning := _restore_tracked(wt):
                stream.write(f"\n{warning}\n")
                print(warning, flush=True)
        stream.write(f"\n종료 코드: {result.code}\n")
    return result
