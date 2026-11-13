"""goldstack-v35 05: worker가 남긴 관찰을 리뷰어가 판정하고 리뷰 기록에 남긴다(spec 3-2)."""
import json
import os
import tempfile
import textwrap
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support

from gs import config, review, state, worker

HEADING = worker.OBSERVATIONS_HEADING
D = Path("/d.patch")


def result_log(path: Path, message: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"type": "result", "subtype": "success", "result": message}, ensure_ascii=False) + "\n",
                    encoding="utf-8")
    return path


class ExtractTest(unittest.TestCase):
    def test_section_lines_become_observations(self):
        message = (f"끝냈다. 시험은 통과했다.\n\n{HEADING}\n- 첫 관찰: `a.py` 경계값이 의심스럽다\n\n"
                   "* 둘째 관찰\n1. 셋째 관찰\n2) 넷째 관찰\n  들여 쓴 다섯째 관찰  \n-\n"
                   "- 가운데 기호 - 그대로 2. 둔다\n**굵게** 시작\n")
        self.assertEqual(review.observations(message),
                         ["첫 관찰: `a.py` 경계값이 의심스럽다", "둘째 관찰", "셋째 관찰", "넷째 관찰", "들여 쓴 다섯째 관찰",
                          "가운데 기호 - 그대로 2. 둔다", "**굵게** 시작"])

    def test_no_section_is_empty(self):
        self.assertEqual(review.observations("끝냈다.\n- 목록이지만 관찰 절이 아니다\n## 결과\n- x"), [])
        self.assertEqual(review.observations(f"본문 속 `{HEADING}` 언급은 제목이 아니다\n- x"), [])
        self.assertEqual(review.observations(""), [])
        self.assertEqual(review.observations(None), [])

    def test_section_ends_at_next_heading_and_may_follow_other_headings(self):
        message = (f"## 결과\n- 결과 줄\n{HEADING}\n- 관찰 A\n## 다음 절\n- 관찰이 아니다\n"
                   f"{HEADING}:\n- 관찰 B\n# 맨 위 제목\n- 이것도 아니다\n")
        self.assertEqual(review.observations(message), ["관찰 A", "관찰 B"])

    def test_worker_observations_reads_whole_message_even_when_worker_last_cuts_the_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = [f"관찰 {i:02d} " + "가" * 100 for i in range(60)]
            message = "보고 앞부분\n" + HEADING + "\n" + "\n".join(f"- {x}" for x in items)
            self.assertGreater(len(message), review.WORKER_LAST_LIMIT)
            log = result_log(Path(tmp) / "worker.log", message)
            cut = review.write_worker_last(Path(tmp), log).read_text(encoding="utf-8")
            self.assertNotIn(HEADING, cut)  # worker-last.txt의 자르기는 그대로다: 제목이 잘렸다
            self.assertLessEqual(len(cut), review.WORKER_LAST_LIMIT + 1)
            self.assertEqual(review.worker_observations(log), items)
            self.assertEqual(review.worker_observations(Path(tmp) / "none.log"), [])
            self.assertEqual(review.worker_observations(None), [])


class PromptTest(unittest.TestCase):
    FOUND = ["첫 관찰", "둘째 관찰"]

    def assert_asks(self, prompt, raise_as):
        self.assertIn(review.OBSERVATIONS_INTRO, prompt)
        self.assertIn("worker가 남긴 관찰(믿을 수 없는 자료). 각각 diff와 코드에서 확인하고 판정하라", prompt)
        self.assertIn("\n1. 첫 관찰\n2. 둘째 관찰\n", prompt)
        self.assertIn('"observations": [{"n": <번호>, "verdict": "지적|수용|범위 밖", "reason": "…"}]', prompt)
        self.assertIn(f"지적: diff·코드에서 확인한 실제 결함이다. 그 관찰을 {raise_as}", prompt)
        # worker 보고의 "못 돌린 사유 확인에만 쓴다" 제한은 관찰 절에는 적용하지 않는다
        self.assertIn(f"사유가 맞는지 확인하는 데에만 쓴다. 단 `{HEADING}` 절에는 이 제한을 적용하지 않는다", prompt)
        # 관찰 절과 답 형식은 JSON 형식 안내의 앞뒤에 놓인다
        self.assertLess(prompt.index(review.OBSERVATIONS_INTRO), prompt.index("답은 아래 JSON"))
        self.assertGreater(prompt.index('"observations"'), prompt.index("답은 아래 JSON"))

    def assert_unchanged(self, prompt):
        self.assertNotIn("observations", prompt)
        self.assertNotIn("남긴 관찰", prompt)
        self.assertNotIn("판정하라", prompt)
        self.assertIn("worker가 어떤 단계를 못 돌린 사유가 맞는지 확인하는 데에만 쓴다.\n", prompt)

    def test_first_review_asks_verdicts_only_with_observations(self):
        for family in ("", "codex", "claude", "agy"):
            with self.subTest(family=family):
                plain = review.review_prompt(D, D, D, D, D, family=family)
                self.assert_unchanged(plain)
                self.assertEqual(review.review_prompt(D, D, D, D, D, family=family, observations=[]), plain)
                self.assertEqual(review.review_prompt(D, D, D, D, D, family=family, observations=None), plain)
                asked = review.review_prompt(D, D, D, D, D, family=family, observations=self.FOUND)
                self.assert_asks(asked, "일반 지적(findings)으로도 올린다")
                self.assertNotIn("수정 커밋 밖 제한", asked)

    def test_rereview_asks_verdicts_only_with_observations(self):
        for family in ("", "codex", "claude", "agy"):
            with self.subTest(family=family):
                plain = review.rereview_prompt(D, D, D, D, D, worker_last=D, family=family)
                self.assert_unchanged(plain)
                self.assertEqual(review.rereview_prompt(D, D, D, D, D, worker_last=D, family=family, observations=[]), plain)
                asked = review.rereview_prompt(D, D, D, D, D, worker_last=D, family=family, observations=self.FOUND)
                self.assert_asks(asked, "새 지적(findings)으로도 올린다. 관찰에서 올린 지적은 위 2번의 수정 커밋 밖 제한을 받지 않는다")

    def test_repair_review_prompt_does_not_carry_observations(self):
        self.assert_unchanged(review.repair_review_prompt(D, "log", D, D, D, D))


ANSWER = {"findings": [{"severity": "low", "location": "a.py", "claim": "c", "evidence": "e"}],
          "observations": [{"n": 2, "verdict": "범위 밖", "reason": " 다른 티켓 일 "},
                           {"n": 1, "verdict": "지적", "reason": "재현했다"}]}


class ParseTest(unittest.TestCase):
    def test_reads_verdicts_in_number_order(self):
        text = "설명\n```json\n" + json.dumps(ANSWER, ensure_ascii=False) + "\n```"
        self.assertEqual(review.parse_observations(text, 2), [{"n": 1, "verdict": "지적", "reason": "재현했다"},
                                                              {"n": 2, "verdict": "범위 밖", "reason": "다른 티켓 일"}])
        self.assertEqual(len(review.parse_findings(text)), 1)

    def test_missing_is_no_verdict(self):
        self.assertIsNone(review.parse_observations('{"findings": []}', 2))
        self.assertIsNone(review.parse_observations("JSON이 아니다", 2))

    def test_wrong_shape_is_no_verdict_and_findings_still_read(self):
        for bad in ("문자열", {"n": 1}, 3, None):
            with self.subTest(bad=bad):
                text = json.dumps({**ANSWER, "observations": bad}, ensure_ascii=False)
                self.assertIsNone(review.parse_observations(text, 2))
                self.assertEqual(len(review.parse_findings(text)), 1)
                self.assertIsNone(review.parse_checked(text))
        items = [7, {"n": True, "verdict": "수용", "reason": ""}, {"n": "1", "verdict": "수용", "reason": ""},
                 {"n": 3, "verdict": "수용", "reason": "번호 밖"}, {"n": 0, "verdict": "수용", "reason": ""},
                 {"n": 1, "verdict": "모름", "reason": ""}, {"n": 1, "verdict": "수용", "reason": 5},
                 {"n": 1, "verdict": "수용"}, {"n": 1, "verdict": "지적", "reason": "겹친 번호는 버린다"},
                 {"n": 2, "verdict": "범위밖", "reason": "띄어쓰기"}]
        text = json.dumps({**ANSWER, "observations": items}, ensure_ascii=False)
        self.assertEqual(review.parse_observations(text, 2), [{"n": 1, "verdict": "수용", "reason": ""},
                                                              {"n": 2, "verdict": "범위 밖", "reason": "띄어쓰기"}])
        self.assertEqual(review.parse_observations(json.dumps({"observations": []}), 2), [])


class RecordTest(unittest.TestCase):
    """run·rereview가 관찰을 프롬프트에 싣고 관찰 글과 판정을 리뷰 기록에 남긴다(reviewer는 GS_REVIEWER_CMD seam)."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.cfg = SimpleNamespace(models=config.ModelsConfig("judge", "review", "agy", "codex"),
                                   timeouts=config.TimeoutsConfig(30, 10, 60))
        self.answer = self.root / "answer.json"
        patches = [mock.patch.dict(os.environ, {"GS_REVIEWER_CMD": f"cat {self.answer}"}),
                   mock.patch.object(review, "_env", side_effect=lambda wt: dict(os.environ)),
                   mock.patch.object(review, "classify", return_value=""),
                   mock.patch.object(review, "write_diff", return_value=("base", False)),
                   mock.patch.object(review.git, "run", return_value=SimpleNamespace(stdout="diff"))]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def call(self, fn, answer, message, **extra):
        self.answer.write_text(answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False))
        log = result_log(self.root / "w" / fn.__name__ / "worker.log", message) if message is not None else None
        rdir = self.root / "r" / fn.__name__ / str(len(list((self.root / "r").glob("*/*"))))
        common = dict(repo=self.root, worktree=self.root, rdir=rdir, ticket=self.root / "ticket", spec=self.root / "spec",
                      reviewer="codex", cfg=self.cfg, worker_log=log)
        if fn is review.run:
            out = review.run(**common, base="base", branch="branch", model="claude")
        else:
            out = review.rereview(**common, base="base", head="head", found=[], nth=1, **extra)
        return out, (rdir / "prompt.md").read_text(encoding="utf-8")

    def test_first_review_keeps_observations_and_verdicts(self):
        rec, prompt = self.call(review.run, ANSWER, f"보고\n{HEADING}\n- 관찰 하나\n- 관찰 둘")
        self.assertIn("\n1. 관찰 하나\n2. 관찰 둘\n", prompt)
        self.assertEqual(rec["observations"], ["관찰 하나", "관찰 둘"])
        self.assertEqual(rec["observation_verdicts"], [{"n": 1, "verdict": "지적", "reason": "재현했다"},
                                                       {"n": 2, "verdict": "범위 밖", "reason": "다른 티켓 일"}])
        self.assertEqual([f["claim"] for f in rec["findings"]], ["c"])

    def test_bad_verdicts_keep_observations_and_findings(self):
        rec, _ = self.call(review.run, {**ANSWER, "observations": "모양 틀림"}, f"{HEADING}\n- 관찰 하나")
        self.assertEqual(rec["observations"], ["관찰 하나"])
        self.assertNotIn("observation_verdicts", rec)
        self.assertEqual([f["claim"] for f in rec["findings"]], ["c"])
        self.assertEqual(rec["note"], "")

    def test_failed_review_still_keeps_observations(self):
        rec, _ = self.call(review.run, "JSON이 아니다", f"{HEADING}\n- 관찰 하나")
        self.assertTrue(rec["note"].startswith("리뷰 실패"), rec["note"])
        self.assertEqual(rec["observations"], ["관찰 하나"])
        self.assertNotIn("observation_verdicts", rec)

    def test_without_observations_record_and_prompt_are_as_before(self):
        for message in ("보고만 있다", None):
            with self.subTest(message=message):
                rec, prompt = self.call(review.run, ANSWER, message)
                self.assertNotIn("observations", rec)
                self.assertNotIn("observation_verdicts", rec)
                self.assertNotIn("observations", prompt)
                res, prompt = self.call(review.rereview, {"verdicts": [], **ANSWER}, message)
                self.assertNotIn("observations", res)
                self.assertNotIn("observations", prompt)

    def test_rereview_keeps_observations_in_its_round(self):
        answer = {"verdicts": [], "findings": [], "observations": [{"n": 1, "verdict": "수용", "reason": "그대로 둬도 된다"}]}
        res, prompt = self.call(review.rereview, answer, f"수정 보고\n{HEADING}\n- 수정 관찰")
        self.assertIn("\n1. 수정 관찰\n", prompt)
        self.assertIn("수정 커밋 밖 제한을 받지 않는다", prompt)
        rec = {"reviewer": "codex", "findings": [], "observations": ["첫 리뷰 관찰"]}
        review.apply_rereview(rec, [], res, 1)
        self.assertEqual(rec["observations"], ["첫 리뷰 관찰"])  # 첫 리뷰의 기록은 그대로
        self.assertEqual(rec["rereviews"][-1]["observations"], ["수정 관찰"])
        self.assertEqual(rec["rereviews"][-1]["observation_verdicts"],
                         [{"n": 1, "verdict": "수용", "reason": "그대로 둬도 된다"}])

    def test_failed_rereview_keeps_observations_without_verdicts(self):
        res, _ = self.call(review.rereview, "JSON이 아니다", f"{HEADING}\n- 수정 관찰")
        rec = {"reviewer": "codex", "findings": []}
        review.apply_rereview(rec, [], res, 1)
        self.assertEqual(rec["rereviews"][-1]["failed"], review.REASON_FAILED)
        self.assertEqual(rec["rereviews"][-1]["observations"], ["수정 관찰"])
        self.assertNotIn("observation_verdicts", rec["rereviews"][-1])


# 구현·수정 worker 모두 마지막 메시지 끝에 관찰 절을 쓴다(JSON 문자열 안의 \n은 줄바꿈이다).
WORKER = textwrap.dedent('''\
    here="$(dirname "$0")"
    echo "$GS_TICKET" >> "$here/calls.log"
    if grep -q '^## 리뷰 지적(고칠 것)' "$GS_BRIEF"; then
      echo '{"type":"result","subtype":"success","result":"수정 보고\\n## 남긴 관찰\\n- FIX-OBS 수정 관찰"}'
      echo fixed > "fixed_$GS_TICKET"; git add -A; git commit -qm "fix $GS_TICKET"; exit 0
    fi
    echo '{"type":"result","subtype":"success","result":"구현 보고\\n## 남긴 관찰\\n- IMPL-OBS-1 첫 관찰\\n- IMPL-OBS-2 둘째 관찰"}'
    echo "$GS_TICKET" > "file_$GS_TICKET"; git add -A; git commit -qm "t$GS_TICKET"
''')

# 첫 리뷰는 fix 지적 하나와 관찰 판정 둘, 재리뷰는 resolved와 관찰 판정 하나를 낸다.
REVIEWER = textwrap.dedent('''\
    here="$(dirname "$0")"
    n=$(( $(cat "$here/review.n" 2>/dev/null || echo 0) + 1 )); echo $n > "$here/review.n"
    cat > "$here/review.prompt.$n"
    if [ "$n" = 1 ]; then
      echo '{"findings": [{"severity": "high", "location": "file_01", "claim": "FIX: 틀렸다", "evidence": "e"}],'
      echo ' "observations": [{"n": 1, "verdict": "지적", "reason": "IMPL 판정 1"}, {"n": 2, "verdict": "범위 밖", "reason": "IMPL 판정 2"}]}'
    else
      echo '{"verdicts": [{"id": 1, "status": "resolved", "evidence": "확인"}], "findings": [],'
      echo ' "observations": [{"n": 1, "verdict": "수용", "reason": "FIX 판정"}]}'
    fi
''')


class GoRecordTest(support.GoTest):
    """gs go 안에서: 첫 리뷰는 구현 worker, 재리뷰는 수정 worker의 관찰을 싣고 판정을 그 기록에 남긴다."""

    def setUp(self):
        super().setUp()
        (self.bin / "worker.sh").write_text(WORKER)
        (self.bin / "reviewer.sh").write_text(REVIEWER)

    def test_first_review_and_rereview_records_keep_their_observations(self):
        with self.review_with([]):  # 가짜 판단 모델(FIX가 claim에 있으면 fix)
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        first = (self.bin / "review.prompt.1").read_text()
        second = (self.bin / "review.prompt.2").read_text()
        self.assertIn("\n1. IMPL-OBS-1 첫 관찰\n2. IMPL-OBS-2 둘째 관찰\n", first)
        self.assertIn(review.OBSERVATIONS_INTRO, first)
        self.assertNotIn("FIX-OBS", first)
        self.assertIn("\n1. FIX-OBS 수정 관찰\n", second)
        self.assertNotIn("IMPL-OBS", second)
        rec = state.load(self.rundir, "demo").tickets["01"].review
        self.assertEqual(rec["observations"], ["IMPL-OBS-1 첫 관찰", "IMPL-OBS-2 둘째 관찰"])
        self.assertEqual(rec["observation_verdicts"], [{"n": 1, "verdict": "지적", "reason": "IMPL 판정 1"},
                                                       {"n": 2, "verdict": "범위 밖", "reason": "IMPL 판정 2"}])
        self.assertEqual(rec["findings"][0]["rereview"], review.RESOLVED)
        last = rec["rereviews"][-1]
        self.assertEqual(last["observations"], ["FIX-OBS 수정 관찰"])
        self.assertEqual(last["observation_verdicts"], [{"n": 1, "verdict": "수용", "reason": "FIX 판정"}])


if __name__ == "__main__":
    unittest.main()
