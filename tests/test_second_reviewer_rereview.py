"""goldstack-v38 04: config `[review] second_reviewer_rereview`로 두 번째 리뷰어를 부르는 재리뷰 회차를 줄인다.

all(기본, 키가 없어도)은 지금처럼 모든 재리뷰에 부른다. first는 1차 재리뷰까지, none은 어느 재리뷰에도 부르지 않는다.
빠진 회차에는 그 리뷰어 기록의 판정할 지적을 첫 리뷰어 재리뷰가 함께 판정한다(go._rereview_slots). 지적 id는 기록마다 1부터라 겹치므로
호출용 id를 주고(go._lent_ids) 판정은 원래 기록의 지적에 판정한 리뷰어(rereview_by·repair_review_by)와 함께 적는다.

RereviewTest는 test_recheck_resolved의 가짜 리뷰어(트리에 fixed_<X>가 있으면 "FIX X: …" 지적이 resolved)로 재리뷰를 끝까지 돌린다.
RepairReviewTest는 검증 실패 → 수리 → 수리 재리뷰를 돌리고, 가짜 리뷰어가 프롬프트의 defer 지적 줄을 읽어 id마다 판정한다.
"""
import json
import os
import sys
import textwrap
import unittest
from unittest import mock

import test_recheck_resolved
import test_repair_review_defer
from test_recheck_resolved import A, B, FIXED, UNFIXED
from test_verify_repair import BREAKS, REPAIRS

from gs import config, review, state

SETTING = "second_reviewer_rereview"


def set_rereview(test, value):
    """`.goldstack/config.toml`에 `[review] second_reviewer_rereview`를 적고 커밋·push한다(gs go는 커밋된 설정을 쓴다)."""
    path = test.repo / config.CONFIG_PATH
    path.write_text(path.read_text() + f'\n[review]\n{SETTING} = "{value}"\n')
    test.commit(f"{SETTING} {value}")


class RereviewTest(test_recheck_resolved.Base):
    def setting(self, value):
        set_rereview(self, value)

    def b_left_after_first_fix(self, *second):
        """codex가 A, agy가 B를 낸다. 1차 수정은 A만 고쳐 B가 1차 재리뷰에서 unresolved로 남고 2차 수정이 돈다. 2차 수정은 second를 한다."""
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.plan(1, "touch fixed_A")
        self.plan(2, *second)

    def agy_rereviews(self):
        return [line for line in self.lines("rereview.calls") if line.startswith("agy")]

    def listed(self, who, n):
        """그 호출이 받은 지적: (호출 id, claim, 원래 리뷰어)."""
        found = json.loads((self.bin / f"rereview.findings.{who}.{n}").read_text())["findings"]
        return [(f["id"], f["claim"], f.get("reviewer")) for f in found]

    def test_first_does_not_call_second_reviewer_in_second_rereview(self):
        """(1) first: 2차 재리뷰에 agy를 부르지 않고 agy의 B를 codex가 판정해 resolved가 된다. agy 호출로 세지 않는다."""
        self.setting("first")
        self.b_left_after_first_fix("touch fixed_B")
        out = self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 2)  # 첫 리뷰 + 1차 재리뷰
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], None), (2, B["claim"], "agy")])
        self.assertIn("다른 리뷰어(agy)가 낸 지적이다", (self.bin / "rereview.prompt.codex.2").read_text())
        ts = self.ts()
        [a], [b] = ts.review["findings"], ts.second_review["findings"]
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        self.assertEqual((b["rereview_evidence"], b["rereview_by"]), ("fixed_B 있음", "codex"))
        self.assertEqual(self.result(a), (1, review.RESOLVED, 2))
        self.assertNotIn("rereview_by", a)
        # 1차 재리뷰의 판정은 agy 자신이 했다: 그 회차 기록이 agy에 있고, 2차 회차 기록은 codex에만 있다
        self.assertEqual([x["round"] for x in ts.second_review["rereviews"]], [1])
        self.assertEqual(ts.review["rereviews"][-1]["lent"], [{"reviewer": "agy", "id": 1, "call_id": 2}])
        self.assertIn("재리뷰 2차(agy는 부르지 않고 codex가 판정): resolved 1", ts.second_review["fix"])
        self.assertIn("codex가 agy의 지적 1개를 함께 판정한다", out)
        self.assertIn(FIXED, self.report_line("FIX B"))
        self.assertIn("리뷰 지적: 수정됨 2", self.final_report())

    def test_all_calls_both_reviewers_like_before(self):
        """(2) all: 2차 재리뷰도 둘 다 부르고 각자 판정한다. 판정한 리뷰어 표시는 없다."""
        self.setting("all")
        self.b_left_after_first_fix("touch fixed_B")
        self.run_ok()
        self.assert_both_called()

    def test_missing_key_is_all(self):
        self.b_left_after_first_fix("touch fixed_B")
        self.run_ok()
        self.assert_both_called()

    def assert_both_called(self):
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "agy 2", "codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 3)
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], None)])
        self.assertEqual(self.listed("agy", 2), [(1, B["claim"], None)])
        self.assertNotIn("다른 리뷰어", (self.bin / "rereview.prompt.codex.2").read_text())
        ts = self.ts()
        [a], [b] = ts.review["findings"], ts.second_review["findings"]
        self.assertEqual(self.result(b), (2, review.RESOLVED, 2))
        for f in (a, b):
            self.assertNotIn("rereview_by", f)
        self.assertNotIn("lent", ts.review["rereviews"][-1])

    def test_overlapping_ids_get_their_own_verdicts(self):
        """(4) codex의 A와 agy의 B가 둘 다 id 1이다. 호출에서는 1·2로 나뉘고 판정은 각 원래 지적에 맞게 적힌다(A unresolved, B resolved)."""
        self.setting("first")
        self.b_left_after_first_fix("touch fixed_B", "rm fixed_A")
        self.run_ok()
        ts = self.ts()
        [a], [b] = ts.review["findings"], ts.second_review["findings"]
        self.assertEqual((a["id"], b["id"]), (1, 1))
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], None), (2, B["claim"], "agy")])
        self.assertEqual((self.result(a), a["rereview_evidence"]), ((1, review.UNRESOLVED, 2), "fixed_A 없음"))
        self.assertEqual((self.result(b), b["rereview_evidence"], b["rereview_by"]),
                         ((2, review.RESOLVED, 2), "fixed_B 있음", "codex"))
        self.assertIn(UNFIXED, self.report_line("FIX A"))
        self.assertIn(FIXED, self.report_line("FIX B"))

    def test_none_skips_second_reviewer_in_first_rereview_too(self):
        self.setting("none")
        self.two_reviewers()
        self.findings("codex", A)
        self.findings("agy", B)
        self.plan(1, "touch fixed_A")
        self.plan(2, "touch fixed_B")
        self.run_ok()
        self.assertEqual(self.lines("rereview.calls"), ["codex 1", "codex 2"])
        self.assertEqual(self.run_state().agy_calls, 1)  # 첫 리뷰만
        self.assertEqual(self.listed("codex", 1), [(1, A["claim"], None), (2, B["claim"], "agy")])
        self.assertEqual(self.listed("codex", 2), [(1, A["claim"], None), (2, B["claim"], "agy")])
        b = self.ts().second_review["findings"][0]
        self.assertEqual((self.result(b), b["rereview_by"]), ((2, review.RESOLVED, 2), "codex"))
        self.assertNotIn("rereviews", self.ts().second_review)
        brief = (self.rundir / "01/1/fix2/brief.md").read_text()  # codex가 unresolved로 판정한 B를 2차 수정이 받는다
        self.assertIn("FIX B", brief)
        self.assertNotIn("FIX A", brief)

    def test_first_reviewer_at_agy_limit_leaves_the_lent_finding_unchecked(self):
        """첫 리뷰어(agy)도 상한에 닿아 부를 수 없으면 두 번째 리뷰어(codex)의 지적은 unchecked(한도)다. codex를 대신 부르지 않는다."""
        self.setting("first")
        self.limit(2)  # agy: 첫 리뷰 + 1차 재리뷰로 다 쓴다
        self.tickets(**{"01": ("claude", "agy", "codex", "[]")})
        self.findings("agy", A)
        self.findings("codex", B)
        self.plan(1, "touch fixed_A")
        self.plan(2, "touch fixed_B")
        self.run_ok()
        self.assertEqual(sorted(self.lines("rereview.calls")), ["agy 1", "codex 1"])
        ts = self.ts()
        b = ts.second_review["findings"][0]
        self.assertEqual((b["rereview"], b["rereview_reason"], b["rereview_round"]), (review.UNCHECKED, review.REASON_LIMIT, 2))
        self.assertNotIn("rereview_by", b)
        self.assertIn("판정을 맡을 agy", ts.second_review["fix"])
        self.assertIn(f"{test_recheck_resolved.UNKNOWN}({review.REASON_LIMIT})", self.report_line("FIX B"))

    def test_resumed_second_rereview_picks_the_same_reviewer(self):
        """2차 재리뷰 도중 끊겨 다음 gs go가 그 회차부터 이어도 agy를 부르지 않고 codex가 B를 판정한다."""
        self.network_limit(1)
        self.setting("first")
        self.b_left_after_first_fix("touch fixed_B")
        (self.bin / "down_codex").write_text("2")  # codex의 두 번째 재리뷰 호출부터 끊긴다
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 3, out + err)
        self.assertEqual(self.ts().network_resume["fix"], 2)
        self.assertEqual(self.agy_rereviews(), ["agy 1"])
        self.assertEqual(self.ts().second_review["findings"][0]["rereview_round"], 1)  # 아직 2차 판정이 없다

        (self.bin / "up").touch()
        self.run_ok()
        self.assertEqual(self.agy_rereviews(), ["agy 1"])
        self.assertEqual(self.run_state().agy_calls, 0)  # 이은 실행은 agy를 부르지 않았다(실행마다 센다)
        last = self.lines("rereview.calls")[-1]
        self.assertEqual(self.listed(*last.split()), [(1, A["claim"], None), (2, B["claim"], "agy")])
        b = self.ts().second_review["findings"][0]
        self.assertEqual((self.result(b), b["rereview_by"]), ((2, review.RESOLVED, 2), "codex"))


# 가짜 리뷰어: 첫 리뷰는 first_<who>.json을 낸다. 수리 재리뷰는 프롬프트의 defer 지적 줄(`- id N [...] 위치: claim`)마다
# claim에 FIXED가 있으면 resolved, 아니면 unresolved로 판정한다. 그래서 어떤 호출 id가 오든 지적 글로 판정이 정해진다.
REPAIR_REVIEWER = textwrap.dedent('''\
    here="$(dirname "$0")"
    who="$GS_REVIEWER"
    in="$(mktemp)"; cat > "$in"
    if grep -q '수리 커밋 diff' "$in"; then
      echo "repair $who" >> "$here/review.calls"
      cp "$in" "$here/repair.prompt.$who"
      exec "$PY" - "$in" <<'PYEOF'
    import json, re, sys
    rows = re.findall(r"^- id (\\d+) \\[\\w+\\] .*?: (.*)$", open(sys.argv[1]).read(), re.M)
    print(json.dumps({"verdicts": [{"id": int(i), "status": "resolved" if "FIXED" in claim else "unresolved",
                                    "evidence": f"수리 커밋을 읽었다: {claim[:20]}"} for i, claim in rows],
                      "findings": []}, ensure_ascii=False))
    PYEOF
    fi
    echo "first $who" >> "$here/review.calls"
    cat "$here/first_$who.json"
''')

CODEX_DEFER = {"severity": "medium", "location": "util.py:3", "claim": "DEFER util.py가 빈 입력에서 틀린다(STILL)", "evidence": "재현: exit 1"}
AGY_DEFER = {"severity": "medium", "location": "other.py:9", "claim": "DEFER other.py 경계값(FIXED)", "evidence": "재현: exit 2"}


class RepairReviewTest(test_repair_review_defer.Base):
    def setUp(self):
        super().setUp()
        agy = self.bin / "agy"  # gs check가 PATH에서 찾는다. 리뷰는 GS_REVIEWER_CMD로 바꿔 끼운다
        agy.write_text("#!/bin/sh\nexit 1\n")
        agy.chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PY": sys.executable})
        patch.start()
        self.addCleanup(patch.stop)
        test_recheck_resolved.Base.tickets(self, **{"01": ("claude", "codex", "agy", "[]")})
        (self.bin / "reviewer.sh").write_text(REPAIR_REVIEWER)
        (self.bin / "judge").write_text(test_repair_review_defer.JUDGE)

    commit = test_recheck_resolved.Base.commit

    def first(self, who, *found):
        (self.bin / f"first_{who}.json").write_text(json.dumps({"findings": list(found)}, ensure_ascii=False))

    def run_repair(self):
        self.worker(BREAKS, REPAIRS)
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.ts().status, "merged")
        return out

    def test_first_skips_second_reviewer_and_first_reviewer_judges_its_defer_findings(self):
        """(3)·(4) first: 수리 재리뷰에 agy를 부르지 않는다. agy의 defer 지적(id 1)을 codex가 자기 defer 지적(id 1)과 함께 호출 id 1·2로 판정한다."""
        set_rereview(self, "first")
        self.first("codex", CODEX_DEFER)
        self.first("agy", AGY_DEFER)
        out = self.run_repair()
        self.assertEqual(sorted(self.lines("review.calls")), ["first agy", "first codex", "repair codex"])
        self.assertEqual(state.load(self.rundir, "demo").agy_calls, 1)  # 첫 리뷰만
        prompt = (self.bin / "repair.prompt.codex").read_text()
        self.assertIn(f"- id 1 [medium] util.py:3: {CODEX_DEFER['claim']}\n  네가 댄 근거: 재현: exit 1", prompt)
        self.assertIn(f"- id 2 [medium] other.py:9: {AGY_DEFER['claim']} (다른 리뷰어 agy의 지적)\n  그 리뷰어가 댄 근거: 재현: exit 2", prompt)
        self.assertIn("다른 리뷰어(agy)가 낸 defer 지적이다", prompt)
        ts = self.ts()
        [mine], [lent] = ts.review["findings"], ts.second_review["findings"]
        self.assertEqual((mine["id"], lent["id"]), (1, 1))
        self.assertEqual(mine["repair_review"], review.UNRESOLVED)
        self.assertNotIn("repair_review_by", mine)
        self.assertEqual((lent["repair_review"], lent["repair_review_by"]), (review.RESOLVED, "codex"))
        self.assertTrue(lent["repair_review_evidence"].startswith("수리 커밋을 읽었다"))
        self.assertTrue(review.repair_resolved(lent))
        self.assertEqual(ts.review["rereviews"][-1]["lent"], [{"reviewer": "agy", "id": 1, "call_id": 2}])
        self.assertIn("수리 재리뷰: 부르지 않았다(second_reviewer_rereview = first)", ts.second_review["fix"])
        self.assertIn("수리 재리뷰(agy는 부르지 않고 codex가 defer 지적 판정): resolved 1 / 1", ts.second_review["fix"])
        self.assertNotIn("rereviews", ts.second_review)
        final = self.final_report()
        self.assertIn(f"{AGY_DEFER['claim']} — 상태: 수정됨(수리 재리뷰 확인)", final)
        self.assertIn(f"{CODEX_DEFER['claim']} — 상태: 재현된 미수리", final)
        self.assertIn("수리 재리뷰: 부르지 않았다", out)

    def test_all_calls_both_reviewers_in_repair_review(self):
        set_rereview(self, "all")
        self.first("codex", CODEX_DEFER)
        self.first("agy", AGY_DEFER)
        self.run_repair()
        self.assertEqual(sorted(self.lines("review.calls")), ["first agy", "first codex", "repair agy", "repair codex"])
        self.assertEqual(state.load(self.rundir, "demo").agy_calls, 2)
        prompt = (self.bin / "repair.prompt.codex").read_text()
        self.assertNotIn("다른 리뷰어", prompt)
        self.assertNotIn(AGY_DEFER["claim"], prompt)
        self.assertIn(AGY_DEFER["claim"], (self.bin / "repair.prompt.agy").read_text())
        ts = self.ts()
        [mine], [own] = ts.review["findings"], ts.second_review["findings"]
        self.assertEqual((mine["repair_review"], own["repair_review"]), (review.UNRESOLVED, review.RESOLVED))
        for f in (mine, own):
            self.assertNotIn("repair_review_by", f)

    def test_first_without_defer_findings_just_skips_the_second_reviewer(self):
        set_rereview(self, "first")
        self.first("codex")
        self.first("agy")
        out = self.run_repair()
        self.assertEqual(sorted(self.lines("review.calls")), ["first agy", "first codex", "repair codex"])
        self.assertNotIn("다른 리뷰어", (self.bin / "repair.prompt.codex").read_text())
        self.assertIn("수리 재리뷰: 부르지 않았다(second_reviewer_rereview = first)", self.ts().second_review["fix"])
        self.assertNotIn("판정한다", self.ts().second_review["fix"])
        self.assertIn("[01] 수리 재리뷰: codex\n", out)


if __name__ == "__main__":
    unittest.main()
