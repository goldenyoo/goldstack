"""feature 디렉터리(`.goldstack/work/<feature>/`)의 spec과 티켓을 읽는다.

읽기에서 생긴 문제는 예외로 던지지 않고 Problem 목록에 모은다. 한 번에 전부 보여 주기 위해서다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath, PureWindowsPath

from . import frontmatter

FAMILIES = ("claude", "codex", "agy")
SPEC_REQUIRED = ("feature", "verify")
SPEC_DEFAULTS = {"max_workers": 3, "idle_minutes": 20, "verify_minutes": 20}
TICKET_KEYS = ("id", "title", "blocked_by", "model", "reviewer")
TICKET_OPTIONAL = ("touches", "second_reviewer")
WORK = ".goldstack/work"  # 대상 레포 루트 기준 feature 디렉터리들의 부모


def work_rel(name: str) -> str:
    """레포 루트 기준 feature 디렉터리 경로(문자열). 사람에게 보이는 경로와 git 경로 인자에 쓴다."""
    return f"{WORK}/{name}"


def work_dir(repo: Path, name: str) -> Path:
    return repo / WORK / name


@dataclass(frozen=True)
class Problem:
    level: str  # "오류" | "경고"
    where: str  # 사람이 읽는 위치(상대 경로)
    message: str

    def __str__(self) -> str:
        where = f"{self.where}: " if self.where else ""
        return f"{self.level}: {where}{self.message}"


@dataclass
class Spec:
    feature: str
    verify: str
    max_workers: int
    idle_minutes: int
    verify_minutes: int
    path: Path


@dataclass
class Ticket:
    id: str
    title: str
    blocked_by: list[str]
    model: str
    reviewer: str
    path: Path
    body: str = ""
    touches: list[str] = field(default_factory=list)
    second_reviewer: str | None = None


@dataclass
class Feature:
    name: str
    root: Path  # .goldstack/work/<feature>
    spec: Spec | None
    tickets: dict[str, Ticket] = field(default_factory=dict)
    problems: list[Problem] = field(default_factory=list)

    @property
    def errors(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "오류"]

    @property
    def warnings(self) -> list[Problem]:
        return [p for p in self.problems if p.level == "경고"]


def find_repo_root(start: Path) -> Path | None:
    for d in (start, *start.parents):
        if (d / ".git").exists():
            return d
    return None


def load(repo: Path, name: str) -> Feature:
    root = work_dir(repo, name)
    feat = Feature(name=name, root=root, spec=None)
    if not root.is_dir():
        feat.problems.append(Problem("오류", rel(root, repo), "feature 디렉터리가 없다"))
        return feat
    feat.spec = _load_spec(root / "spec.md", name, repo, feat.problems)
    tdir = root / "tickets"
    if not tdir.is_dir():
        feat.problems.append(Problem("오류", rel(tdir, repo), "tickets 디렉터리가 없다"))
        return feat
    paths = sorted(tdir.glob("*.md"))
    if not paths:
        feat.problems.append(Problem("오류", rel(tdir, repo), "티켓이 없다"))
    for path in paths:
        t = _load_ticket(path, repo, feat.problems)
        if t is None:
            continue
        if t.id in feat.tickets:
            other = rel(feat.tickets[t.id].path, repo)
            feat.problems.append(Problem("오류", rel(path, repo), f"id {t.id}가 {other}와 겹친다"))
            continue
        feat.tickets[t.id] = t
    return feat


def rel(path: Path, repo: Path) -> str:
    try:
        return str(path.relative_to(repo))
    except ValueError:
        return str(path)


def _read(path: Path, repo: Path, problems: list[Problem]):
    where = rel(path, repo)
    try:
        return frontmatter.split(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        problems.append(Problem("오류", where, "파일이 없다"))
    except frontmatter.FrontmatterError as e:
        problems.append(Problem("오류", f"{where}:{e.line}", e.message))
    return None


def _load_spec(path: Path, name: str, repo: Path, problems: list[Problem]) -> Spec | None:
    got = _read(path, repo, problems)
    if got is None:
        return None
    data, _ = got
    where = rel(path, repo)
    ok = True
    for key in SPEC_REQUIRED:
        if not isinstance(data.get(key), str):
            problems.append(Problem("오류", where, f"`{key}`가 없거나 문자열이 아니다"))
            ok = False
    if isinstance(data.get("feature"), str) and data["feature"] != name:
        problems.append(Problem("오류", where, f"feature `{data['feature']}`가 디렉터리 이름 `{name}`과 다르다"))
        ok = False
    verify = data.get("verify")
    if isinstance(verify, str) and (not verify.strip() or "\n" in verify or "\r" in verify):
        # 빈 명령은 `sh -c ""`로 늘 성공해서 검증이 조용히 사라진다
        problems.append(Problem("오류", where, "`verify`는 비어 있지 않은 한 줄 셸 명령이어야 한다"))
        ok = False
    ints = {}
    for key, default in SPEC_DEFAULTS.items():
        raw = data.get(key, str(default))
        if not (isinstance(raw, str) and re.fullmatch(r"[0-9]+", raw) and int(raw) >= 1):
            problems.append(Problem("오류", where, f"`{key}`는 1 이상의 정수여야 한다: {raw!r}"))
            ok = False
            continue
        ints[key] = int(raw)
    for key in data.keys() - set(SPEC_REQUIRED) - set(SPEC_DEFAULTS):
        problems.append(Problem("경고", where, f"알 수 없는 키 `{key}`"))
    if not ok:
        return None
    return Spec(feature=data["feature"], verify=data["verify"], path=path, **ints)


def _load_ticket(path: Path, repo: Path, problems: list[Problem]) -> Ticket | None:
    got = _read(path, repo, problems)
    if got is None:
        return None
    data, body = got
    where = rel(path, repo)
    n = len(problems)

    def err(msg: str) -> None:
        problems.append(Problem("오류", where, msg))

    for key in TICKET_KEYS:
        if key not in data:
            err(f"`{key}`가 없다")
    for key in ("id", "title", "model", "reviewer", "second_reviewer"):
        if key in data and not isinstance(data[key], str):
            err(f"`{key}`는 문자열이어야 한다")
    if "blocked_by" in data and not isinstance(data["blocked_by"], list):
        err("`blocked_by`는 목록이어야 한다(없으면 [])")
    for key in data.keys() - set(TICKET_KEYS) - set(TICKET_OPTIONAL):
        problems.append(Problem("경고", where, f"알 수 없는 키 `{key}`"))
    if any(p.level == "오류" for p in problems[n:]):
        return None  # 형태가 틀리면 그래프에 넣을 수 없다

    tid = data["id"]
    if not path.name.startswith(f"{tid}-"):
        err(f"파일 이름이 `{tid}-`로 시작해야 한다(id와 파일 이름 불일치)")
    for key in ("model", "reviewer", "second_reviewer"):
        if key in data and data[key] not in FAMILIES:
            err(f"`{key}` 값 `{data[key]}`는 {'|'.join(FAMILIES)} 중 하나여야 한다")
    if data["model"] == data["reviewer"]:
        err(f"리뷰는 다른 계열이어야 한다: model과 reviewer가 둘 다 `{data['model']}`")
    second_reviewer = data.get("second_reviewer")
    for key in ("model", "reviewer"):
        if second_reviewer is not None and second_reviewer == data[key]:
            err(f"리뷰는 다른 계열이어야 한다: {key}과 second_reviewer가 둘 다 `{second_reviewer}`")
    deps = data["blocked_by"]
    if len(set(deps)) != len(deps):
        err("`blocked_by`에 같은 id가 두 번 있다")
    touches = data.get("touches", [])
    if not isinstance(touches, list):
        err("`touches`는 문자열 목록이어야 한다(없으면 [])")
        touches = []
    valid_touches = []
    for value in touches:
        if (not isinstance(value, str) or not value.strip()
                or PurePosixPath(value).is_absolute() or PureWindowsPath(value).is_absolute()
                or ".." in value.replace("\\", "/").split("/")):
            err(f"`touches`는 비어 있지 않은 레포 루트 기준 경로여야 한다(절대 경로·.. 금지): {value!r}")
        else:
            valid_touches.append(value)
    # 값 오류가 있어도 그래프에는 넣는다. 빼면 이 티켓을 참조하는 티켓마다 "없는 id" 오류가 덧붙는다.
    return Ticket(id=tid, title=data["title"], blocked_by=list(deps), model=data["model"],
                  reviewer=data["reviewer"], path=path, body=body, touches=valid_touches,
                  second_reviewer=second_reviewer)
