"""goldstack-v9 07: 보고만 high·medium 지적을 `.goldstack/ideas/` 파일로, 보고서 커밋에 함께."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import support
import test_resume_report
from gs import backlog, cli, finish, findings, review, setup, state
from support import sh

REPORT = ".goldstack/work/demo/report.md"
IDEA = ".goldstack/ideas/demo-{}.md"
FINDINGS = [
    {"severity": "high", "location": "a.py:1", "claim": "높은 지적", "evidence": "근거 하나"},
    {"severity": "medium", "location": "b.py:2", "claim": "중간 지적", "evidence": "근거 둘"},
    {"severity": "low", "location": "c.py:3", "claim": "낮은 지적", "evidence": "근거 셋"},
]
HUMAN = '---\ndate: "2026-01-01"\nseverity: "high"\nsource: "사람"\nstatus: "taken"\nfeature: "next"\n---\n사람이 고침\n'


def finding(claim="지적", severity="high", location="a.py:1", number=1, **kw):
    fields = {"action": review.REPORT, "why": "고칠 만큼은 아니다", "evidence": "근거", **kw}
    return asdict(review.Finding(id=number, severity=severity, location=location, claim=claim, **fields))


def run_backlog(repo, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cli.main(["--repo", str(repo), "backlog", *args])
    return code, out.getvalue(), err.getvalue()


class Unit(unittest.TestCase):
    """임시 레포와 최소한의 실행 객체. 파일 쓰기만 본다."""

    def setUp(self):
        support.isolate_git_env(self)
        os.environ.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1", GIT_AUTHOR_NAME="t",
                          GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.repo = self.root / "repo"
        self.repo.mkdir()
        sh(self.repo, "git", "init", "-q", "-b", "main")
        sh(self.repo, "git", "commit", "-q", "--allow-empty", "-m", "init")
        self.rundir = self.root / "run"
        (self.rundir / "finish").mkdir(parents=True)
        st = state.State(feature="demo", started_at="2026-11-05T01:02:03+09:00")
        self.ts = st.ticket("01")
        self.ts.status = state.MERGED
        self.save = mock.Mock()
        self.r = SimpleNamespace(name="demo", order=["01"], iwt=self.repo, rundir=self.rundir, st=st, save=self.save)

    def write(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            written = findings.write(self.r)
        self.warnings = out.getvalue()
        return written

    def reload(self):
        """재개: 번호가 state.json을 거쳐도 남는다."""
        state.save(self.rundir, self.r.st)
        self.r.st = state.load(self.rundir, "demo")
        self.ts = self.r.st.tickets["01"]

    def idea(self, tail):
        return self.repo / IDEA.format(tail)

    def names(self):
        return sorted(p.stem for p in (self.repo / ".goldstack/ideas").glob("*.md"))


class WriteTest(Unit):
    def test_file_follows_spec_format_and_is_staged(self):
        self.ts.review = {"findings": [finding("문자 \"따옴표\": 지적", evidence="근거 내용")]}
        self.assertEqual(self.write(), [IDEA.format("01-1")])
        self.assertEqual(self.idea("01-1").read_text(encoding="utf-8"), (
            '---\ndate: "2026-11-05"\nseverity: "high"\nsource: "demo 리뷰 01"\nstatus: "open"\nfeature: ""\n---\n'
            '문자 "따옴표": 지적\n\n위치: a.py:1\n근거: 근거 내용\n판단: 고칠 만큼은 아니다\n'
            f'보고서: {REPORT}\n'))
        idea = backlog.read_idea(self.idea("01-1"))
        self.assertEqual((idea.slug, idea.severity, idea.status, idea.source, idea.summary),
                         ("demo-01-1", "high", "open", "demo 리뷰 01", '문자 "따옴표": 지적'))
        self.assertIn(f"A  {IDEA.format('01-1')}", sh(self.repo, "git", "status", "--porcelain"))
        self.assertEqual(self.warnings, "")
        self.save.assert_called_once()  # 파일 전에 번호를 저장한다

    def test_only_report_only_high_and_medium(self):
        fix = {"action": review.FIX}
        self.ts.review = {"findings": [
            finding("보고만 high"),
            finding("보고만 medium", "medium"),
            finding("low는 보고서에만", "low"),
            finding("수정됨", **fix, rereview=review.RESOLVED),
            finding("미해결", **fix, rereview=review.UNRESOLVED),
            finding("수정 못 함", **fix, fix_reason="한도"),
            finding("확인 못 함", **fix, rereview=review.UNCHECKED),
            finding("2차 재리뷰의 새 지적", **fix, found_round=2),
        ]}
        self.write()
        self.assertEqual({backlog.read_idea(p).summary for p in (self.repo / ".goldstack/ideas").glob("*.md")},
                         {"보고만 high", "보고만 medium", "2차 재리뷰의 새 지적"})

    def test_number_is_ordinal_of_ticket_findings_across_reviewers(self):
        self.ts.review = {"findings": [finding("고친 지적", action=review.FIX, rereview=review.RESOLVED),
                                       finding("첫 리뷰어", number=2)]}
        self.ts.second_review = {"findings": [finding("둘째 리뷰어", location="b.py:1", number=1)]}  # id는 첫 기록과 겹친다
        self.write()
        self.assertEqual(self.names(), ["demo-01-2", "demo-01-3"])
        self.assertEqual(backlog.read_idea(self.idea("01-3")).summary, "둘째 리뷰어")

    def test_number_stays_when_earlier_record_grows(self):
        self.ts.review = {"findings": [finding("첫 지적")]}
        self.ts.second_review = {"findings": [finding("둘째 리뷰어 지적", location="b.py:1")]}
        self.write()
        self.reload()
        self.ts.review["findings"].append(finding("재리뷰가 더한 지적", location="c.py:1", number=2, found_round=2))
        self.assertEqual(self.write(), [IDEA.format("01-3")])
        self.assertEqual(backlog.read_idea(self.idea("01-2")).summary, "둘째 리뷰어 지적")
        self.assertEqual(backlog.read_idea(self.idea("01-3")).summary, "재리뷰가 더한 지적")

    def test_rewrite_keeps_taken_dropped_and_human_edits(self):
        self.ts.review = {"findings": [finding("지적 하나"), finding("지적 둘", location="b.py:1", number=2)]}
        self.write()
        self.idea("01-1").write_text(HUMAN, encoding="utf-8")  # 첫 줄까지 고쳐도 번호로 같은 지적을 안다
        dropped = self.idea("01-2").read_text(encoding="utf-8").replace('"open"', '"dropped"') + "버린 이유: 중복\n"
        self.idea("01-2").write_text(dropped, encoding="utf-8")
        self.reload()
        self.assertEqual(self.write(), [])
        self.assertEqual(self.names(), ["demo-01-1", "demo-01-2"])
        self.assertEqual(self.idea("01-1").read_text(encoding="utf-8"), HUMAN)
        self.assertEqual(self.idea("01-2").read_text(encoding="utf-8"), dropped)

    def test_missing_file_is_written_again_under_the_same_number(self):
        self.ts.review = {"findings": [finding()]}
        self.write()
        sh(self.repo, "git", "reset", "-q", "--hard")  # 커밋 전에 끊긴 재개: integration은 reset된다
        self.assertFalse(self.idea("01-1").exists())
        self.reload()
        self.assertEqual(self.write(), [IDEA.format("01-1")])

    def test_retry_with_new_record_keeps_old_file(self):
        self.ts.review = {"findings": [finding("앞 시도의 지적")]}
        self.write()
        self.ts.review = {"findings": [finding("새 시도의 지적")]}  # go._start는 재시도에서 기록을 비운다
        self.assertEqual(self.write(), [IDEA.format("01-2"), IDEA.format("01-1")])  # 새 파일, 닫은 옛 파일
        self.assertEqual(backlog.read_idea(self.idea("01-1")).summary, "앞 시도의 지적")
        self.assertEqual(backlog.read_idea(self.idea("01-1")).status, "dropped")
        self.assertEqual(backlog.read_idea(self.idea("01-2")).status, "open")

    def test_retry_with_same_finding_uses_its_file(self):
        self.ts.review = {"findings": [finding("같은 지적")]}
        self.write()
        self.ts.review = {"findings": [finding("같은 지적", evidence="다시 쓴 근거")]}
        self.assertEqual(self.write(), [])
        self.assertEqual(self.ts.review["findings"][0][findings.NUMBER], 1)
        self.assertEqual(self.names(), ["demo-01-1"])

    def test_two_reviewers_with_same_finding_get_one_file(self):
        self.ts.review = {"findings": [finding("같은 지적")]}
        self.ts.second_review = {"findings": [finding("같은 지적")]}
        self.write()
        self.assertEqual(self.names(), ["demo-01-1"])

    def test_slug_follows_backlog_rule(self):
        self.r.name = 'My_Feature "x"'
        self.r.order = ["A 1"]
        self.r.st.tickets["A 1"] = self.ts
        self.ts.review = {"findings": [finding()]}
        [rel] = self.write()
        self.assertRegex(Path(rel).stem, r"^[a-z0-9-]+$")
        idea = backlog.read_idea(self.repo / rel)
        self.assertEqual(idea.source, 'My_Feature "x" 리뷰 A 1')

    def test_tickets_with_same_slug_get_a_file_each(self):
        self.r.order = ["A_1", "A-1"]
        self.r.st.ticket("A_1").review = {"findings": [finding("밑줄 티켓의 지적")]}
        self.r.st.ticket("A-1").review = {"findings": [finding("줄표 티켓의 지적", location="b.py:1")]}
        rels = [IDEA.format("a-1-1"), IDEA.format("a-1-2")]
        self.assertEqual(self.write(), rels)
        self.assertEqual(self.warnings, "")
        self.assertEqual(findings.paths(self.r), set(rels))
        for tail, tid, claim in (("a-1-1", "A_1", "밑줄 티켓의 지적"), ("a-1-2", "A-1", "줄표 티켓의 지적")):
            idea = backlog.read_idea(self.idea(tail))
            self.assertEqual((idea.source, idea.summary), (f"demo 리뷰 {tid}", claim))
        self.reload()  # 재개: 번호가 그대로라 더 생기지 않는다
        self.assertEqual(self.write(), [])
        self.assertEqual(self.names(), ["demo-a-1-1", "demo-a-1-2"])

    def test_same_slug_ticket_out_of_scope_keeps_its_number(self):
        self.r.order = ["A-1"]
        self.r.st.ticket("A_1").review = {"findings": [{**finding("범위 밖 티켓의 지적"), findings.NUMBER: 1}]}
        self.r.st.ticket("A-1").review = {"findings": [finding("줄표 티켓의 지적", location="b.py:1")]}
        self.assertEqual(self.write(), [IDEA.format("a-1-2")])  # 1번 파일은 아직 없어도 A_1의 번호다

    def test_longer_ticket_id_is_not_mistaken_for_a_number(self):
        (self.repo / ".goldstack/ideas").mkdir(parents=True)
        self.idea("01-2-1").write_text(HUMAN, encoding="utf-8")  # 티켓 01-2의 1번
        self.ts.review = {"findings": [finding(), finding("둘", location="b.py:1", number=2)]}
        self.assertEqual(self.write(), [IDEA.format("01-1"), IDEA.format("01-2")])

    def test_multiline_text_is_one_line_and_evidence_is_limited(self):
        self.ts.review = {"findings": [finding("첫 줄\n둘째 줄", evidence="ㄱ" * (findings.EVIDENCE_LIMIT + 50),
                                               why="여러\n줄", location=" a.py\n:1 ")]}
        self.write()
        lines = self.idea("01-1").read_text(encoding="utf-8").splitlines()
        self.assertEqual(backlog.read_idea(self.idea("01-1")).summary, "첫 줄 둘째 줄")
        self.assertIn("위치: a.py :1", lines)
        self.assertIn("판단: 여러 줄", lines)
        evidence = next(line for line in lines if line.startswith("근거: "))
        self.assertLess(len(evidence), findings.EVIDENCE_LIMIT + 40)
        self.assertIn("ㄱ" * findings.EVIDENCE_LIMIT, evidence)
        self.assertNotIn("ㄱ" * (findings.EVIDENCE_LIMIT + 1), evidence)


class RetryTest(Unit):
    """spec 2-6: 재시도가 병합되면 옛 시도의 open 파일을 dropped로 닫는다."""

    def retry(self, old="옛 시도", new="새 시도"):
        self.ts.review = {"findings": [finding(old)]}
        self.write()
        self.ts.review = {"findings": [finding(new, location="b.py:9")]}  # go._start는 재시도에서 기록을 비운다

    def raw(self, tail):
        return self.idea(tail).read_bytes()

    def test_open_file_of_dropped_attempt_is_closed_with_a_note(self):
        self.retry()
        before = self.raw("01-1")
        self.assertEqual(self.write(), [IDEA.format("01-2"), IDEA.format("01-1")])
        text = self.raw("01-1").decode()
        self.assertEqual(text, before.decode().replace('status: "open"', 'status: "dropped"') + findings.REPLACED_NOTE + "\n")
        self.assertEqual(backlog.read_idea(self.idea("01-2")).status, "open")
        self.assertIn(IDEA.format("01-1"), sh(self.repo, "git", "diff", "--cached", "--name-only"))

    def test_rerun_gives_the_same_result(self):
        self.retry()
        self.write()
        after = {n: self.raw(n) for n in ("01-1", "01-2")}
        self.reload()
        self.assertEqual(self.write(), [])
        self.assertEqual({n: self.raw(n) for n in ("01-1", "01-2")}, after)

    def test_taken_dropped_and_numbered_files_stay_byte_for_byte(self):
        self.ts.review = {"findings": [finding("하나"), finding("둘", location="b.py:1", number=2),
                                       finding("셋", location="c.py:1", number=3)]}
        self.write()
        self.idea("01-1").write_bytes(HUMAN.encode())  # taken
        self.idea("01-2").write_bytes(HUMAN.replace("taken", "dropped").encode())
        self.ts.review = {"findings": [finding("셋", location="c.py:1", number=3)]}  # 3번은 지금 state에 있다
        self.ts.review["findings"][0][findings.NUMBER] = 3
        kept = {n: self.raw(n) for n in ("01-1", "01-2", "01-3")}
        self.assertEqual(self.write(), [])
        self.assertEqual({n: self.raw(n) for n in ("01-1", "01-2", "01-3")}, kept)

    def test_unmerged_ticket_and_other_ticket_files_stay(self):
        self.r.order = ["01", "02"]
        other = self.r.st.ticket("02")
        other.status = state.FAILED
        other.review = {"findings": [finding("실패한 티켓")]}
        self.write()
        self.r.st.ticket("03").status = state.MERGED  # 범위 밖(r.order에 없음)
        self.r.st.tickets["03"].review = {"findings": [finding("범위 밖")]}
        self.r.order = ["01", "02", "03"]
        self.write()
        self.r.order = ["01", "02"]
        other.review = {}
        self.r.st.tickets["03"].review = {}
        self.ts.review = {"findings": [finding("01의 지적")]}
        self.write()
        kept = {n: self.raw(n) for n in ("02-1", "03-1")}
        self.assertEqual(self.write(), [])
        self.assertEqual({n: self.raw(n) for n in ("02-1", "03-1")}, kept)
        self.assertEqual(backlog.read_idea(self.idea("02-1")).status, "open")

    def test_similar_ticket_names_do_not_mix(self):
        self.r.order = ["A_1", "A-1"]
        self.r.st.tickets.pop("01")
        under, dash = self.r.st.ticket("A_1"), self.r.st.ticket("A-1")
        under.status = dash.status = state.MERGED
        under.review = {"findings": [finding("밑줄 옛 시도")]}
        dash.review = {"findings": [finding("줄표 옛 시도", location="b.py:1")]}
        self.write()
        self.assertEqual(self.names(), ["demo-a-1-1", "demo-a-1-2"])
        under.review = {"findings": [finding("밑줄 새 시도", location="c.py:1")]}  # 밑줄만 재시도
        dash.status = state.FAILED
        self.write()
        statuses = {n: backlog.read_idea(self.idea(n)).status for n in ("a-1-1", "a-1-2", "a-1-3")}
        owners = {n: backlog.read_idea(self.idea(n)).source for n in statuses}
        dash_file = next(n for n in owners if owners[n] == "demo 리뷰 A-1")
        self.assertEqual(statuses[dash_file], "open")  # 줄표 티켓은 병합되지 않았으니 그대로다
        under_old = next(n for n in owners if owners[n] == "demo 리뷰 A_1" and "밑줄 옛" in backlog.read_idea(self.idea(n)).summary)
        self.assertEqual(statuses[under_old], "dropped")

    def test_other_feature_with_same_prefix_is_not_closed(self):
        """feature demo-a의 티켓 1과 feature demo의 티켓 A_1은 파일 prefix(demo-a-1-)가 같다. source로 가른다."""
        self.r.order = ["A_1"]
        self.r.st.tickets.pop("01")
        self.r.st.ticket("A_1").status = state.MERGED
        foreign = self.idea("a-1-1")
        foreign.parent.mkdir(parents=True, exist_ok=True)
        foreign.write_text('---\ndate: "2026-11-05"\nseverity: "high"\nsource: "demo-a 리뷰 1"\nstatus: "open"\n'
                           'feature: ""\n---\n다른 feature의 지적\n', encoding="utf-8")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "다른 feature의 파일")
        before = foreign.read_bytes()
        self.assertEqual(self.write(), [])
        self.assertEqual(foreign.read_bytes(), before)

    def test_close_failure_only_warns_and_restores(self):
        self.retry()
        before = self.raw("01-1")
        with mock.patch("gs.findings.git.run", side_effect=RuntimeError("add 실패")):
            self.assertEqual(self.write(), [])
        self.assertIn("■ 경고: 재시도로 대체된 지적 파일", self.warnings)
        self.assertEqual(self.raw("01-1"), before)

    def test_broken_file_only_warns(self):
        self.retry()
        self.idea("01-1").write_bytes(b"\xff\xfe not utf8")
        self.assertEqual(self.write(), [IDEA.format("01-2")])
        self.assertIn("■ 경고: 재시도로 대체된 지적 파일", self.warnings)

    def test_paths_include_closed_files_so_verify_can_be_skipped(self):
        self.retry()
        self.write()
        self.assertIn(IDEA.format("01-1"), findings.paths(self.r))


class WriteFailureTest(Unit):
    def commit_all(self, message):
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", message)

    def test_ideas_path_is_a_file_only_warns(self):
        (self.repo / ".goldstack").mkdir()
        (self.repo / ".goldstack/ideas").write_text("파일\n")
        self.commit_all("막힌 경로")
        self.ts.review = {"findings": [finding()]}
        self.assertEqual(self.write(), [])
        self.assertIn("■ 경고: 보고만 지적 파일", self.warnings)
        self.assertTrue(setup.is_clean(self.repo))

    def test_ignored_ideas_only_warn_and_leave_no_file(self):
        (self.repo / ".gitignore").write_text(".goldstack/ideas/\n")
        self.commit_all("무시")
        self.ts.review = {"findings": [finding()]}
        self.assertEqual(self.write(), [])
        self.assertIn("■ 경고: 보고만 지적 파일", self.warnings)
        self.assertFalse(self.idea("01-1").exists())
        self.assertTrue(setup.is_clean(self.repo))

    def test_one_bad_finding_does_not_stop_the_others(self):
        self.ts.review = {"findings": [finding("인코딩 못 함 \ud800"), finding("정상", location="b.py:1", number=2)]}
        self.assertEqual(self.write(), [IDEA.format("01-2")])
        self.assertIn(IDEA.format("01-1"), self.warnings)
        self.assertFalse(self.idea("01-1").exists())

    def test_malformed_record_only_warns(self):
        self.ts.review = {"findings": [None]}
        self.assertEqual(self.write(), [])
        self.assertIn("■ 경고: 보고만 지적 파일", self.warnings)

    def test_copy_to_base_failure_only_warns(self):
        self.ts.review = {"findings": [finding()]}
        self.write()
        base = self.root / "base"
        base.mkdir()
        sh(base, "git", "init", "-q", "-b", "main")
        (base / ".goldstack").mkdir()
        (base / ".goldstack/ideas").write_text("파일\n")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(findings.copy_to_base(self.r, base), [])
        self.assertIn("■ 경고: 보고만 지적 파일", out.getvalue())


class CopyToBaseTest(Unit):
    def base(self):
        wt = self.root / "base"
        wt.mkdir()
        sh(wt, "git", "init", "-q", "-b", "main")
        return wt

    def test_copies_only_missing_and_keeps_what_base_has(self):
        self.ts.review = {"findings": [finding("하나"), finding("둘", location="b.py:1", number=2),
                                       finding("지운 것", location="c.py:1", number=3)]}
        self.write()
        self.idea("01-3").unlink()  # integration에 없으면 옮길 것이 없다
        wt = self.base()
        (wt / ".goldstack/ideas").mkdir(parents=True)
        (wt / IDEA.format("01-1")).write_text(HUMAN, encoding="utf-8")
        self.assertEqual(findings.copy_to_base(self.r, wt), [IDEA.format("01-2")])
        self.assertEqual((wt / IDEA.format("01-1")).read_text(encoding="utf-8"), HUMAN)
        self.assertEqual((wt / IDEA.format("01-2")).read_bytes(), self.idea("01-2").read_bytes())
        self.assertFalse((wt / IDEA.format("01-3")).exists())


class CopyToBaseRetryTest(Unit):
    """copy_to_base와 함께 돌면 base 쪽도 같은 상태가 된다."""

    base = CopyToBaseTest.base

    def test_base_open_file_of_dropped_attempt_is_closed_like_integration(self):
        self.ts.review = {"findings": [finding("옛 시도")]}
        self.write()
        wt = self.base()
        (wt / ".goldstack/ideas").mkdir(parents=True)
        (wt / IDEA.format("01-1")).write_bytes(self.idea("01-1").read_bytes())  # feature PR로 이미 base에 있다
        self.ts.review = {"findings": [finding("새 시도", location="b.py:9")]}
        self.write()
        copied = findings.copy_to_base(self.r, wt)
        self.assertEqual(copied, [IDEA.format("01-2"), IDEA.format("01-1")])
        self.assertEqual((wt / IDEA.format("01-1")).read_bytes(), self.idea("01-1").read_bytes())
        self.assertEqual((wt / IDEA.format("01-2")).read_bytes(), self.idea("01-2").read_bytes())
        self.assertEqual(findings.copy_to_base(self.r, wt), [])  # 두 번째는 달라질 것이 없다
        self.assertEqual((wt / IDEA.format("01-1")).read_bytes(), self.idea("01-1").read_bytes())

    def test_base_taken_file_and_missing_file_stay(self):
        self.ts.review = {"findings": [finding("옛 시도")]}
        self.write()
        self.ts.review = {"findings": [finding("새 시도", location="b.py:9")]}
        self.write()
        wt = self.base()
        (wt / ".goldstack/ideas").mkdir(parents=True)
        (wt / IDEA.format("01-1")).write_text(HUMAN, encoding="utf-8")
        copied = findings.copy_to_base(self.r, wt)
        self.assertEqual(copied, [IDEA.format("01-2")])  # 닫힌 옛 파일이 base에 없으면 옮기지 않는다
        self.assertEqual((wt / IDEA.format("01-1")).read_text(encoding="utf-8"), HUMAN)


class OldStateTest(Unit):
    def test_old_state_json_without_new_fields(self):
        (self.rundir / "state.json").write_text(json.dumps({
            "feature": "demo", "finish": {"phase": "verified"},
            "tickets": {"01": {"status": "merged", "unknown_old_key": 1,
                               "review": {"reviewer": "codex", "findings": [{
                                   "id": 1, "severity": "medium", "location": "", "claim": "옛 지적", "evidence": ""}]}},
                        "02": {"status": "failed", "review": {"reviewer": "codex", "note": "리뷰 실패"}}},
        }), encoding="utf-8")
        self.r.st = state.load(self.rundir, "demo")
        self.r.order = ["01", "02"]
        self.assertEqual(findings.paths(self.r), set())
        self.assertEqual(self.write(), [IDEA.format("01-1")])
        text = self.idea("01-1").read_text(encoding="utf-8")
        self.assertIn("옛 지적\n\n위치: 없음\n근거: 없음\n판단: 기록 없음\n", text)
        self.assertRegex(text, r'date: "\d{4}-\d{2}-\d{2}"')  # started_at이 없어도 형식에 맞는다
        backlog.read_idea(self.idea("01-1"))
        self.assertEqual(findings.paths(self.r), {IDEA.format("01-1")})
        self.reload()
        self.assertEqual(self.write(), [])


class DeferTest(Unit):
    """goldstack-v27 01: defer(재현된 미수리) 지적은 원래 심각도와 상관없이 high 파일이고, 본문에 원래 심각도를 적는다."""

    def test_defer_of_any_severity_is_a_high_idea_with_original_severity(self):
        self.ts.review = {"findings": [
            finding("high defer", action=review.DEFER),
            finding("medium defer", "medium", "b.py:1", 2, action=review.DEFER),
            finding("low defer", "low", "c.py:1", 3, action=review.DEFER, why="c.py는 고칠 수 있는 파일 밖이다"),
            finding("low 보고만", "low", "d.py:1", 4),
        ]}
        self.assertEqual(self.write(), [IDEA.format(f"01-{n}") for n in (1, 2, 3)])
        self.assertEqual(self.idea("01-3").read_text(encoding="utf-8"), (
            '---\ndate: "2026-11-05"\nseverity: "high"\nsource: "demo 리뷰 01"\nstatus: "open"\nfeature: ""\n---\n'
            'low defer\n\n위치: c.py:1\n근거: 근거\n판단: c.py는 고칠 수 있는 파일 밖이다\n'
            '재현된 미수리 결함(defer): 고칠 수 있는 파일 밖을 고쳐야 해 고치지 않았다. 원래 심각도: low\n'
            f'보고서: {REPORT}\n'))
        for n, original in ((1, "high"), (2, "medium"), (3, "low")):
            idea = backlog.read_idea(self.idea(f"01-{n}"))
            self.assertEqual((idea.severity, idea.status), ("high", "open"))
            self.assertIn(f"원래 심각도: {original}\n", self.idea(f"01-{n}").read_text(encoding="utf-8"))

    def test_same_finding_as_report_then_defer_is_one_high_file(self):
        """두 리뷰어의 같은 지적(첫 줄·위치)이 한 파일을 나눠 쓴다. 앞 기록이 medium 보고만이어도 defer의 high 파일이 남는다."""
        self.ts.review = {"findings": [finding("같은 지적", "medium")]}
        self.ts.second_review = {"findings": [finding("같은 지적", "medium", action=review.DEFER)]}
        self.assertEqual(self.write(), [IDEA.format("01-1")])
        self.assertEqual(self.names(), ["demo-01-1"])
        idea = backlog.read_idea(self.idea("01-1"))
        self.assertEqual((idea.severity, idea.status), ("high", "open"))
        self.assertIn("원래 심각도: medium\n", self.idea("01-1").read_text(encoding="utf-8"))

    def test_report_only_file_has_no_defer_line(self):
        self.ts.review = {"findings": [finding("보고만 medium", "medium")]}
        self.write()
        text = self.idea("01-1").read_text(encoding="utf-8")
        self.assertIn('severity: "medium"', text)
        self.assertNotIn("재현된 미수리", text)


class VerifyFinalTest(Unit):
    def setUp(self):
        super().setUp()
        (self.repo / REPORT).parent.mkdir(parents=True)
        (self.repo / REPORT).write_text("보고서\n")
        self.ts.review = {"findings": [finding()]}
        self.head = sh(self.repo, "git", "rev-parse", "HEAD")

    def commit(self, *rels):
        sh(self.repo, "git", "add", "--", *rels)
        sh(self.repo, "git", "commit", "-qm", "report")

    def verify_final(self):
        with mock.patch("gs.finish._verify", return_value=True) as verify, contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(finish._verify_final(self.r, self.head))
        return verify.called

    def test_report_and_idea_files_skip_verify(self):
        self.write()
        self.commit(REPORT, IDEA.format("01-1"))
        self.assertFalse(self.verify_final())
        self.assertIn("보고서만 바뀜, 건너뜀", (self.rundir / "finish/integration-final-verify.log").read_text())

    def test_other_idea_file_runs_verify(self):
        (self.repo / ".goldstack/ideas").mkdir(parents=True)
        (self.repo / ".goldstack/ideas/other.md").write_text(HUMAN, encoding="utf-8")
        self.commit(REPORT, ".goldstack/ideas/other.md")
        self.assertTrue(self.verify_final())

    def test_code_change_with_idea_file_runs_verify(self):
        self.write()
        (self.repo / "code.py").write_text("x = 1\n")
        self.commit(REPORT, IDEA.format("01-1"), "code.py")
        self.assertTrue(self.verify_final())


class Scenario:
    """직접 push·보호된 base가 함께 쓰는 확인."""

    def base_ideas(self):
        out = sh(self.remote, "git", "ls-tree", "--name-only", "main", ".goldstack/ideas/")
        return sorted(Path(line).stem for line in out.splitlines())

    def base_idea(self, tail):
        return sh(self.remote, "git", "show", f"main:{IDEA.format(tail)}")

    def changed(self, rev):
        return sh(self.remote, "git", "diff-tree", "--no-commit-id", "--name-only", "-r", rev).splitlines()

    def assert_two_ideas_on_base(self):
        self.assertEqual(self.base_ideas(), ["demo-01-1", "demo-01-2"])
        self.assertIn("근거 하나", self.base_idea("01-1"))
        self.assertIn("중간 지적", self.base_idea("01-2"))

    def assert_backlog_lists_base_ideas(self):
        clone = self.bin / "backlog-clone"
        sh(self.bin, "git", "clone", "-q", str(self.remote), str(clone))
        code, out, err = run_backlog(clone)
        self.assertEqual((code, err), (0, ""), out)
        self.assertNotIn("경고", out)
        self.assertIn("아이디어 (열림 2)", out)
        day = state.load(self.rundir, "demo").started_at[:10]
        self.assertIn(f"high    {day}  demo-01-1  높은 지적   (demo 리뷰 01)", out)
        self.assertIn(f"medium  {day}  demo-01-2  중간 지적   (demo 리뷰 01)", out)
        self.assertNotIn("낮은 지적", out)


class DirectPushTest(Scenario, support.GoTest):
    def test_files_land_with_first_report_commit_and_backlog_lists_them(self):
        with self.review_with(FINDINGS):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assert_two_ideas_on_base()
        self.assertIn("낮은 지적", self.final_report())
        self.assertEqual(sorted(self.changed(f["merge_head"])), sorted([IDEA.format("01-1"), IDEA.format("01-2"), REPORT]))
        self.assertIn("integration-final: 보고서만 바뀜, 건너뜀", self.final_report())
        self.assert_backlog_lists_base_ideas()
        self.assertNotIn("보고만 지적 파일", out)

    def test_reverted_report_commit_brings_files_back(self):
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        with self.review_with(FINDINGS):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual(self.under_report(), f["revert_sha"])  # revert가 지운 파일을 보고서 커밋이 되살린다
        self.assertEqual(sorted(self.changed("main")), sorted([IDEA.format("01-1"), IDEA.format("01-2"), REPORT]))
        self.assert_two_ideas_on_base()
        self.assertNotIn("file_01", self.remote_files())

        self.add_ticket("11")  # 다음 마무리: 양쪽의 같은 파일이 충돌하지 않고 번호도 그대로다
        with self.review_with(FINDINGS):
            code, out, err = self.go("--only", "01,11")
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "reverted", out + err)
        self.assertNotIn("충돌", out + err)
        self.assertEqual(self.base_ideas(), ["demo-01-1", "demo-01-2", "demo-11-1", "demo-11-2"])

    def stop_at_merged(self):
        with self.review_with(FINDINGS), mock.patch("gs.finish._postmerge", side_effect=RuntimeError("interrupted")):
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                self.go("--only", "01")
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "merged")

    def strip_state(self):
        """파일을 쓰기 전의 gs가 남긴 state: 지적에 번호도 판단도 없다."""
        path = self.rundir / "state.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        rec = raw["tickets"]["01"]["review"]
        rec["findings"] = [{k: f[k] for k in ("id", "severity", "location", "claim", "evidence", "action")}
                           for f in rec["findings"]]
        path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    def test_old_gs_pr_and_old_state_get_files_from_report_commit(self):
        with mock.patch("gs.findings.write", return_value=[]):
            self.stop_at_merged()
        self.assertEqual(self.base_ideas(), [])
        self.strip_state()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertEqual(self.under_report(), f["merge_sha"])
        self.assertEqual(sorted(self.changed("main")), sorted([IDEA.format("01-1"), IDEA.format("01-2"), REPORT]))
        self.assert_two_ideas_on_base()
        self.assertIn("판단: 기록 없음", self.base_idea("01-1"))
        self.assertEqual(sh(self.remote, "git", "show", f"main:{REPORT}"), self.final_report())
        self.assertEqual(self.integration("show", f"gs/demo/integration:{IDEA.format('01-1')}"), self.base_idea("01-1"))

    def human_edits_idea(self):
        (self.bin / "human.md").write_text(HUMAN, encoding="utf-8")
        self.someone(f"cp {self.bin / 'human.md'} {IDEA.format('01-1')}", f"git add {IDEA.format('01-1')}",
                     "git commit -qm taken")

    def test_resume_keeps_human_edit_and_does_not_duplicate(self):
        self.stop_at_merged()
        self.assert_two_ideas_on_base()
        self.human_edits_idea()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertEqual(self.changed("main"), [REPORT])  # 이미 있는 파일은 보고서 커밋에 들지 않는다
        self.assertEqual(self.base_ideas(), ["demo-01-1", "demo-01-2"])
        self.assertEqual(self.base_idea("01-1"), HUMAN.strip())

    def test_next_finish_keeps_human_edit_and_does_not_duplicate(self):
        with self.review_with(FINDINGS):
            self.assertEqual(self.go("--only", "01")[0], 0)
        other = self.base_idea("01-2")
        self.human_edits_idea()
        self.add_ticket("11")
        with self.review_with(FINDINGS):
            code, out, err = self.go("--only", "01,11")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.calls(), ["01", "11"])
        self.assertEqual(self.base_ideas(), ["demo-01-1", "demo-01-2", "demo-11-1", "demo-11-2"])
        self.assertEqual(self.base_idea("01-1"), HUMAN.strip())
        self.assertEqual(self.base_idea("01-2"), other)
        clone = self.bin / "backlog-clone"
        sh(self.bin, "git", "clone", "-q", str(self.remote), str(clone))
        code, listing, err = run_backlog(clone, "--all")
        self.assertEqual((code, err), (0, ""), listing)
        self.assertRegex(listing, r"(?m)^high +2026-01-01 +taken +demo-01-1 +사람이 고침")

    def test_write_failure_keeps_result_and_warns(self):
        (self.repo / ".goldstack/ideas").write_text("파일\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "막힌 경로")
        sh(self.repo, "git", "push", "-q", "origin", "main")
        with self.review_with(FINDINGS):
            code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(f["phase"], "verified")
        self.assertIn("■ 경고: 보고만 지적 파일", out)
        self.assertIn("integration-final: 보고서만 바뀜, 건너뜀", self.final_report())
        self.assertEqual(sh(self.remote, "git", "show", "main:.goldstack/ideas"), "파일")
        self.assertEqual(sh(self.remote, "git", "show", f"main:{REPORT}"), self.final_report())


class ProtectedBaseTest(Scenario, test_resume_report.Fixture):
    def go_with_findings(self):
        with self.G.review_with(self, FINDINGS):
            return self.go()

    def test_files_land_through_feature_pr(self):
        code, out, err = self.go_with_findings()
        self.assertEqual(code, 0, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "verified")
        self.assertEqual([(p["head"], p["state"]) for p in self.prs()],
                         [("gs/demo/integration", "MERGED"), ("gs/demo/report", "MERGED")])
        self.assert_two_ideas_on_base()
        self.assert_backlog_lists_base_ideas()
        self.assert_no_base_push()

    def reverted_through_report_pr(self, method):
        self.tearDown()
        self.setUp(method=method, break_main=True)
        code, out, err = self.go_with_findings()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "reverted")
        self.assertEqual([p["head"] for p in self.prs()],
                         ["gs/demo/integration", "gs/demo/revert", "gs/demo/report"])
        self.assertEqual(sorted(self.changed(f["base_report"])),
                         sorted([IDEA.format("01-1"), IDEA.format("01-2"), REPORT]))
        self.assert_two_ideas_on_base()
        self.assertNotIn("file_01", self.remote_files())
        self.assertEqual(self.base_report(), self.final_report())
        self.assert_no_base_push()

    def test_reverted_report_pr_brings_files_back(self):
        self.reverted_through_report_pr("merge")

    def test_reverted_report_pr_brings_files_back_squash(self):
        self.reverted_through_report_pr("squash")

    def test_old_gs_pr_gets_files_through_report_pr_after_approval(self):
        self.protect("integration", "report")
        with mock.patch("gs.findings.write", return_value=[]):
            code, out, err = self.go_with_findings()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.finish()["phase"], "merge_pending")
        self.human_merge(1)
        self.assertEqual(self.base_ideas(), [])

        code, out, err = self.go()
        self.assertEqual(code, 1, out + err)
        f = self.finish()
        self.assertEqual(f["phase"], "report_pending")
        self.assertEqual(self.base_ideas(), [])  # 승인 전이라 아직 base에 없다
        self.assertEqual(sorted(self.changed(f["report_head"])),
                         sorted([IDEA.format("01-1"), IDEA.format("01-2"), REPORT]))

        self.approve(2)
        code, out, err = self.go()
        self.assertEqual(code, 0, out + err)
        self.assertEqual(self.finish()["phase"], "verified")
        self.assert_two_ideas_on_base()
        self.assertEqual(self.base_report(), self.final_report())
        self.assert_backlog_lists_base_ideas()
        self.assert_no_base_push()


if __name__ == "__main__":
    unittest.main()
