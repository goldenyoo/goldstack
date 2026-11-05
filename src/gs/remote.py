"""herdr 원격 준비 검사. 비밀 값·인증 출력은 전송하지 않고 판정만 돌려받는다."""
from __future__ import annotations

import base64
import json
import os
import shlex
import shutil
import subprocess
import time
import uuid
import zlib
from importlib import metadata
from pathlib import Path
from typing import TextIO

from . import adapters, config, herdr, version

TIMEOUT = 90
MIN_FREE = 1024 ** 3  # 최소 1 GiB. worker 산출물을 위한 여유 공간.
GUIDE = "docs/guide.md의 tmux 절"

# 원격 python3는 gs의 실행 환경과 독립적으로 준비 상태를 검사한다.
# CLI 출력에는 인증 정보가 있을 수 있어 정해진 버전·참/거짓만 결과에 싣는다.
PROBE = r'''
import json, os, shutil, subprocess, sys
from pathlib import Path
repo, commit, minimum = sys.argv[1:]
p = Path(repo).expanduser()
valid = p.is_dir() and (p / '.git').exists()
cwd = str(p) if valid else None

def run(args):
    try:
        cp = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=8,
                            env=dict(os.environ, GIT_TERMINAL_PROMPT='0', GIT_ASKPASS='false',
                                     SSH_ASKPASS='false', GCM_INTERACTIVE='Never'))
        return cp.returncode == 0, cp.stdout.strip()
    except (OSError, subprocess.TimeoutExpired, UnicodeError):
        return False, ''

def ver(args):
    ok, text = run(args)
    return text.splitlines()[0] if ok and text else None

result = {'repo': valid, 'env': valid and (p / '.goldstack/local.env').is_file()}
result['gs'] = ver(['gs', '--version'])
result['plugin'] = None
ok, text = run(['claude', 'plugin', 'list', '--json'])
if ok:
    try:
        plugins = json.loads(text)
        if isinstance(plugins, list):
            for item in plugins:
                if (isinstance(item, dict) and str(item.get('id', '')).split('@')[0] == 'goldstack'
                        and item.get('enabled', True) is not False):
                    result['plugin'] = item.get('version')
                    break
    except ValueError:
        pass
for name, args in [('gh', ['gh', 'auth', 'status']),
                   ('claude', ['claude', 'auth', 'status']),
                   ('codex', ['codex', 'login', 'status'])]:
    ok, text = run(args)
    if name == 'claude' and ok:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and data.get('loggedIn') is False:
                ok = False
        except ValueError:
            pass
    result[name + '_auth'] = ok
for name in ('claude', 'codex', 'agy'):
    result[name + '_version'] = ver([name, '--version'])
try:
    result['disk'] = shutil.disk_usage(str(p) if valid else str(Path.home())).free >= int(minimum)
except OSError:
    result['disk'] = False
result['grill'] = False
if valid and commit:
    result['grill'] = (run(['git', 'cat-file', '-e', commit + '^{commit}'])[0]
                       or run(['git', '-c', 'credential.interactive=false',
                               'fetch', '--dry-run', 'origin', commit])[0])
print(json.dumps(result), flush=True)
'''


def _run(args: list[str], timeout: float, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=timeout)


def grill_commit(repo: Path) -> str:
    """현재 feature의 마지막 spec 커밋. 일반 브랜치에서는 마지막 grill spec을 쓴다."""
    branch = _run(["git", "branch", "--show-current"], 10, repo).stdout.strip().split("/")
    path = (f".goldstack/work/{branch[1]}/spec.md" if len(branch) >= 3 and branch[0] == "gs"
            else ".goldstack/work/*/spec.md")
    cp = _run(["git", "log", "-1", "--format=%H", "--", path], 10, repo)
    return cp.stdout.strip() if cp.returncode == 0 else ""


def probe(machine: str, repo_path: str, commit: str, timeout: float = TIMEOUT) -> dict:
    """workspace/pane으로 검사하고 고유한 끝 줄까지 기다린다. 모든 herdr 호출에 제한 시간이 있다."""
    deadline = time.monotonic() + timeout
    prefix = [herdr.bin(), "--machine", machine]

    def call(args: list[str]) -> subprocess.CompletedProcess:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise herdr.HerdrError("timeout", "원격 검사 시간 초과")
        cp = _run(prefix + args, remaining)
        if cp.returncode:
            try:
                herdr._check_error(herdr._json(cp.stderr or cp.stdout))
            except herdr.HerdrError as e:
                if e.code == "timeout":
                    raise
            raise herdr.HerdrError("remote", "herdr 원격 요청 실패(연결과 pane 상태를 확인한다)")
        return cp

    created = call(["workspace", "create", "--label", "gs remote check", "--no-focus"])
    value = herdr._json(created.stdout)
    herdr._check_error(value)
    result = value.get("result", {})
    root = result.get("root_pane") if isinstance(result, dict) else None
    pane = root.get("pane_id") if isinstance(root, dict) else None
    if not isinstance(pane, str) or not pane:
        raise herdr.HerdrError("remote", "workspace 응답에 root_pane.pane_id가 없다")
    token = uuid.uuid4().hex
    start, end = f"GS_CHECK_START_{token}", f"GS_CHECK_END_{token}"
    # macOS 터미널의 canonical 입력 한도 안에 들게 한 줄로 압축한다.
    packed = base64.b64encode(zlib.compress(PROBE.encode())).decode()
    script = f"import base64,zlib;exec(zlib.decompress(base64.b64decode({packed!r})))"
    command = ("printf '\\n%s\\n' " + shlex.quote(start) + "; "
               + shlex.join(["python3", "-c", script, repo_path, commit, str(MIN_FREE)])
               + "; printf '\\n%s\\n' " + shlex.quote(end))
    try:
        call(["pane", "run", pane, shlex.join(["sh", "-c", command])])
        remaining_ms = max(1, int((deadline - time.monotonic()) * 1000))
        call(["pane", "wait-output", pane, "--regex", f"(?m)^{end}\\r?$",
              "--timeout", str(remaining_ms), "--source", "recent-unwrapped"])
        cp = call(["pane", "read", pane, "--format", "text", "--source", "recent-unwrapped", "--lines", "200", "--raw"])
        # --raw는 pane read의 JSON 포장 대신 텍스트를 받는다.
        lines = cp.stdout.replace("\r", "").splitlines()
        begin = lines.index(start)
        finish = lines.index(end, begin + 1)
        data = json.loads("\n".join(lines[begin + 1:finish]).strip())
        if not isinstance(data, dict):
            raise ValueError("검사 결과가 객체가 아니다")
        return data
    except (ValueError, IndexError) as e:
        raise herdr.HerdrError("remote", "원격 검사 결과가 없다(python3와 pane 출력을 확인한다)") from e
    finally:
        # 검사 전용 pane을 닫는다. 정리 실패가 원래 검사 결과를 가리지 않는다.
        try:
            _run(prefix + ["pane", "close", pane], 5)
        except (OSError, subprocess.TimeoutExpired):
            pass


def _local_cli(repo: Path, name: str) -> str | None:
    binary = adapters.claude_bin() if name == "claude" else os.environ.get("GS_" + name.upper(), name)
    try:
        cp = _run([binary, "--version"], 8, repo)
        return cp.stdout.strip().splitlines()[0] if cp.returncode == 0 and cp.stdout.strip() else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def check(repo: Path, machine: str, out: TextIO, err: TextIO) -> int:
    failed = False

    def item(name: str, ok: bool, remedy: str) -> None:
        nonlocal failed
        failed |= not ok
        print(f"{'통과' if ok else '빠짐'}: {name} → {'준비됨' if ok else remedy}", file=out)

    if not shutil.which(herdr.bin()):
        print(f"오류: herdr가 없다 → {GUIDE}을 따른다", file=err)
        return 1
    try:
        cp = _run([herdr.bin(), "machine", "status"], 10)
        # 다른 저장된 머신 실패로 종료 1이어도 지정한 머신 줄만 판정한다.
        rows = [line.replace('\\t', '\t').split() for line in cp.stdout.splitlines()]
        row = next((r for r in rows if len(r) == 3 and machine in r[:2]), None)
        if row is None:
            print(f"오류: 저장된 머신이 아니다 → herdr 머신 등록 또는 {GUIDE}을 따른다", file=err)
            return 1
        connected = row[-1] == "reachable"
        item("연결", connected, "herdr machine status로 연결을 복구한다")
        if not connected:
            return 1
        key = f"GS_REMOTE_REPO_{machine}"
        path = config.read_local_env(repo).get(key, "")
        item("레포 경로 설정", bool(path), f".goldstack/local.env에 {key}=<원격 레포 절대 경로>를 쓴다")
        if not path:
            return 1
        commit = grill_commit(repo)
        data = probe(machine, path, commit)
        local = version.installation(repo)
        remote_gs = data.get("gs")
        item("gs", remote_gs == f"gs {local.version}", "원격에서 gs self-update(미설치면 gs 설치)")
        item("goldstack 플러그인", bool(local.plugin_version) and data.get("plugin") == local.plugin_version,
             "원격에서 gs self-update; 로컬 플러그인 버전도 확인한다")
        for name, login in (("gh", "gh auth login"), ("claude", "claude auth login"), ("codex", "codex login")):
            item(f"{name} 인증", data.get(name + "_auth") is True, f"원격에서 {login}")
        item("디스크 여유", data.get("disk") is True, "원격 레포 볼륨에 1 GiB 이상 확보한다")
        item("레포 경로", data.get("repo") is True, f"{key} 경로에 레포를 clone한다")
        item(".goldstack/local.env", data.get("env") is True, "원격 레포에 .goldstack/local.env를 직접 준비한다(값은 검사하지 않음)")
        item("grill 커밋 수신", bool(commit) and data.get("grill") is True,
             "feature spec을 커밋·push하고 원격 레포의 origin과 git 인증을 확인한다")
        for name in ("claude", "codex", "agy"):
            current, remote = _local_cli(repo, name), data.get(name + "_version")
            if current != remote or current is None:
                print(f"경고: {name} 버전 차이 또는 조회 불가 → 양쪽 {name} --version을 확인한다", file=out)
    except (OSError, subprocess.TimeoutExpired, herdr.HerdrError, metadata.PackageNotFoundError) as e:
        # 명령 출력에는 비밀이 있을 수 있어 예외 본문을 그대로 내보내지 않는다.
        reason = "시간 초과" if isinstance(e, subprocess.TimeoutExpired) or getattr(e, "code", "") == "timeout" else "조회 실패"
        item("원격 검사", False, f"{reason}; herdr 연결·python3·pane 상태를 확인하고 다시 실행한다")
    return int(failed)
