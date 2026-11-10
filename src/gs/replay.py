"""`gs replay`의 입력 확정: 지난 티켓의 원래 시작 commit과, 그 commit 트리의 티켓·spec. 실행하지 않는 순수 함수만 둔다.

재생은 지난 티켓을 같은 조건에서 다른 worker 모델로 다시 돌려 모델끼리 견주는 수단이다.

**같게 두는 것**
- 시작 commit: 그 티켓 브랜치가 갈라진 integration 지점(`start_commit`). 오늘의 base나 integration이 아니다.
- 티켓 파일과 spec: 시작 commit 트리의 것(`freeze_inputs`). 작업 트리의 파일은 그사이 고쳐졌을 수 있어 읽지 않는다.
- 리뷰어·판단 설정: 티켓 frontmatter의 `reviewer`(`second_reviewer`)와 config의 판단 모델. 같은 눈금으로 재야 모델 차이만 남는다.

**바꾸는 것**
- worker 모델: `--worker <claude|codex>:<모델>/<effort>`가 티켓의 `model`과 tier 표를 대신한다(`parse_worker`).

worker·verify·리뷰 실행, 결과 표, CLI 등록은 `gs replay`(실행 쪽)가 맡는다.
"""
from __future__ import annotations

import math
import re
import subprocess
import tomllib
from dataclasses import dataclass
from pathlib import Path

from . import feature as featmod
from . import frontmatter, git

WORKER_FAMILIES = ("claude", "codex")
_NAME = re.compile(r"[A-Za-z0-9._-]+")
_MODEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]*")


class InvalidValueError(ValueError):
    """옵션 값의 형식이 틀렸다. 메시지에 이유와 올바른 형식이 있다."""


class MissingCommitError(git.GitError):
    """시작 commit을 정할 수 없다(못 찾음·여럿·`--base`가 commit이 아님). 메시지에 `--base` 안내가 있다."""


class MissingFileError(git.GitError):
    """시작 commit 트리에 티켓 파일이나 spec이 없거나 읽을 수 없다."""


@dataclass(frozen=True)
class Worker:
    family: str  # claude | codex
    model: str
    effort: str

    def __str__(self) -> str:
        return f"{self.family}:{self.model}/{self.effort}"


@dataclass(frozen=True)
class Frozen:
    """`freeze_inputs`의 결과. 티켓·spec은 모두 시작 commit 트리의 것이다."""
    commit: str
    ticket_path: Path  # outdir에 쓴 티켓 사본
    spec_path: Path  # outdir에 쓴 spec 사본
    model: str  # 원래 티켓의 worker 계열(재생은 `--worker`가 대신한다)
    reviewer: str
    touches: list[str]
    verify: str  # spec verify
    second_reviewer: str | None = None


def parse_worker(value: str) -> Worker:
    """`<claude|codex>:<모델>/<effort>`. 틀리면 InvalidValueError."""
    shape = "`--worker`는 <claude|codex>:<모델>/<effort> 꼴이어야 한다(예: claude:fable/high)"
    family, colon, rest = value.partition(":")
    if not colon:
        raise InvalidValueError(f"{shape}: {value!r}에 ':'가 없다")
    if family not in WORKER_FAMILIES:
        raise InvalidValueError(f"{shape}: 계열 {family!r}는 {'|'.join(WORKER_FAMILIES)} 중 하나여야 한다")
    model, slash, effort = rest.rpartition("/")
    if not slash:
        raise InvalidValueError(f"{shape}: {value!r}에 '/<effort>'가 없다")
    if not _MODEL.fullmatch(model):
        raise InvalidValueError(f"{shape}: 모델 {model!r}이 비었거나 낱말 밖 글자가 있다")
    if not _NAME.fullmatch(effort):
        raise InvalidValueError(f"{shape}: effort {effort!r}가 비었거나 낱말 밖 글자가 있다")
    return Worker(family, model, effort)


def parse_usage(value: str) -> tuple[float, float]:
    """`<전>,<후>`: 사람이 읽은 `/usage` 주간 %(각 0–100). 틀리면 InvalidValueError."""
    shape = "`--usage`는 <전>,<후> 꼴의 0–100 숫자여야 한다(예: 41,44)"
    parts = value.split(",")
    if len(parts) != 2:
        raise InvalidValueError(f"{shape}: {value!r}에서 쉼표로 나뉜 값이 {len(parts)}개다")
    numbers = []
    for part in parts:
        text = part.strip().removesuffix("%").strip()
        try:
            number = float(text)
        except ValueError:
            raise InvalidValueError(f"{shape}: {part.strip()!r}는 숫자가 아니다") from None
        if not math.isfinite(number) or not 0 <= number <= 100:
            raise InvalidValueError(f"{shape}: {part.strip()!r}는 0–100 밖이다")
        numbers.append(number)
    return numbers[0], numbers[1]


def _check_names(feature: str, ticket_id: str) -> None:
    for what, value in (("feature", feature), ("티켓 id", ticket_id)):
        if not _NAME.fullmatch(value):
            raise MissingFileError(f"{what} 이름이 올바르지 않다: {value!r}")


def _git_remote_base(repo: Path) -> tuple[str, str]:
    """대상 레포 config의 `[git] remote`·`base`. 이름을 가정하지 않는다."""
    path = repo / ".goldstack" / "config.toml"
    try:
        with path.open("rb") as f:
            section = tomllib.load(f).get("git", {})
        return section["remote"], section["base"]
    except (OSError, ValueError, KeyError, TypeError) as e:
        raise MissingCommitError(f"{path}에서 [git] remote·base를 읽을 수 없다({type(e).__name__}: {e}). "
                                 "`--base <sha>`로 시작 commit을 직접 준다") from e


def _commit_of(repo: Path, ref: str) -> str | None:
    cp = git.run(repo, "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}", check=False)
    return cp.stdout.strip() if cp.returncode == 0 and cp.stdout.strip() else None


def start_commit(repo: Path, feature: str, ticket_id: str, base: str | None = None) -> str:
    """티켓 브랜치의 원래 시작 commit(전체 sha). `base`는 `--base <sha>` 덮어쓰기다.

    config `[git] base`(와 그 원격, 이 feature의 integration) 이력에서 `Merge <NN>:` 제목에 `gs-ticket: <feature>/<NN>`
    줄이 있는 병합 커밋 M을 찾는다. M의 둘째 부모에서 첫 부모만 따라가며 M^1에 없는 가장 오래된 커밋의 부모가 시작 commit이다.
    티켓 브랜치에 integration을 합친 커밋이 끼어도 그 둘째 부모는 따라가지 않아 갈림점을 잘못 잡지 않는다
    (`merge-base M^1 M^2`는 합친 integration까지 닿아 더 뒤일 수 있다).
    """
    _check_names(feature, ticket_id)
    if base is not None:
        found = _commit_of(repo, base)
        if found is None:
            raise MissingCommitError(f"--base {base!r}는 이 레포의 commit이 아니다")
        return found
    remote, branch = _git_remote_base(repo)
    integration = f"gs/{feature}/integration"
    refs = [ref for ref in (f"{remote}/{branch}", branch, f"{remote}/{integration}", integration) if _commit_of(repo, ref)]
    hint = f"`--base <sha>`로 시작 commit을 직접 준다(검색한 ref: {', '.join(refs) or '없음'})"
    if not refs:
        raise MissingCommitError(f"{remote}/{branch}도 {integration}도 이 레포에 없어 `Merge {ticket_id}:`를 찾을 수 없다. {hint}")
    log = git.run(repo, "log", "--merges", "--format=%H%x00%P%x00%s%x00%b%x01", *refs).stdout
    subject = re.compile(rf"Merge {re.escape(ticket_id)}:")
    trailer = f"gs-ticket: {feature}/{ticket_id}"
    merges: dict[str, list[str]] = {}
    for record in log.split("\x01"):
        if not record.strip():
            continue
        sha, parents, title, body = record.lstrip("\n").split("\x00", 3)
        if subject.match(title) and any(line.rstrip() == trailer for line in body.splitlines()):
            merges[sha] = parents.split()
    if not merges:
        raise MissingCommitError(f"{feature}/{ticket_id}의 `Merge {ticket_id}:` 커밋이 없다. {hint}")
    if len(merges) > 1:
        shown = ", ".join(sha[:12] for sha in merges)
        raise MissingCommitError(f"{feature}/{ticket_id}의 `Merge {ticket_id}:` 커밋이 {len(merges)}개다({shown}). "
                                 f"그 병합 직전의 시작 commit을 골라 {hint}")
    (merge, parents), = merges.items()
    first, second = parents[0], parents[1]
    # 티켓 브랜치 첫 부모 사슬에서 integration(M^1)에 아직 없는 커밋들. 맨 끝이 가장 오래된 것이다.
    own = git.run(repo, "rev-list", "--first-parent", second, "--not", first).stdout.split()
    if not own:
        raise MissingCommitError(f"{merge[:12]}의 티켓 브랜치 쪽에 이 티켓만의 커밋이 없다. {hint}")
    oldest = own[-1]
    start = _commit_of(repo, f"{oldest}^")
    if start is None:
        raise MissingCommitError(f"{oldest[:12]}에 부모가 없어 시작 commit을 정할 수 없다. {hint}")
    if git.run(repo, "merge-base", "--is-ancestor", start, first, check=False).returncode:
        raise MissingCommitError(f"시작 commit 후보 {start[:12]}가 {merge[:12]}의 첫 부모 이력에 없다. {hint}")
    return start


def _show(repo: Path, commit: str, path: str) -> bytes:
    cp = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=repo, capture_output=True, stdin=subprocess.DEVNULL)
    if cp.returncode:
        raise MissingFileError(f"{commit[:12]} 트리에 {path}가 없다: {cp.stderr.decode('utf-8', 'replace').strip()}")
    return cp.stdout


def freeze_inputs(repo: Path, commit: str, feature: str, ticket_id: str, outdir: Path) -> Frozen:
    """`commit` 트리의 티켓 파일(`tickets/<NN>-*.md`)과 `spec.md`를 `outdir`에 꺼내 쓴다. 작업 트리는 읽지 않는다.

    티켓 frontmatter(model, reviewer, touches)와 spec `verify`를 돌려준다. 없거나 읽을 수 없으면 MissingFileError.
    """
    _check_names(feature, ticket_id)
    sha = _commit_of(repo, commit)
    if sha is None:
        raise MissingFileError(f"{commit!r}는 이 레포의 commit이 아니다")
    work = featmod.work_rel(feature)
    listed = git.run(repo, "ls-tree", "-z", "--name-only", sha, f"{work}/tickets/", check=False).stdout.split("\0")
    names = [Path(line).name for line in listed if Path(line).name.startswith(f"{ticket_id}-") and line.endswith(".md")]
    if not names:
        raise MissingFileError(f"{sha[:12]} 트리의 {work}/tickets/에 {ticket_id}-*.md가 없다")
    if len(names) > 1:
        raise MissingFileError(f"{sha[:12]} 트리의 {work}/tickets/에 {ticket_id}-*.md가 {len(names)}개다: {', '.join(names)}")
    ticket_bytes = _show(repo, sha, f"{work}/tickets/{names[0]}")
    spec_bytes = _show(repo, sha, f"{work}/spec.md")
    try:
        ticket, _ = frontmatter.split(ticket_bytes.decode("utf-8"))
        spec, _ = frontmatter.split(spec_bytes.decode("utf-8"))
    except (frontmatter.FrontmatterError, UnicodeDecodeError) as e:
        raise MissingFileError(f"{sha[:12]} 트리의 티켓·spec frontmatter를 읽을 수 없다: {e}") from e
    for what, data, keys in (("티켓", ticket, ("model", "reviewer")), ("spec", spec, ("verify",))):
        for key in keys:
            if not isinstance(data.get(key), str):
                raise MissingFileError(f"{sha[:12]} 트리의 {what}에 `{key}`가 없거나 문자열이 아니다")
    touches = ticket.get("touches", [])
    if not isinstance(touches, list):
        raise MissingFileError(f"{sha[:12]} 트리의 티켓 `touches`가 목록이 아니다")
    second = ticket.get("second_reviewer")
    outdir.mkdir(parents=True, exist_ok=True)
    ticket_path, spec_path = outdir / names[0], outdir / "spec.md"
    ticket_path.write_bytes(ticket_bytes)
    spec_path.write_bytes(spec_bytes)
    return Frozen(commit=sha, ticket_path=ticket_path, spec_path=spec_path, model=ticket["model"],
                  reviewer=ticket["reviewer"], touches=list(touches), verify=spec["verify"],
                  second_reviewer=second if isinstance(second, str) else None)
