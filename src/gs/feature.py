"""feature 디렉터리(`.work/<feature>/`)의 spec과 티켓을 읽는다.

읽기에서 생긴 문제는 예외로 던지지 않고 Problem 목록에 모은다. 한 번에 전부 보여 주기 위해서다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from . import frontmatter

FAMILIES = ("claude", "codex", "agy")
SPEC_REQUIRED = ("feature", "verify")
SPEC_DEFAULTS = {"max_workers": 3, "idle_minutes": 20}
TICKET_KEYS = ("id", "title", "blocked_by", "model", "reviewer")


@dataclass(frozen=True)
class Problem:
    level: str  # "오류" | "경고"
    where: str  # 사람이 읽는 위치(상대 경로)
    message: str

    def __str__(self) -> str:
        return f"{self.level}: {self.where}: {self.message}"


@dataclass
class Spec:
    feature: str
    verify: str
    max_workers: int
    idle_minutes: int
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


@dataclass
class Feature:
    name: str
    root: Path  # .work/<feature>
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
    root = repo / ".work" / name
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
    ints = {}
    for key, default in SPEC_DEFAULTS.items():
        raw = data.get(key, str(default))
        if not (isinstance(raw, str) and raw.isdigit() and int(raw) >= 1):
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
    for key in ("id", "title", "model", "reviewer"):
        if key in data and not isinstance(data[key], str):
            err(f"`{key}`는 문자열이어야 한다")
    if "blocked_by" in data and not isinstance(data["blocked_by"], list):
        err("`blocked_by`는 목록이어야 한다(없으면 [])")
    for key in data.keys() - set(TICKET_KEYS):
        problems.append(Problem("경고", where, f"알 수 없는 키 `{key}`"))
    if any(p.level == "오류" for p in problems[n:]):
        return None  # 형태가 틀리면 그래프에 넣을 수 없다

    tid = data["id"]
    if not path.name.startswith(f"{tid}-"):
        err(f"파일 이름이 `{tid}-`로 시작해야 한다(id와 파일 이름 불일치)")
    for key in ("model", "reviewer"):
        if data[key] not in FAMILIES:
            err(f"`{key}` 값 `{data[key]}`는 {'|'.join(FAMILIES)} 중 하나여야 한다")
    if data["model"] == data["reviewer"]:
        err(f"리뷰는 다른 계열이어야 한다: model과 reviewer가 둘 다 `{data['model']}`")
    deps = data["blocked_by"]
    if len(set(deps)) != len(deps):
        err("`blocked_by`에 같은 id가 두 번 있다")
    # 값 오류가 있어도 그래프에는 넣는다. 빼면 이 티켓을 참조하는 티켓마다 "없는 id" 오류가 덧붙는다.
    return Ticket(id=tid, title=data["title"], blocked_by=list(deps), model=data["model"],
                  reviewer=data["reviewer"], path=path, body=body)
