"""가짜 판단 스크립트(시험 fixture)는 두 호출이 겹쳐도 자기 입력으로 답한다.

두 리뷰어의 판단 호출은 동시에 돈다(go의 리뷰 스레드). 가짜 판단이 입력을 공용 파일 `judge.input`에 쓰고 그 파일을 다시 읽으면
겹친 호출이 서로의 입력으로 답하고, 한쪽 리뷰어의 지적이 틀리게 분류된다. 리눅스 CI에서 `RepairReviewTest`가 그렇게 떨어졌다
(.goldstack/ideas/ci-tests-job-red-unread.md). 여기서는 그 겹침을 정해진 순서로 만든다: 먼저 뜬 호출 A를 입력을 받은 직후의
첫 `grep`에서 붙잡아 두고, 그사이 호출 B를 끝까지 돌린 뒤 A를 놓는다.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import support
import test_repair_review_defer
import test_replay_run

HOLD = "FAKE_JUDGE_HOLD"
# 이 변수가 있으면 그 파일이 생길 때까지 기다렸다가 진짜 grep을 부른다
GREP = f'#!/bin/bash\nif [ -n "${HOLD}" ]; then while [ ! -e "${HOLD}" ]; do sleep 0.01; done; fi\nexec "%s" "$@"\n'
LIMIT = 30  # 붙잡힌 호출이 풀리지 않을 때 시험이 멈추지 않게 하는 상한(초). 통과하는 길에서는 닿지 않는다

CLASSIFIERS = {
    "support.FAKE_REVIEW_JUDGE": "#!/bin/bash\n" + support.FAKE_REVIEW_JUDGE,
    "test_replay_run.FAKE_JUDGE": test_replay_run.FAKE_JUDGE % {"py": sys.executable},
    "test_repair_review_defer.JUDGE": test_repair_review_defer.JUDGE,
}


class OverlapTest(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.bin = self.root / "bin"
        shim = self.root / "shim"
        self.bin.mkdir()
        shim.mkdir()
        (shim / "grep").write_text(GREP % shutil.which("grep"))
        (shim / "grep").chmod(0o755)
        self.env = {**os.environ, "PATH": f"{shim}{os.pathsep}{os.environ['PATH']}", "PY": sys.executable}
        self.env.pop(HOLD, None)

    def judge(self, script: str) -> Path:
        path = self.bin / "judge"
        path.write_text(script)
        path.chmod(0o755)
        return path

    def overlapped(self, script: str, first: str, second: str) -> tuple[str, str]:
        """A(first)를 입력 직후에 붙잡고 B(second)를 끝낸 뒤 A를 놓는다. 두 호출의 출력을 돌려준다."""
        judge, release, given = self.judge(script), self.root / "release", self.root / "first.prompt"
        release.unlink(missing_ok=True)
        (self.bin / "judge.input").unlink(missing_ok=True)
        given.write_text(first)
        with given.open() as stdin:
            a = subprocess.Popen([str(judge)], stdin=stdin, stdout=subprocess.PIPE, text=True,
                                 env={**self.env, HOLD: str(release)})
        self.addCleanup(a.kill)
        self.addCleanup(release.touch)  # 먼저 돈다: 단언이 실패해도 붙잡힌 grep이 풀려 끝난다(부모만 죽이면 그 루프가 남는다)
        seen = self.bin / "judge.input"  # 가짜 판단이 시험에 보이려고 남기는 입력. A가 입력을 다 받았다는 표시로 쓴다
        deadline = time.monotonic() + LIMIT
        while not (seen.exists() and seen.read_text() == first):
            self.assertLess(time.monotonic(), deadline, "첫 호출이 입력을 judge.input에 남기지 않았다")
            time.sleep(0.01)
        b = subprocess.run([str(judge)], input=second, capture_output=True, text=True, env=self.env, timeout=LIMIT)
        self.assertIsNone(a.poll(), "첫 호출이 붙잡히지 않고 끝났다. 겹침이 만들어지지 않았다")
        release.touch()
        out, _ = a.communicate(timeout=LIMIT)
        return out, b.stdout

    def test_classifiers_answer_from_their_own_findings(self):
        for name, script in CLASSIFIERS.items():
            with self.subTest(judge=name):
                prompts = {}
                for who, number in (("a", 7), ("b", 9)):
                    path = self.root / name / who / "findings.json"
                    path.parent.mkdir(parents=True)
                    path.write_text(json.dumps({"findings": [{"id": number, "claim": "FIX DEFER"}]}))
                    prompts[who] = f"지적 파일: `{path}`\n"
                first, second = self.overlapped(script, prompts["a"], prompts["b"])
                ids = [[d["id"] for d in json.loads(out)["decisions"]] for out in (first, second)]
                self.assertEqual(ids, [[7], [9]])

    def test_failure_summary_reads_its_own_log(self):
        prompts = {}
        for who in ("a", "b"):
            log = self.root / f"{who}.log"
            log.write_text(f"{who} 검증 로그\n")
            prompts[who] = f"실패를 요약해라\n{log}\n"
        first, second = self.overlapped("#!/bin/bash\n" + support.FAKE_JUDGE, prompts["a"], prompts["b"])
        self.assertIn("a 검증 로그", first)
        self.assertIn("b 검증 로그", second)


if __name__ == "__main__":
    unittest.main()
