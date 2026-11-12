"""goldstack-v35 02: worker가 `GS_ROLE`을 지우거나 바꾸는 명령을 hook이 막는다.

#59의 worker들이 측정용 자식 `claude -p`를 `env -u GS_ROLE …`로 띄웠다. 지우면 자식에는 worker hook이 판정하지 않는다.
판정은 `strip_prefix` 전 argv로 한다(`strip_prefix`가 `GS_ROLE=x`·`env -i`를 지우고 `env -u GS_ROLE`의 `GS_ROLE`을 명령 이름으로 남긴다).
"""
import contextlib
import io
import json
import unittest

import support  # noqa: F401  시험 공용 fixture(이 파일은 hook 판정만 본다)
from gs import hook

WT = "/gs-test-nowhere/repo/.goldstack/work/f/run/wt/02"
WORKER = {"GS_ROLE": "worker", "GS_WORKTREE": WT, "HOME": "/gs-test-nowhere/home"}

# 막는 형태. 같은 명령이 아래 SHELLS의 감싸는 모양에 들어가도 막힌다
CORE = [
    "env -u GS_ROLE claude -p hi",
    "env -uGS_ROLE claude -p hi",
    "env --unset=GS_ROLE claude -p hi",
    "env --unset GS_ROLE claude -p hi",
    "env -u CLAUDE_EFFORT -u GS_ROLE claude -p hi",
    "env -u GS_ROLE -u GS_WORKTREE -u GS_TICKET -u GS_NOEQUALS -u GS_BRIEF -u GS_WORKER_TESTS claude -p hi",  # #59 pod 로그
    "env -iu GS_ROLE claude -p hi",
    "env -i claude -p hi",
    "env --ignore-environment claude -p hi",
    "env - claude -p hi",
    "env -i HOME=/x PATH=/usr/bin claude -p hi",
    "env GS_ROLE=other claude -p hi",
    "env GS_ROLE= claude -p hi",
    "env GS_ROLE=subject FOO=1 claude -p hi",
    "env -S 'env -u GS_ROLE claude -p hi'",
    "env --split-string='env -u GS_ROLE claude -p hi'",
    "unset GS_ROLE",
    "unset -v GS_ROLE",
    "unset FOO GS_ROLE",
    "unset 'GS_*'",
    "export GS_ROLE=other",
    "export GS_ROLE=",
    "export FOO=1 GS_ROLE=other",
    "export -n GS_ROLE",
    "export -n GS_ROLE=worker",
    "declare +x GS_ROLE=worker",
    "typeset +x GS_ROLE=worker",
    "env FOO.BAR=1 GS_ROLE=other claude -p hi",
    "env a-b=1 env -u GS_ROLE claude -p hi",
    "exec -ca=1 claude -p hi",
    "exec -cafoo=bar claude -p hi",
    "gs --rep /x child -- env -u GS_ROLE claude -p hi",
    "gs --re /x child -- env -u GS_ROLE claude -p hi",
    "\\gs child -- env -u GS_ROLE claude -p hi",
    "readonly GS_ROLE=other",
    "GS_ROLE+=x claude -p hi",
    "declare +x GS_ROLE",
    "GS_ROLE=other claude -p hi",
    "GS_ROLE= claude -p hi",
    "FOO=1 GS_ROLE=other claude -p hi",
    "GS_ROLE=other",
    "exec -c claude -p hi",
]
# 막는 형태가 놓이는 자리. `{}`에 CORE 명령이 들어간다
SHELLS = [
    "{}",
    "echo start; {}",
    "true && {}",
    "false || {}",
    "echo x | {}",
    "echo start\n{}",
    "bash -c '{}'",
    "sh -c '{}'",
    "zsh -c '{}'",
    "bash -lc '{}'",
    "echo $({})",
    "echo `{}`",
    "echo \"$({})\"",
    "( {} )",
    "{{ {} ; }}",
    "eval '{}'",
    "sudo {}",
    "sudo -u root {}",
    "timeout 5 {}",
    "timeout -s KILL 5 {}",
    "nohup {}",
    "setsid {}",
    "setsid nohup timeout 5 {}",
    "setsid bash -c '{}'",
    "setsid nohup bash -c '{}'",
    "env -u CLAUDE_EFFORT bash -c '{}'",
    "env -C /tmp sh -c '{}'",
    "timeout -s KILL 5 bash -c '{}'",
    "timeout 0.5 zsh -c '{}'",
    "exec -a x bash -c '{}'",
    "setsid eval '{}'",
    "gs child -- {}",
    "gs --repo /x child -- {}",
    "command {}",
    "xargs -n 1 {}",
]
# 안의 따옴표가 바깥 따옴표와 겹치는 명령(CORE의 `-S '…'`)은 감싸지 않는다
NOT_WRAPPED = {"env -S 'env -u GS_ROLE claude -p hi'", "env --split-string='env -u GS_ROLE claude -p hi'"}

PASSED = [
    "echo $GS_ROLE",
    'echo "role is $GS_ROLE"',
    "env | grep GS_",
    "env",
    "printenv GS_ROLE",
    "printenv | grep GS_ROLE",
    "env -u CLAUDE_EFFORT claude -p hi",
    "env -u CLAUDECODE -u CLAUDE_CODE_SESSION_ID claude -p hi",
    "env -u GS_ROLE_OTHER claude -p hi",
    "env FOO=1 claude -p hi",
    "env GS_ROLE=worker claude -p hi",  # 값이 그대로라 아무것도 바꾸지 않는다
    "env -i GS_ROLE=worker claude -p hi",
    "GS_ROLE=worker true",
    "export GS_ROLE=worker",
    "export GS_ROLE",
    "export FOO=1",
    "unset FOO",
    "unset GS_ROLES",
    "gs child -- claude -p hi",
    "gs child -- env -u CLAUDE_EFFORT claude -p hi",
    "setsid bash -c 'echo $GS_ROLE'",
    "env -u CLAUDE_EFFORT bash -c 'env | grep GS_'",
    "export -n FOO=1",
    "grep GS_ROLE src/gs/hook.py",
    'git commit -m "unset GS_ROLE 막기"',
    "git commit -m 'env -u GS_ROLE claude -p hi'",
    "git commit -m x\n",
    "echo hi > out.txt",
    "sudo ls",
    "timeout 5 ls",
    "exec ls",
    "bash -c 'echo $GS_ROLE'",
    "bash -c 'env | grep GS_'",
    # heredoc 본문은 데이터다
    "git commit -F - <<'EOF'\nunset GS_ROLE\nenv -u GS_ROLE claude -p hi\nexport GS_ROLE=other\nGS_ROLE=x y\nEOF",
    "cat > notes.md <<EOF\nunset GS_ROLE\nEOF\necho done",
    # 주석도 데이터다
    "echo hi # unset GS_ROLE",
]
# 알려진 오차단: 명령 분해가 따옴표를 벗겨 따옴표 속 `;`를 명령 구분으로 읽는다(머리말 `echo ';' zsh -c`와 같은 원인)
KNOWN_OVERBLOCK = ["echo ';' unset GS_ROLE"]


def wrapped():
    for core in CORE:
        for shell in SHELLS:
            if shell == "{}" or core not in NOT_WRAPPED:
                yield core, shell, shell.replace("{{", "{").replace("}}", "}").replace("{}", core)


class RoleStripTest(unittest.TestCase):
    def verdict(self, command, env=None):
        payload = {"cwd": WT, "tool_name": "Bash", "tool_input": {"command": command}}
        return hook.decide(payload, WORKER if env is None else env)

    def test_core_forms_blocked(self):
        for command in CORE:
            with self.subTest(command=command):
                self.assertIsNotNone(self.verdict(command), command)

    def test_blocked_forms_in_any_position(self):
        count = 0
        for core, shell, command in wrapped():
            with self.subTest(core=core, shell=shell):
                self.assertIsNotNone(self.verdict(command), command)
            count += 1
        self.assertGreater(count, 600)

    def test_reason_explains_and_points_to_gs_child(self):
        for command in ["env -u GS_ROLE claude -p hi", "env -i claude", "env GS_ROLE=x claude", "unset GS_ROLE",
                        "export GS_ROLE=x", "GS_ROLE=x claude", "export -n GS_ROLE", "bash -c 'unset GS_ROLE'"]:
            with self.subTest(command=command):
                reason = self.verdict(command)
                self.assertIn("`GS_ROLE`", reason)
                self.assertIn("바꿀 수 없다", reason)
                self.assertIn("`gs child -- <명령>`", reason)
                self.assertIn("GS_*는 남고 Claude Code 세션 변수만 지운다", reason)

    def test_reason_names_the_form(self):
        """어느 형태가 걸렸는지 이유에 남는다."""
        for command, form in [("env -u GS_ROLE x", "env -u GS_ROLE"), ("env --unset=GS_ROLE x", "env --unset=GS_ROLE"),
                              ("env -i x", "env -i"), ("env GS_ROLE=x y", "env GS_ROLE=<값>"),
                              ("unset GS_ROLE", "unset GS_ROLE"), ("export GS_ROLE=x", "export GS_ROLE=<값>"),
                              ("export -n GS_ROLE", "export -n GS_ROLE"), ("GS_ROLE=x y", "GS_ROLE=<값> <명령>")]:
            with self.subTest(command=command):
                self.assertIn(form, self.verdict(command))

    def test_gs_child_command_gets_the_same_verdict(self):
        """`gs child -- <명령>`은 `<명령>`을 그대로 exec한다. 그 명령도 기존 hook 판정을 받는다."""
        self.assertIsNotNone(self.verdict("gs child -- git push"))
        self.assertIsNotNone(self.verdict("gs --repo /x child -- setsid bash -c 'git push'"))
        self.assertIsNone(self.verdict("gs child"))

    def test_outer_checks_still_run_after_wrapped_shell_or_gs_child(self):
        """앞붙이 뒤 셸 본문·`gs child`를 본 뒤에도 바깥 리다이렉션·xargs 치환 판정이 돈다."""
        out = "/gs-test-nowhere/outside.txt"
        secret = "/gs-test-nowhere/home/.ssh/id_ed25519"
        for command in [f"env -u CLAUDE_EFFORT bash -c 'echo ok' > {out}",
                        f"setsid bash -c 'echo ok' < {secret}",
                        f"gs child > {out}", f"gs child 2> {out}", f"gs child < {secret}",
                        f"gs child -- echo ok > {out}",
                        "echo git | xargs -I eval eval push",
                        "echo git | xargs -I bash bash -c push",
                        "echo pkill | xargs -I gs gs child",
                        "echo push | xargs gs child -- git",
                        "echo pu | setsid xargs -I X bash -c 'git Xsh origin'"]:
            with self.subTest(command=command):
                self.assertIsNotNone(self.verdict(command), command)

    def test_gs_child_repeated_does_not_recurse_forever(self):
        self.assertIsNone(self.verdict("gs child -- " * 1000 + "echo ok"))

    def test_passed_forms(self):
        for command in PASSED:
            with self.subTest(command=command):
                self.assertIsNone(self.verdict(command), command)

    def test_known_overblock_is_pinned(self):
        """`echo ';' unset GS_ROLE`: 따옴표 정보를 잃어 뒤쪽을 명령으로 읽는다. 이 hook의 기존 한계다."""
        for command in KNOWN_OVERBLOCK:
            with self.subTest(command=command):
                self.assertIn("`GS_ROLE`", self.verdict(command) or "")

    def test_without_worker_role_everything_passes(self):
        for env in [{}, {"GS_ROLE": ""}, {"GS_ROLE": "reviewer"}, {"HOME": "/x"}]:
            for command in [*CORE, *(c for _, _, c in wrapped())]:
                self.assertIsNone(self.verdict(command, env), (env, command))
        for command in CORE:
            for env in [{}, {"GS_ROLE": "reviewer"}]:
                self.assertIsNone(self.verdict(command, env), command)

    def test_main_entry_blocks_with_exit_2_and_reason(self):
        def run(command, env):
            err = io.StringIO()
            stdin = io.StringIO(json.dumps({"cwd": WT, "tool_name": "Bash", "tool_input": {"command": command}}))
            with contextlib.redirect_stderr(err):
                return hook.main(["pretooluse"], stdin=stdin, env=env), err.getvalue()

        code, err = run("env -u GS_ROLE claude -p hi", WORKER)
        self.assertEqual(code, 2)
        self.assertIn("gs가 막음", err)
        self.assertIn("gs child -- <명령>", err)
        self.assertEqual(run("env -u GS_ROLE claude -p hi", {}), (0, ""))
        self.assertEqual(run("echo $GS_ROLE", WORKER), (0, ""))

    def test_strip_prefix_alone_would_miss_these(self):
        """판정을 `strip_prefix` 후로 하면 놓치는 형태가 실제로 있다(전 argv로 봐야 하는 이유)."""
        self.assertEqual(hook.strip_prefix(["GS_ROLE=x", "claude"]), ["claude"])
        self.assertEqual(hook.strip_prefix(["env", "-i", "claude"]), ["claude"])
        self.assertEqual(hook.strip_prefix(["env", "-u", "GS_ROLE", "claude"])[0], "GS_ROLE")
        for argv in (["GS_ROLE=x", "claude"], ["env", "-i", "claude"], ["env", "-u", "GS_ROLE", "claude"]):
            self.assertIsNotNone(hook.check_role_strip(argv), argv)


if __name__ == "__main__":
    unittest.main()
