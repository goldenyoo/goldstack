"""goldstack-v36 01: `gs child`는 명령 맨 앞에서 한 겹만 받는다. 앞붙이 옵션의 값을 명령으로 읽지 않고, 셸 중첩 한도를 넘으면 막는다.

spec §6 측정 표를 `hook.decide`(`GS_ROLE=worker`)로 고정한다. 0.2.19는 `gs child` 안쪽 명령에 바깥 앞붙이를 다시 붙여
`depth <= 3`일 때만 따라갔다. 그래서 앞붙이 뒤나 반복된 `gs child`, 한도를 넘은 중첩이 검사 없이 통과했다.
`strip_prefix`는 `setsid`와 값을 받는 옵션(`env -u X`, `timeout -s KILL`, `exec -a x`)을 몰라 `gs child` 없이도 `git push`를 놓쳤다.
"""
import shlex
import unittest

import support  # noqa: F401  시험 공용 fixture(이 파일은 hook 판정만 본다)
from gs import hook

WT = "/gs-test-nowhere/repo/.goldstack/work/f/run/wt/01"
WORKER = {"GS_ROLE": "worker", "GS_WORKTREE": WT, "HOME": "/gs-test-nowhere/home"}
CHILD = "gs child -- "
PUSH = "`git push`는 worker가 하지 않는다"


def nested(script: str, times: int) -> str:
    """`bash -c`로 `times`겹 감싼다. 셸이 그대로 읽는 따옴표(`shlex.quote`)를 쓴다."""
    for _ in range(times):
        script = "bash -c " + shlex.quote(script)
    return script


# spec §6: 막혀야 하는 명령
BLOCKED = [
    "gs child -- git push",
    CHILD * 5 + "git push",
    CHILD * 5 + "env -u GS_ROLE claude -p hi",
    "gs child -- gs child -- claude -p hi",
    nested(CHILD * 3 + "git push", 1),
    "setsid gs child -- git push",
    "env -u CLAUDE_EFFORT gs child -- git push",
    "timeout -s KILL 5 gs child -- git push",
    "exec -a x gs child -- git push",
    "echo push | setsid xargs gs child -- git",
    # `env -S`로 펼친 앞붙이 뒤의 `gs child -- env -u GS_ROLE …`(goldstack-v35 02 리뷰의 재현)
    'env -S "gs child --" env -u GS_ROLE claude -p hi',
    'setsid env -u FOO -S "gs child --" bash -c "unset GS_ROLE; claude -p hi"',
    'exec -a myname env --split-string="gs child --" env -u GS_ROLE claude -p hi',
    'timeout -s TERM 5 env -S "gs --repo /x child --" env -u GS_ROLE claude -p hi',
    'sudo -u root env -S "gs --repo=/x child --" env -u GS_ROLE claude -p hi',
    'env -i -S "GS_ROLE=worker gs child -- claude -p hi"',
    "env -S 'gs child -- claude -p hi'",
    "env --split-string='gs child -- claude -p hi'",
    "gs child -- env -u GS_ROLE claude -p hi",
    "gs child -- bash -c 'git push'",
    nested("git push", 5),
    "setsid git push",
    "env -u CLAUDE_EFFORT git push",
    "timeout -s KILL 5 git push",
    "exec -a x git push",
    "env -S 'git push'",
    "gs child -- setsid git push",
    "gs child -- env -u CLAUDE_EFFORT git push",
    "gs child -- timeout -s KILL 5 git push",
]

# spec §6: 통과해야 하는 명령
PASSED = [
    "gs child -- claude -p hi --model opus",
    "gs child -- codex exec hi",
    "gs child -- bash run.sh",
    "gs child -- timeout 600 claude -p hi",
    "gs --repo . child -- claude -p hi",
    nested("echo hi", 3),
    "timeout 5 claude -p hi",
    "setsid claude -p hi",
    "env -u CLAUDE_EFFORT git status",
    "timeout -s KILL 5 git status",
    "env -S 'git status'",
]

# 앞붙이 뒤나 반복된 `gs child`. 안쪽이 허용 명령이어도 막고, 이유는 `GS_CHILD_FRONT`다
NOT_FRONT = [
    CHILD * 5 + "git push",
    CHILD * 5 + "env -u GS_ROLE claude -p hi",
    "gs child -- gs child -- claude -p hi",
    "gs child -- gs --repo /x child -- claude -p hi",
    "gs child -- \\gs child -- claude -p hi",
    nested(CHILD * 3 + "git push", 1),
    "setsid gs child -- git push",
    "env -u CLAUDE_EFFORT gs child -- git push",
    "timeout -s KILL 5 gs child -- git push",
    "exec -a x gs child -- git push",
    "echo push | setsid xargs gs child -- git",
    'env -S "gs child --" env -u GS_ROLE claude -p hi',
    'env -i -S "GS_ROLE=worker gs child -- claude -p hi"',  # 0.2.19는 `GS_ROLE=worker`를 잘라 `env -i`로 오차단했다
    "env -S 'gs child -- claude -p hi'",
    "env --split-string='gs child -- claude -p hi'",
    "FOO=1 gs child -- claude -p hi",
    "nohup gs child -- claude -p hi",
    "setsid gs child -- claude -p hi",
    "timeout 600 gs child -- claude -p hi",
    "nice -n 5 gs child -- claude -p hi",
    "sudo -u root gs child -- claude -p hi",
    "xargs gs child -- claude -p hi",
    "command gs child -- claude -p hi",
    "gs child -- setsid gs child -- claude -p hi",
    "gs child -- env -S 'gs child -- claude -p hi'",
    "echo start; setsid gs child -- claude -p hi",
    "echo $(setsid gs child -- claude -p hi)",
]

# 앞붙이와 값을 받는 옵션. `{}`에 명령이 들어간다. `git push`면 막고 `git status`면 통과한다
WRAPPED = [
    "setsid {}", "setsid -f {}", "setsid --fork {}",
    "env -u CLAUDE_EFFORT {}", "env -uCLAUDE_EFFORT {}", "env --unset CLAUDE_EFFORT {}", "env --unset=CLAUDE_EFFORT {}",
    "env -C /tmp {}", "env --chdir /tmp {}", "env --chdir=/tmp {}", "env -S 'FOO=1' {}", "env --split-string 'FOO=1' {}",
    "env -i GS_ROLE=worker {}",
    "timeout -s KILL 5 {}", "timeout -sKILL 5 {}", "timeout --signal KILL 5 {}", "timeout --signal=KILL 5 {}",
    "timeout --sig KILL 5 {}", "timeout -k 1 5 {}", "timeout --kill-after 1 5 {}", "timeout -k 1 -s KILL 5 {}",
    "timeout 0.5 {}", "timeout 1m {}", "timeout $T {}", "timeout -- 5 {}", "timeout --foreground 5 {}",
    "exec -a x {}", "exec -l {}",
    "nice -n 5 {}", "nice -n +5 {}", "nice -n -5 {}", "nice --adjustment 5 {}", "nice -10 {}",
    "stdbuf -o L {}", "stdbuf -e 0 {}", "stdbuf -i 0 {}", "stdbuf -oL {}", "stdbuf --output L {}",
    "ionice -c 3 {}", "ionice -c idle {}", "ionice -n 7 {}", "ionice --class idle {}",
    "caffeinate {}", "caffeinate -i {}", "caffeinate -t 5 {}", "caffeinate -w 123 {}",
    "time -f %e {}", "time -o /tmp/t {}",
    "sudo -u root {}", "sudo --user root {}",
    "setsid nohup timeout -s KILL 5 env -u CLAUDE_EFFORT {}",
    "gs child -- setsid {}", "gs child -- env -u CLAUDE_EFFORT {}", "gs child -- timeout -s KILL 5 {}",
    "gs child -- exec -a x {}", "gs child -- stdbuf -o L {}", "gs child -- nice -n +5 {}",
]

# 모르는 옵션이라는 이유로 막지 않는다
UNKNOWN_OPTIONS = [
    "timeout --frobnicate 5 claude -p hi",
    "setsid --wait claude -p hi",
    "env -v claude -p hi",
    "caffeinate -dims claude -p hi",
    "nice --frobnicate claude -p hi",
]


class GsChildTest(unittest.TestCase):
    def verdict(self, command, env=None):
        payload = {"cwd": WT, "tool_name": "Bash", "tool_input": {"command": command}}
        return hook.decide(payload, WORKER if env is None else env)

    def ctx(self):
        return hook.Ctx(worktree=WT, cwd=WT, env=WORKER)

    def test_spec_blocked_table(self):
        for command in BLOCKED:
            with self.subTest(command=command):
                self.assertIsNotNone(self.verdict(command), command)

    def test_spec_passed_table(self):
        for command in PASSED:
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command), command)

    def test_gs_child_only_at_the_front_once(self):
        """앞붙이 뒤나 반복된 `gs child`는 안쪽 명령이 무엇이든 그 이유로 막는다. 맨 앞은 원래 argv(`env -S`를 펼치기 전)로 본다."""
        for command in NOT_FRONT:
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command), hook.GS_CHILD_FRONT, command)

    def test_front_reason_tells_where_to_put_the_prefix(self):
        reason = self.verdict("setsid gs child -- claude -p hi")
        self.assertIn("`gs child`는 명령 맨 앞에 한 번만 쓴다", reason)
        self.assertIn("앞붙이는 `gs child --` 뒤에 둔다", reason)
        self.assertIn("`gs child -- timeout 600 claude -p …`", reason)
        self.assertIsNone(self.verdict("gs child -- setsid timeout 600 claude -p hi"))  # 안내대로 고친 명령은 통과한다

    def test_inner_command_is_judged_as_a_new_command(self):
        """`gs child --` 뒤의 명령은 바깥 앞붙이 없이 처음부터 같은 판정을 받는다(`GS_ROLE` 지우기, `git push`, 셸 본문)."""
        self.assertEqual(self.verdict("gs child -- git push"), PUSH)
        self.assertEqual(self.verdict("gs child git push"), PUSH)  # `--` 없이도 argparse는 나머지를 명령으로 받는다
        self.assertEqual(self.verdict("gs child -- bash -c 'git push'"), PUSH)
        self.assertEqual(self.verdict("gs child -- timeout -s KILL 5 git push"), PUSH)
        self.assertIn("`env -u GS_ROLE`", self.verdict("gs child -- env -u GS_ROLE claude -p hi"))
        self.assertIn("`unset GS_ROLE`", self.verdict("gs child -- bash -c 'unset GS_ROLE; claude -p hi'"))
        self.assertIn("worktree 밖", self.verdict("gs child -- echo ok > /gs-test-nowhere/outside.txt"))
        self.assertIn("pkill", self.verdict("gs child -- pkill python"))

    def test_wrapper_option_values_are_not_the_command(self):
        for form in WRAPPED:
            with self.subTest(form=form):
                self.assertEqual(self.verdict(form.format("git push")), PUSH, form)
                self.assertIsNone(self.verdict(form.format("git status")), form)

    def test_role_strip_after_wrapper_options(self):
        """`strip_prefix`와 `GS_ROLE` 판정이 같은 판독을 쓴다. 새로 아는 앞붙이 뒤의 `GS_ROLE` 지우기도 막는다."""
        for form in ("ionice -c idle {}", "caffeinate -t 5 {}", "stdbuf -o L {}", "nice -n +5 {}", "timeout $T {}",
                     "timeout -k 1 -s KILL 5 {}", "time -o /tmp/t {}", "ionice -c idle bash -c '{}'"):
            for core in ("env -u GS_ROLE claude -p hi", "unset GS_ROLE", "GS_ROLE=other claude -p hi"):
                command = form.format(core)
                with self.subTest(command=command):
                    self.assertIn("`GS_ROLE`", self.verdict(command) or "", command)

    def test_xargs_replace_string_in_a_prefix_word(self):
        """앞붙이 옵션의 값을 건너뛰면 그 값 속 xargs 치환 문자열이 보이지 않게 된다. `@`가 `GS_ROLE`이 되면 `env -u GS_ROLE`이다."""
        for command in ("echo GS_ROLE | xargs -I@ env -u @ claude -p hi", "echo GS_ROLE | xargs -I{} env --unset {} claude -p hi",
                        "echo GS_ROLE | xargs -i env -u {} claude -p hi", "echo GS_ROLE | xargs -J@ env -u @ claude -p hi",
                        "echo ROLE | xargs -I@ env -u GS_@ claude -p hi", "echo x | xargs -I@ env -C @ rm -rf x",
                        "echo GS_ROLE | xargs -I@ bash -c 'env -u @ claude -p hi'",
                        "echo GS_ROLE | xargs -I@ sh -c 'gs child -- env -u @ claude -p hi'",
                        "echo KILL | xargs -I@ timeout -s @ 5 git status",
                        "echo ROLE | xargs -I X sh -c 'GS_X=other claude -p hi'",  # 이름에 든 치환 문자열
                        "echo x | xargs -I w sh -c 'GS_ROLE=worker claude -p hi'"):  # `worker`가 `xorker`가 된다
            with self.subTest(command=command):
                self.assertIn("`xargs`의 치환 문자열이 앞붙이 단어", self.verdict(command) or "", command)
        for command in ("echo f | xargs -I {} timeout 5 git status {}", "echo f | xargs -I {} env FOO=1 echo {}",
                        "echo f | xargs -I {} setsid echo {}", "echo f | xargs -n 1 env -u CLAUDE_EFFORT echo",
                        "echo f | xargs -I {} sh -c 'f={}; cat \"$f\"'", "echo f | xargs -I {} env FOO={} echo hi"):
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command), command)

    def test_env_split_string_that_env_reads_differently_is_blocked(self):
        """env -S는 `#`(주석), `\\_`(공백), `\\c`(끝), `${VAR}`를 셸과 다르게 푼다. 같게 풀지 못하면 판정하지 않고 막는다."""
        for command in ("env -S '#' git push", "env -S '\\c' git push", "env -S '\\_' git push", "env -S 'git\\_push'",
                        "env -S '${NOPE}' git push", "env -S '#' env -u GS_ROLE claude -p hi",
                        "env -S '-u\\_GS_ROLE' claude -p hi", "env -S '#' gs child -- claude -p hi",
                        "env -S 'gs\\_child -- claude -p hi'", "env --split-string='#' git status",
                        "env -S \"'unclosed\" git status", "env -iS '#' claude -p hi", "setsid env -S '#' git push"):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command), hook.ENV_SPLIT_UNREADABLE, command)
        self.assertIsNone(self.verdict("env -S 'FOO=1 BAR=2' git status"))

    def test_timeout_duration_slot_takes_only_a_duration(self):
        """`timeout` 옵션 뒤의 시간처럼 생긴 단어만 시간으로 건너뛴다. 아니면 그 단어가 명령이다."""
        for command in ("timeout git push", "timeout 5 git push", "timeout 0.5 git push", "timeout .5 git push",
                        "timeout 1e3 git push", "timeout inf git push", "timeout $T git push", "timeout ${T}s git push",
                        "timeout -s KILL git push"):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command), PUSH, command)
        self.assertEqual(hook.strip_prefix(["timeout", "git", "push"]), ["git", "push"])
        self.assertEqual(hook.strip_prefix(["timeout", "5", "git", "push"]), ["git", "push"])

    def test_unknown_options_do_not_block(self):
        for command in UNKNOWN_OPTIONS:
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command), command)

    def test_strip_prefix_reads_wrapper_options(self):
        cases = [
            (["setsid", "git", "push"], ["git", "push"]),
            (["env", "-u", "CLAUDE_EFFORT", "git", "push"], ["git", "push"]),
            (["env", "--unset", "CLAUDE_EFFORT", "git", "push"], ["git", "push"]),
            (["env", "-C", "/tmp", "git", "push"], ["git", "push"]),
            (["env", "--chdir", "/tmp", "git", "push"], ["git", "push"]),
            (["env", "-S", "FOO=1 git push"], ["git", "push"]),
            (["env", "--split-string=git push"], ["git", "push"]),
            (["timeout", "-s", "KILL", "5", "git", "push"], ["git", "push"]),
            (["timeout", "--signal", "KILL", "5", "git", "push"], ["git", "push"]),
            (["timeout", "-k", "1", "5", "git", "push"], ["git", "push"]),
            (["timeout", "--kill-after", "1", "5", "git", "push"], ["git", "push"]),
            (["timeout", "0.5", "git", "push"], ["git", "push"]),
            (["exec", "-a", "x", "git", "push"], ["git", "push"]),
            (["nice", "-n", "+5", "git", "push"], ["git", "push"]),
            (["stdbuf", "-i", "0", "-o", "L", "-e", "0", "git", "push"], ["git", "push"]),
            (["ionice", "-c", "idle", "git", "push"], ["git", "push"]),
            (["caffeinate", "-t", "5", "git", "push"], ["git", "push"]),
        ]
        for argv, rest in cases:
            with self.subTest(argv=argv):
                self.assertEqual(hook.strip_prefix(argv), rest)

    def test_split_prefix_keeps_expanded_words(self):
        """`env -S`가 단어 수를 바꿔도 앞붙이는 펼친 단어에서 자른다. 원래 argv를 길이로 자르면 엉뚱한 곳이 잘린다(goldstack-v35 02)."""
        self.assertEqual(hook.split_prefix(["env", "-S", "xargs -I X", "git", "X"]),
                         (["env", "xargs", "-I", "X"], ["git", "X"]))
        self.assertEqual(hook.split_prefix(["env", "-i", "-S", "GS_ROLE=worker gs child -- claude"]),
                         (["env", "-i", "GS_ROLE=worker"], ["gs", "child", "--", "claude"]))
        # 펼친 앞붙이의 `xargs`가 바깥 판정에 걸린다
        self.assertIsNotNone(self.verdict("echo push | env -S 'xargs -I X' git X"))
        self.assertIsNotNone(self.verdict("echo push | env -S xargs git"))

    def test_too_deep_is_blocked(self):
        """재귀 한도를 넘으면 통과가 아니라 막는다. 본문이 무해해도 막는다(읽지 않았으니 모른다)."""
        for command in (nested("git push", 4), nested("git push", 5), nested("echo hi", 4),
                        "echo $(echo $(echo $(echo $(echo hi))))", nested("echo $(echo hi)", 3),
                        "eval " + shlex.quote(nested("eval " + shlex.quote("eval 'echo hi'"), 1))):
            with self.subTest(command=command):
                self.assertEqual(self.verdict(command), hook.TOO_DEEP, command)
        self.assertIn("셸 중첩", hook.TOO_DEEP)
        self.assertIn("판정할 수 없다", hook.TOO_DEEP)
        self.assertIn("펼쳐서 쓴다", hook.TOO_DEEP)
        for command in (nested("echo hi", 3), "echo $(echo $(echo $(echo hi)))", nested("git status", 3)):
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command), command)
        self.assertEqual(nested("git push", 3).count("bash -c"), 3)
        self.assertEqual(self.verdict(nested("git push", 3)), PUSH)

    def test_check_bash_and_check_segment_block_past_the_limit(self):
        ctx = self.ctx()
        self.assertIsNone(hook.check_bash("echo hi", ctx, hook.MAX_DEPTH))
        self.assertEqual(hook.check_bash("echo hi", ctx, hook.MAX_DEPTH + 1), hook.TOO_DEEP)
        self.assertIsNone(hook.check_segment(["echo", "hi"], [], WT, ctx, hook.MAX_DEPTH))
        self.assertEqual(hook.check_segment(["echo", "hi"], [], WT, ctx, hook.MAX_DEPTH + 1), hook.TOO_DEEP)

    def test_without_worker_role_everything_passes(self):
        for command in [*BLOCKED, *NOT_FRONT, nested("git push", 9)]:
            for env in ({}, {"GS_ROLE": "reviewer"}):
                self.assertIsNone(self.verdict(command, env), (env, command))


if __name__ == "__main__":
    unittest.main()
