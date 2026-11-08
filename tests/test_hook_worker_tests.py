"""goldstack-v26 01: worker의 고비용 시험 실행을 hook이 config `[hook.worker_tests]` 규칙으로 막는다.

판정 시험은 이 레포의 실제 config 값을 쓴다. 막힘·통과 명령은 v25 worker.log에서 가져왔다(03의 시험 폴더 순회,
02·03의 `printf … | xargs` 목록). 전달 시험은 config → 어댑터 `env()` → `worker.write_script`의 export → hook을
실제 코드와 실제 bash로 잇는다. 가짜 claude·agy가 그 환경에서 진짜 hook 진입점(`gs hook pretooluse`·`agy-pretooluse`)을 부른다.
"""
import ast
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

import support
from gs import adapters, config, hook, hook_agy, worker
from gs.feature import Ticket
from support import isolate_git_env, sh

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src/gs"
ADVICE = "전체 검증은 gs가 병합 전에 돌린다. 고친 곳에 닿는 좁은 시험만 돌린다"
# 판정 시험의 worktree. /tmp 밖이어야 v25 명령의 `> /tmp/…`가 기존 판정(worktree 밖 쓰기)에 걸리지 않는다.
# 실제 worktree는 레포의 `.goldstack/work/…` 아래다. Linux의 임시 디렉터리는 /tmp 아래라 쓰지 않는다
WT = "/gs-test-nowhere/repo/.goldstack/work/f/run/wt/01"

# v25 03 worker의 명령 그대로(시험 95개 중 16개만 뺀 순회)
V25_03 = r"""ls tests | grep '^test_' | grep -v -E '^(test_verify_repair|test_setup_when|test_ticket_verify|test_verify_failure_report|test_feedback_collect|test_async_review|test_review_target|test_go_execution|test_review_network|test_worker_commands|test_metrics|test_review|test_feedback_format|test_fix_brief|test_model_config|test_review_tiers)\.py$' | xargs -P 6 -I{} sh -c '.venv/bin/python -m unittest discover -s tests -p {} > /tmp/gs03_t3_{}.log 2>&1; echo "{}: $(tail -1 /tmp/gs03_t3_{}.log)"' > /tmp/gs03_rest.txt 2>&1; grep -v ": OK$" /tmp/gs03_rest.txt; echo "files: $(wc -l < /tmp/gs03_rest.txt)\""""
NAMES = ["test_verify_repair.py", "test_setup_when.py", "test_ticket_verify.py", "test_verify_failure_report.py",
         "test_feedback_collect.py", "test_async_review.py", "test_review_target.py", "test_go_execution.py",
         "test_review_network.py", "test_worker_commands.py", "test_metrics.py", "test_review.py"]


def listed(n):
    """v25 02·03 worker의 `printf … | xargs` 모양. 시험 파일 n개."""
    return (f"printf '%s\\n' {' '.join(NAMES[:n])} | xargs -P 6 -I{{}} sh -c "
            "'.venv/bin/python -m unittest discover -s tests -p {} > /tmp/gs03_t_{}.log 2>&1; "
            "echo \"{}: $(tail -1 /tmp/gs03_t_{}.log)\"'")


BLOCKED = [V25_03, listed(11), listed(12),
           ".venv/bin/python -m unittest discover -s tests",
           "python -m unittest discover -s tests",
           ".venv/bin/python -m unittest discover -s tests -p 'test_*.py'",
           "ls tests | grep '^test_' | xargs -P 6 -n 1 .venv/bin/python -m unittest discover -s tests -p"]
PASSED = [listed(8), listed(10),
          ".venv/bin/python -m unittest discover -s tests -p test_x.py",
          "uv run python -m unittest discover -s tests -p test_hook.py",
          "git add " + " ".join(f"tests/{name}" for name in NAMES),
          "ls tests | grep -E '^test_(hook|config)'"]


def repo_rules():
    """이 레포 config의 `[hook.worker_tests]`를 gs가 worker에 넘기는 값."""
    cfg, problems = config.load(ROOT)
    assert cfg is not None, problems
    return cfg.hook.worker_tests.env_value()


def bash(command, cwd=WT):
    return {"tool_name": "Bash", "cwd": cwd, "tool_input": {"command": command}}


def agy_bash(command, cwd=WT):
    return {"workspacePaths": [cwd], "toolCall": {"name": "run_command", "args": {"CommandLine": command, "Cwd": cwd}}}


class Base(unittest.TestCase):
    def setUp(self):
        self.env = {"GS_ROLE": "worker", "GS_WORKTREE": WT, "HOME": "/gs-test-nowhere/home",
                    config.WORKER_TESTS_ENV: repo_rules()}

    def verdict(self, command, env=None, cwd=WT):
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            reason = hook.decide(bash(command, cwd), self.env if env is None else env)
        return reason, err.getvalue()

    def claude_hook(self, command, env=None):
        """`gs hook pretooluse` 진입점. (종료 코드, stderr)."""
        err = io.StringIO()
        with contextlib.redirect_stderr(err):
            code = hook.main(["pretooluse"], io.StringIO(json.dumps(bash(command))), self.env if env is None else env)
        return code, err.getvalue()

    def agy_hook(self, command, env=None):
        """`gs hook agy-pretooluse` 진입점. (stdout 판정 JSON, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stderr(err):
            hook_agy.main(io.StringIO(json.dumps(agy_bash(command))), out, self.env if env is None else env)
        return json.loads(out.getvalue()), err.getvalue()


class RepoRulesTest(Base):
    """이 레포의 config 값으로 막고 통과시킨다."""

    def test_full_runs_are_blocked_with_the_advice(self):
        self.assertTrue(self.env[config.WORKER_TESTS_ENV])
        for command in BLOCKED:
            with self.subTest(command=command[:80]):
                reason, err = self.verdict(command)
                self.assertIsNotNone(reason)
                self.assertIn(ADVICE, reason)
                self.assertIn("[hook.worker_tests]", reason)
                self.assertEqual(err, "")

    def test_narrow_runs_and_non_runner_commands_pass(self):
        for command in PASSED:
            with self.subTest(command=command[:80]):
                self.assertEqual(self.verdict(command), (None, ""))

    def test_file_count_is_distinct_names_over_max_files(self):
        reason, _ = self.verdict(listed(11))
        self.assertIn("시험 파일 11개", reason)
        self.assertIn("max_files 10개", reason)
        same = " ".join(["tests/test_review.py", "test_review.py"] * 8)  # 16번 나와도 이름은 하나다
        self.assertEqual(self.verdict(f".venv/bin/python -m unittest {same}"), (None, ""))
        self.assertIsNotNone(self.verdict(".venv/bin/python -m unittest " + " ".join(NAMES[:11]))[0])
        # runner에 맞지 않으면 파일 수와 상관없이 통과한다
        self.assertEqual(self.verdict("cat " + " ".join(f"tests/{n}" for n in NAMES) + " | wc -l"), (None, ""))

    def test_deny_names_the_rule_that_matched(self):
        reason, _ = self.verdict(V25_03)
        self.assertIn("deny", reason)
        reason, _ = self.verdict("python -m unittest discover -s tests")
        self.assertIn("deny", reason)

    def test_raw_text_rule_also_sees_heredoc_and_strings(self):
        """한계(hook.py 머리말): 명령 원문 정규식이라 데이터로 적은 금지 명령도 막힌다."""
        self.assertIsNotNone(self.verdict("git commit -qm 'python -m unittest discover -s tests 금지'")[0])
        self.assertIsNotNone(self.verdict("cat > note.md <<'EOF'\npython -m unittest discover -s tests\nEOF")[0])

    def test_both_hook_entry_points_use_the_same_verdict(self):
        for command in BLOCKED:
            with self.subTest(command=command[:80]):
                code, err = self.claude_hook(command)
                self.assertEqual(code, 2)
                self.assertIn(ADVICE, err)
                verdict, _ = self.agy_hook(command)
                self.assertEqual(verdict["decision"], "deny")
                self.assertIn(ADVICE, verdict["reason"])
        for command in PASSED:
            with self.subTest(command=command[:80]):
                self.assertEqual(self.claude_hook(command), (0, ""))
                self.assertEqual(self.agy_hook(command), ({"decision": "allow"}, ""))

    def test_non_worker_always_passes(self):
        for role in (None, "", "reviewer"):
            env = {k: v for k, v in self.env.items() if k != "GS_ROLE"}
            if role is not None:
                env["GS_ROLE"] = role
            for command in BLOCKED:
                with self.subTest(role=role, command=command[:60]):
                    self.assertEqual(self.verdict(command, env), (None, ""))
                    self.assertEqual(self.claude_hook(command, env), (0, ""))
                    self.assertEqual(self.agy_hook(command, env)[0], {"decision": "allow"})


class OffTest(Base):
    """절이 없거나 값이 비면 아무것도 막지 않는다. 깨진 값은 이 규칙만 건너뛰고 경고한다."""

    def test_config_without_rules_blocks_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / ".goldstack").mkdir()
            (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
            cfg, problems = config.load(repo)
        self.assertEqual([p for p in problems if p.level == "오류"], [])
        env = {**self.env, config.WORKER_TESTS_ENV: cfg.hook.worker_tests.env_value()}
        self.assertEqual(env[config.WORKER_TESTS_ENV], "")
        for command in BLOCKED:
            with self.subTest(command=command[:80]):
                self.assertEqual(self.verdict(command, env), (None, ""))

    def test_empty_or_missing_env_blocks_nothing(self):
        empty = {**self.env, config.WORKER_TESTS_ENV: ""}
        missing = {k: v for k, v in self.env.items() if k != config.WORKER_TESTS_ENV}
        for env in (empty, missing):
            for command in BLOCKED:
                with self.subTest(env=sorted(env), command=command[:60]):
                    self.assertEqual(self.verdict(command, env), (None, ""))
                    self.assertEqual(self.claude_hook(command, env), (0, ""))

    def test_unreadable_env_skips_only_this_rule_and_warns(self):
        for bad in ("{", "[1]", '{"deny": ["("]}', '{"runner": "x", "file": "y"}', '{"max_files": -1}',
                    '{"deny": ["a{4294967295}"]}', '{"deny": ["' + "(" * 2000 + ")" * 2000 + '"]}'):
            env = {**self.env, config.WORKER_TESTS_ENV: bad}
            with self.subTest(bad=bad):
                reason, err = self.verdict("python -m unittest discover -s tests", env)
                self.assertIsNone(reason)
                self.assertIn(config.WORKER_TESTS_ENV, err)
                self.assertIn("건너뛴다", err)
                code, err = self.claude_hook("python -m unittest discover -s tests", env)
                self.assertEqual(code, 0)
                self.assertIn(config.WORKER_TESTS_ENV, err)
                # 다른 판정은 그대로다
                self.assertIsNotNone(self.verdict("git push origin HEAD", env)[0])
                self.assertEqual(self.claude_hook("git push origin HEAD", env)[0], 2)

    def test_worktree_config_does_not_change_the_rules(self):
        """hook은 worktree의 `.goldstack/config.toml`을 읽지 않는다. worker가 그 파일을 고쳐도 그 실행의 규칙은 그대로다."""
        with tempfile.TemporaryDirectory() as tmp:
            wt = os.path.realpath(tmp)
            (Path(wt) / ".goldstack").mkdir()
            (Path(wt) / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"')
                                                       + '[hook.worker_tests]\ndeny = ["git status"]\n')
            rules = {**self.env, "GS_WORKTREE": wt}
            self.assertIsNotNone(self.verdict("python -m unittest discover -s tests", rules, cwd=wt)[0])
            self.assertEqual(self.verdict("git status", rules, cwd=wt), (None, ""))
            empty = {**rules, config.WORKER_TESTS_ENV: ""}
            self.assertEqual(self.verdict("git status", empty, cwd=wt), (None, ""))


# 가짜 claude·agy가 부르는 확인 스크립트: 물려받은 환경에서 hook이 읽은 규칙과 진짜 hook 진입점의 판정을 남긴다
PROBE = r'''
import json, os, subprocess, sys
from gs import hook
kind = sys.argv[1]
rules = hook.worker_tests(os.environ)
out = {"env": os.environ.get("GS_WORKER_TESTS"),
       "rules": None if rules is None else [list(rules.deny), rules.runner, rules.file, rules.max_files],
       "verdicts": []}
for command in json.loads(os.environ["GS_TEST_COMMANDS"]):
    if kind == "claude":
        payload = {"tool_name": "Bash", "cwd": os.getcwd(), "tool_input": {"command": command}}
        cp = subprocess.run([sys.executable, "-m", "gs.cli", "hook", "pretooluse"], input=json.dumps(payload),
                            capture_output=True, text=True)
        out["verdicts"].append([cp.returncode == 2, cp.stderr])
    else:
        payload = {"workspacePaths": [os.getcwd()],
                   "toolCall": {"name": "run_command", "args": {"CommandLine": command, "Cwd": os.getcwd()}}}
        cp = subprocess.run([sys.executable, "-m", "gs.cli", "hook", "agy-pretooluse"], input=json.dumps(payload),
                            capture_output=True, text=True)
        verdict = json.loads(cp.stdout)
        out["verdicts"].append([verdict["decision"] == "deny", verdict.get("reason", "")])
with open(os.environ["GS_TEST_OUT"], "w", encoding="utf-8") as f:
    json.dump(out, f)
'''
FAKE_CLAUDE = '#!/bin/bash\nif [ "$1" = plugin ]; then echo "[]"; exit 0; fi\ncat > /dev/null\nexec "$GS_TEST_PY" "$GS_TEST_PROBE" claude\n'
FAKE_AGY = '#!/bin/bash\nexec "$GS_TEST_PY" "$GS_TEST_PROBE" agy\n'

# 따옴표·역슬래시·`|`·`$`가 든 정규식. 역슬래시가 하나라도 빠지면 아래 판정이 달라진다
TRICKY = ("[hook.worker_tests]\n"
          + r"""deny = ["ls tests \\| grep '\\^test_' \\| wc -l$", '-p "\w+\.py"']""" + "\n"
          + r"""runner = 'unittest|pytest'""" + "\n"
          + r"""file = 'test_\w+\.py'""" + "\n"
          + "max_files = 2\n")
TRICKY_DENY = [r"ls tests \| grep '\^test_' \| wc -l$", r'-p "\w+\.py"']
DELIVERED = [("ls tests | grep '^test_' | wc -l", True),  # deny[0]: 작은따옴표, `\|`, `\^`, `$`
             ('.venv/bin/python -m unittest discover -s tests -p "test_x.py"', True),  # deny[1]: 큰따옴표, `\w`, `\.`
             ("pytest tests/test_a.py tests/test_b.py tests/test_c.py", True),  # runner의 `|` 뒤 갈래 + file의 `\w`
             ("pytest tests/test_a.py tests/test_b.py", False),
             ("git add tests/test_a.py tests/test_b.py tests/test_c.py", False)]


class DeliveryTest(unittest.TestCase):
    """config → 어댑터 env() → write_script의 export → (실제 bash) → 가짜 worker → 진짜 hook 진입점."""

    def setUp(self):
        isolate_git_env(self)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(os.path.realpath(tmp.name))
        self.wt = self.root / "wt"
        self.wt.mkdir()
        bin_dir = self.root / "bin"
        bin_dir.mkdir()
        for name, text in (("claude", FAKE_CLAUDE), ("agy", FAKE_AGY)):
            (bin_dir / name).write_text(text)
            (bin_dir / name).chmod(0o755)
        (self.root / "probe.py").write_text(PROBE)
        self.out = self.root / "probe.json"
        patch = mock.patch.dict(os.environ, {
            "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
            "GS_CLAUDE": str(bin_dir / "claude"), "GS_AGY": str(bin_dir / "agy"),
            "GS_TEST_PY": sys.executable, "GS_TEST_PROBE": str(self.root / "probe.py"), "GS_TEST_OUT": str(self.out),
        })
        patch.start()
        self.addCleanup(patch.stop)
        for name in ("GS_WORKER_CMD", "GS_ROLE", config.WORKER_TESTS_ENV):
            os.environ.pop(name, None)

    def deliver(self, family, extra, commands):
        repo = self.root / f"repo-{family}"
        (repo / ".goldstack").mkdir(parents=True)
        (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"') + extra)
        cfg, problems = config.load(repo)
        self.assertIsNotNone(cfg, problems)
        adapter = adapters.for_model(family, cfg.models, worker_tests=cfg.hook.worker_tests)
        rundir = self.root / f"run-{family}"
        rundir.mkdir()
        t = Ticket(id="01", title="t", blocked_by=[], model=family, reviewer="codex", path=Path("01-t.md"))
        job = worker.Job(ticket=t, worktree=self.wt, rundir=rundir)
        job.brief.write_text("brief\n")
        worker.write_script(job, adapter)
        self.out.unlink(missing_ok=True)
        with mock.patch.dict(os.environ, {"GS_TEST_COMMANDS": json.dumps([c for c, _ in commands])}):
            cp = subprocess.run(["bash", str(job.script)], stdin=subprocess.DEVNULL, capture_output=True, text=True,
                                timeout=120)
        log = job.log.read_text() if job.log.exists() else ""
        self.assertTrue(self.out.exists(), cp.stdout + cp.stderr + log)
        return cfg, json.loads(self.out.read_text())

    def test_tricky_regexes_reach_the_hook_unchanged(self):
        for family in ("claude", "agy"):
            with self.subTest(family=family):
                cfg, got = self.deliver(family, TRICKY, DELIVERED)
                rules = cfg.hook.worker_tests
                self.assertEqual(list(rules.deny), TRICKY_DENY)  # TOML이 읽은 값부터 확인한다
                self.assertEqual(got["env"], rules.env_value())
                self.assertEqual(got["rules"], [TRICKY_DENY, "unittest|pytest", r"test_\w+\.py", 2])
                for (command, blocked), (denied, reason) in zip(DELIVERED, got["verdicts"], strict=True):
                    self.assertEqual(denied, blocked, (command, reason))
                    if blocked:
                        self.assertIn(ADVICE, reason)

    def test_empty_config_overwrites_the_inherited_value(self):
        """gs를 띄운 셸에 값이 있어도 config가 비면 worker에는 빈 값이 간다."""
        inherited = json.dumps({"deny": ["."], "runner": "", "file": "", "max_files": 0})
        commands = [(c, False) for c, _ in DELIVERED]
        for family in ("claude", "agy"):
            with self.subTest(family=family), mock.patch.dict(os.environ, {config.WORKER_TESTS_ENV: inherited}):
                _, got = self.deliver(family, "", commands)
                self.assertEqual((got["env"], got["rules"]), ("", None))
                self.assertEqual([denied for denied, _ in got["verdicts"]], [False] * len(commands))

    def test_script_exports_the_variable_even_if_the_adapter_does_not(self):
        class Bare(adapters.Custom):
            def env(self, inp):
                return {"GS_BRIEF": str(inp.brief), "GS_WORKTREE": str(inp.worktree)}

        rundir = self.root / "run-bare"
        rundir.mkdir()
        t = Ticket(id="01", title="t", blocked_by=[], model="claude", reviewer="codex", path=Path("01-t.md"))
        job = worker.Job(ticket=t, worktree=self.wt, rundir=rundir)
        worker.write_script(job, Bare("true"))
        self.assertIn(f"export {config.WORKER_TESTS_ENV}=''\n", job.script.read_text())


class LaunchSitesTest(unittest.TestCase):
    def test_every_worker_launch_takes_the_adapter_from_worker_adapter(self):
        """첫(_start)·재개(_resume)·수정(_start_fix)·수리(_start_repair) worker가 모두 `_worker_adapter`의 어댑터로
        실행 스크립트를 쓴다. 그 함수가 config 규칙을 어댑터에 싣는다(LaunchTest가 실제 실행으로 본다)."""
        tree = ast.parse((SRC / "go.py").read_text(encoding="utf-8"))
        sites = {}
        for fn in tree.body:
            if not isinstance(fn, ast.FunctionDef):
                continue
            calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and ast.unparse(n.func) == "worker.write_script"]
            if not calls:
                continue
            made = {target.id for n in ast.walk(fn) if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call)
                    and ast.unparse(n.value.func) == "_worker_adapter"
                    for target in n.targets if isinstance(target, ast.Name)}
            sites[fn.name] = all(isinstance(c.args[1], ast.Name) and c.args[1].id in made for c in calls)
        self.assertEqual(sites, {"_resume": True, "_start": True, "_start_fix": True, "_start_repair": True})


FINDING = {"severity": "high", "location": "file_01", "claim": "FIX A", "evidence": "e"}
RULES = ("[hook.worker_tests]\n"
         + r"""deny = ["unittest discover -s tests$", 'grep "\^test_"']""" + "\n"
         + r"""runner = 'unittest|pytest'""" + "\n"
         + r"""file = 'test_\w+\.py'""" + "\nmax_files = 3\n")


class LaunchTest(support.GoTest):
    """진짜 `go()`가 첫·수정·수리 worker를 띄울 때 config 규칙을 worker 환경 변수로 넘긴다."""
    INHERITED = json.dumps({"deny": ["inherited"], "runner": "", "file": "", "max_files": 0})

    def setUp(self):
        super().setUp()
        os.environ[config.WORKER_TESTS_ENV] = self.INHERITED  # gs를 띄운 셸의 값. self.env가 끝에 되돌린다
        os.environ.pop("GS_ROLE", None)
        (self.bin / "worker.sh").write_text(textwrap.dedent('''\
            here="$(dirname "$0")"
            echo "$GS_TICKET" >> "$here/calls.log"
            if grep -q "^## 검증 실패(고칠 것)" "$GS_BRIEF"; then role=repair
            elif grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then role=fix
            else role=first; fi
            printf '%s\\t%s\\n' "$role" "${GS_WORKER_TESTS-unset}" >> "$here/rules.log"
            case $role in
              repair) git rm -q BROKEN; git commit -qm "repair $GS_TICKET" ;;
              fix) [ -f "$here/fixed" ] && exit 0  # 2차 수정은 할 것이 없다
                   touch "$here/fixed" BROKEN; git add -A; git commit -qm "fix breaks verify" ;;
              *) echo x > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET" ;;
            esac
        '''))

    def set_rules(self, extra):
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text() + extra)
        sh(self.repo, "git", "commit", "-qam", "worker tests rules")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)

    def run_workers(self):
        """첫 worker → 리뷰 지적의 수정 worker(BROKEN을 커밋) → 검증 실패의 수리 worker. 각 worker가 받은 값."""
        with self.review_with([FINDING]):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        records = [tuple(line.split("\t", 1)) for line in self.lines("rules.log")]
        self.assertEqual({role for role, _ in records}, {"first", "fix", "repair"}, records)
        return {value for _, value in records}

    def test_every_worker_gets_the_rules_of_the_config(self):
        self.set_rules(RULES)
        expected = config.load(self.repo)[0].hook.worker_tests.env_value()
        self.assertTrue(expected)
        self.assertEqual(self.run_workers(), {expected})

    def test_empty_config_overwrites_the_inherited_value(self):
        self.assertEqual(self.run_workers(), {""})


if __name__ == "__main__":
    unittest.main()
