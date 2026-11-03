"""worker 하나 띄우기: brief와 실행 스크립트를 쓰고, herdr pane이나 subprocess에서 돌린다.

끝은 실행 스크립트가 남기는 exit 파일로 안다(프로세스 종료 = 끝). 화면을 읽어 추측하지 않는다.
worker 명령은 GS_WORKER_CMD로 바꿔 끼울 수 있다(시험 seam).
"""
from __future__ import annotations

import os
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from . import herdr
from .feature import Spec, Ticket

# 09의 hook이 생기기 전까지의 임시 장치. claude 도구 차단으로 push와 gh를 막는다.
CLAUDE_CMD = (
    'claude -p --output-format stream-json --verbose --permission-mode bypassPermissions '
    '--disallowedTools "Bash(git push *)" "Bash(gh *)" < "$GS_BRIEF"'
)
POLL_SECONDS = 2.0


@dataclass
class Job:
    ticket: Ticket
    worktree: Path
    rundir: Path  # .work/<f>/run/NN

    @property
    def brief(self) -> Path:
        return self.rundir / "brief.md"

    @property
    def script(self) -> Path:
        return self.rundir / "run.sh"

    @property
    def log(self) -> Path:
        return self.rundir / "worker.log"

    @property
    def exit_file(self) -> Path:
        return self.rundir / "exit"


def worker_command(ticket: Ticket) -> str:
    override = os.environ.get("GS_WORKER_CMD")
    if override:
        return override
    if ticket.model != "claude":
        raise ValueError(f"model `{ticket.model}` 어댑터는 아직 없다(05)")
    return CLAUDE_CMD


def write_brief(job: Job, spec: Spec, feature: str, branch: str) -> None:
    t = job.ticket
    spec_rel = f".work/{feature}/spec.md"
    ticket_rel = f".work/{feature}/tickets/{t.path.name}"
    job.brief.write_text(f"""# 티켓 {t.id}: {t.title}

너는 goldstack worker다. 이 worktree(`{job.worktree}`, 브랜치 `{branch}`)에서 아래 티켓 하나를 구현한다.

규칙:
- 이 worktree 안의 파일만 바꾼다.
- 끝나면 변경을 이 브랜치에 커밋한다(여러 커밋 가능). 커밋이 없으면 실패로 처리된다.
- push, PR 생성, 병합은 하지 않는다. gs가 한다.
- 검증 명령 `{spec.verify}`를 커밋 전에 돌려 통과시킨다. gs가 다시 돌려 확인한다.
- 사람에게 묻지 않는다. 막히면 이유를 마지막 메시지에 적고 끝낸다.
- 완료 조건이 이 티켓의 명세다. 범위 밖은 건드리지 않는다.

참고: feature spec `{spec_rel}`, 티켓 파일 `{ticket_rel}` (둘 다 이 worktree 안에 있다)

---
{t.body.strip()}
""", encoding="utf-8")


def write_script(job: Job, command: str) -> None:
    """worker를 돌리고 종료 코드를 exit 파일에 원자적으로 남기는 bash 스크립트."""
    q = shlex.quote
    env = {
        "GS_ROLE": "worker",
        "GS_TICKET": job.ticket.id,
        "GS_BRIEF": str(job.brief),
        "GS_WORKTREE": str(job.worktree),
    }
    exports = "\n".join(f"export {k}={q(v)}" for k, v in env.items())
    job.script.write_text(f"""#!/bin/bash
# gs가 만든 worker 실행 스크립트. 티켓 값은 모두 shlex.quote로 넣는다(제목이 셸 코드로 실행되지 않게)
set -o pipefail
unset CLAUDECODE CLAUDE_CODE_ENTRYPOINT
{exports}
cd {q(str(job.worktree))} || {{ echo 127 > {q(str(job.exit_file))}; exit 127; }}
echo {q(f"■ gs worker {job.ticket.id}: {job.ticket.title}")}
( {command} ) 2>&1 | tee -a {q(str(job.log))} | {q(sys.executable)} -m gs.streamfmt
code=${{PIPESTATUS[0]}}
echo "$code" > {q(str(job.exit_file))}.tmp && mv {q(str(job.exit_file))}.tmp {q(str(job.exit_file))}
echo {q(f"■ gs worker {job.ticket.id} 끝: 종료 코드")} "$code"
""", encoding="utf-8")


def read_exit(job: Job) -> int | None:
    try:
        return int(job.exit_file.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None


class SubprocessRunner:
    """pane 없이 바로 실행. 시험과 herdr 밖에서 쓴다. 손잡이는 Popen."""
    name = "subprocess"

    def start(self, job: Job, label: str) -> tuple[subprocess.Popen, str]:
        proc = subprocess.Popen(["bash", str(job.script)], stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc, f"pid {proc.pid}"

    def alive(self, proc: subprocess.Popen) -> bool:
        return proc.poll() is None

    def finish(self, proc: subprocess.Popen, ok: bool) -> None:
        pass


class HerdrRunner:
    """feature마다 탭 하나(`gs:<feature>`)에 worker pane을 모은다. 손잡이는 pane id.

    worker마다 새 pane(새 셸)을 연다. 남은 입력이 다음 실행을 깨는 일이 없게(ORIGINS 실패 15).
    첫 worker는 탭을 만들어 그 root pane을, 다음 worker는 탭에 열린 pane을 나눠 쓴다.
    성공하면 pane을 닫고, 실패하면 들여다볼 수 있게 남긴다. 탭의 pane이 모두 닫혀 탭이 사라지면 다음에 새로 만든다.
    """
    name = "herdr"

    def __init__(self, cwd: Path, feature: str):
        self.sess = herdr.session()
        self.feature = feature
        ws = os.environ.get("HERDR_WORKSPACE_ID")
        self.workspace = ws or herdr.workspace_create(self.sess, cwd, f"gs:{feature}")["workspace"]["workspace_id"]
        self.tab: str | None = None
        self.panes: list[str] = []  # 이 탭에 열려 있는 gs pane. 끝이 가장 최근

    def _open_pane(self, job: Job) -> str:
        while self.panes:
            target = self.panes[-1]
            direction = "right" if len(self.panes) % 2 else "down"  # 한 방향으로만 나누면 너무 좁아진다
            try:
                return herdr.pane_split(self.sess, target, job.worktree, direction)["pane"]["pane_id"]
            except herdr.HerdrError:
                self.panes.pop()  # 사람이 닫았거나 탭이 사라졌다
        res = herdr.tab_create(self.sess, self.workspace, job.worktree, f"gs:{self.feature}")
        self.tab = res["tab"]["tab_id"]
        return res["root_pane"]["pane_id"]

    def start(self, job: Job, label: str) -> tuple[str, str]:
        pane = self._open_pane(job)
        self.panes.append(pane)
        herdr.pane_run(self.sess, pane, f"bash {shlex.quote(str(job.script))}")
        return pane, f"pane {pane}"

    def alive(self, pane: str) -> bool:
        try:
            herdr.pane_get(self.sess, pane)
            return True
        except herdr.HerdrError:
            return False

    def finish(self, pane: str, ok: bool) -> None:
        if not ok:
            return
        try:
            herdr.pane_close(self.sess, pane)
        except herdr.HerdrError:
            pass
        if pane in self.panes:
            self.panes.remove(pane)


def make_runner(cwd: Path, feature: str):
    choice = os.environ.get("GS_RUNNER")
    if choice == "subprocess" or (choice is None and not herdr.available()):
        return SubprocessRunner()
    return HerdrRunner(cwd, feature)


def poll_interval(runner) -> float:
    return POLL_SECONDS if runner.name == "herdr" else 0.05


class Proc:
    """띄운 worker 하나. poll()은 기다리지 않는다: 끝났으면 종료 코드, 실행기가 사라졌으면 -1, 아니면 None."""

    def __init__(self, job: Job, runner, label: str):
        job.rundir.mkdir(parents=True, exist_ok=True)
        job.exit_file.unlink(missing_ok=True)
        self.job = job
        self.runner = runner
        self.handle, self.where = runner.start(job, label)
        self._gone_since: float | None = None

    def poll(self) -> int | None:
        code = read_exit(self.job)
        if code is not None:
            return code
        if self.runner.alive(self.handle):
            self._gone_since = None
            return None
        # 실행기가 끝난 직후 exit 파일이 늦게 보일 수 있어 조금 더 기다린다
        self._gone_since = self._gone_since or time.monotonic()
        if time.monotonic() - self._gone_since > 2 * POLL_SECONDS:
            return -1
        return None

    def finish(self, ok: bool) -> None:
        self.runner.finish(self.handle, ok)
