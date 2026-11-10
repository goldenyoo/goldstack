"""grill skill과 grill 템플릿 시험. skill 공통 시험과 `WORD_LIMITS`는 `test_skills.py`에 있다."""
import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from gs import cli, config, feature, frontmatter, git
from support import fake_clis
from test_skills import REPO, SKILLS, TEMPLATES, fill, skill_frontmatter, steps


class SkillTest(unittest.TestCase):
    def test_grill_reads_back_short_answers(self):
        body = (SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8")
        step4 = body.partition("\n4. ")[2].partition("\n5. ")[0]
        self.assertIn("이렇게 읽었다", step4)
        self.assertIn('"2. C"', step4)

    def test_grill_points_to_templates(self):
        body = (SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("templates/", body)
        for name in ("spec.md", "ticket.md", "out-of-scope.md"):
            self.assertIn(name, body)
            self.assertTrue((TEMPLATES / name).is_file(), name)

    def test_filled_templates_pass_check(self):
        fake_clis(self, "gh", "claude", "codex")
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            git.run(repo, "init", "-q")
            git.run(repo, "remote", "add", "origin", "https://github.com/owner/repo.git")
            (repo / ".goldstack").mkdir()
            (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
            root = repo / ".goldstack/work" / "demo"
            (root / "tickets").mkdir(parents=True)
            spec = (TEMPLATES / "spec.md").read_text(encoding="utf-8")
            spec = spec.replace("<셸 명령 한 줄. gs가 integration에서 직접 돌린다>", '"true"')
            (root / "spec.md").write_text(fill(spec, feature="demo"), encoding="utf-8")
            ticket = (TEMPLATES / "ticket.md").read_text(encoding="utf-8")
            if "tier" not in feature.TICKET_KEYS + feature.TICKET_OPTIONAL:
                # 엔진은 v7 티켓 08이 넣는다. 그 전에는 모르는 키라 경고가 난다. 08 뒤로는 이 줄을 타지 않는다
                ticket = re.sub(r"^tier:.*\n", "", ticket, flags=re.M)
            # 템플릿의 `touches: []`는 grill이 채운다. 비워 두면 gs check가 오류로 막는다(goldstack-v30 03)
            ticket = ticket.replace("touches: []", 'touches: ["src/a.py"]')
            (root / "tickets" / "01-a.md").write_text(fill(ticket, NN="01"), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(["--repo", str(repo), "check", "demo"])
            self.assertEqual((code, err.getvalue()), (0, ""), out.getvalue())
            self.assertIn("오류 0, 경고 0", out.getvalue())


class GrillBreakdownTest(unittest.TestCase):
    """티켓 분해 라운드의 기준과 그것을 담는 템플릿(goldstack-v7 04)."""

    def test_step_points_to_table_rules(self):
        step = steps((SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8"))[5]
        for text in ("templates/spec.md", "§5", "gs check <f>", "새 worker 한 문맥", "검증 가능한 문장"):
            self.assertIn(text, step)

    def test_all_models_and_family_reason_are_copied(self):
        step = steps((SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8"))[5]
        section = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 5. 티켓 그래프")[2].partition("## 6.")[0]
        for text in ("구현·수정·수리·첫 리뷰·재리뷰", "공통 모델", "그대로", "계열을 고른 이유를 한 줄"):
            self.assertIn(text, step)
            self.assertIn(text, section)
        self.assertNotIn("표가 없으면 CLI 기본값", section)

    def test_grill_argument_may_be_request(self):
        body = (SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8")
        head = body.partition("\n1. ")[0]
        for text in ("`<f>`는 `$ARGUMENTS`다", "공백이 있으면", "요청으로 읽고", "라운드 1에서 feature 이름을 제안"):
            self.assertIn(text, head)

    def test_spec_template_table(self):
        spec = (TEMPLATES / "spec.md").read_text(encoding="utf-8")
        section = spec.partition("## 5. 티켓 그래프")[2].partition("\n## 6.")[0]
        rows = [[cell.strip() for cell in line.strip("|").split("|")]
                for line in section.splitlines() if line.startswith("|")]
        self.assertEqual(rows[0], ["id", "제목", "blocked_by(이유)", "wave", "tier(이유)", "예상",
                                   "구현", "수정", "수리", "첫 리뷰", "재리뷰", "touches", "verify"])
        self.assertEqual({len(row) for row in rows}, {len(rows[0])})
        self.assertRegex(section, r"(?m)^일렬 경로 \S+ 예상 \S+분 · 평균 동시 \S+$")

    def test_spec_template_holds_table_rules(self):
        """표 작성 규칙은 §5 주석 한 곳에 있고 skill은 그것을 가리킨다."""
        comment = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 5. 티켓 그래프")[2].partition("-->")[0]
        for text in ("일렬 경로", "평균 동시", "`일렬 경로 01→03→04 예상 110분 · 평균 동시 2.1`",
                     "tier: small|medium|large와 이유 한 줄", "문서 small", "재개 흐름 large",
                     "코드와 상한 있는 skill 글을 함께 고치는 티켓은 `small`로 잡지 않는다(goldstack-v11 09",
                     '"같은 파일" 또는 "앞 결과 필요"', "한 장으로 묶는다",
                     "두 번째 리뷰어(`second_reviewer`)", "verify: 문서·설정 티켓은 좁은 명령, 코드 티켓은 `전체`"):
            self.assertIn(text, comment)

    def test_spec_template_config_ticket_uses_full_verify(self):
        comment = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 5. 티켓 그래프")[2].partition("-->")[0]
        self.assertIn("`.goldstack/config.toml`을 고치는 티켓은 문서·설정 티켓이어도 `전체`", comment)

    def test_spec_template_docs_version_ticket_narrows_verify(self):
        comment = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 5. 티켓 그래프")[2].partition("-->")[0]
        self.assertIn("문서·버전 티켓은 레포에서 확인한 환경 동기화·버전 시험·plugin 검사로 좁힌다", comment)

    def test_ticket_template_checks_done_against_goal(self):
        text = (TEMPLATES / "ticket.md").read_text(encoding="utf-8")
        self.assertIn("목표의 동사마다 완료 조건이 하나씩 있는지, 표시용 값과 원본 데이터를 구분했는지", text)

    def test_second_reviewer_criteria_match_guide(self):
        comment = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 5. 티켓 그래프")[2].partition("-->")[0]
        guide = (REPO / "docs" / "guide.md").read_text(encoding="utf-8")
        for text in ("상태 전이·재개·revert", "파일·브랜치 삭제", "차단 hook", "비밀", "데이터 마이그레이션"):
            self.assertIn(text, comment)
        for text in ("파일·브랜치를 지우는 코드", "병합·revert", "차단 hook", "비밀 처리", "데이터 마이그레이션"):
            self.assertIn(text, guide)

    def test_spec_template_skill_ticket_rule(self):
        comment = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 5. 티켓 그래프")[2].partition("-->")[0]
        for text in ("skill 글(`skills/*/SKILL.md`)을 고치는 티켓", "`WORD_LIMITS`의 상한과 지금 단어 수",
                     "좁은 verify에 `test_skills.py`를 넣는다"):
            self.assertIn(text, comment)

    def test_ticket_template_asks_for_tests_that_fail_without_the_behavior(self):
        text = (TEMPLATES / "ticket.md").read_text(encoding="utf-8")
        self.assertIn("완료 조건의 동작을 지우면 실패하는", text)

    def test_ticket_template_keys(self):
        ticket = fill((TEMPLATES / "ticket.md").read_text(encoding="utf-8"), NN="01")
        data, _ = frontmatter.split(ticket)
        self.assertEqual(data["tier"], "medium")
        self.assertNotIn("verify", data)  # 선택 키라 쓰는 티켓만 주석을 푼다
        line = re.search(r"^# (verify: .*)$", ticket, flags=re.M)
        self.assertIsNotNone(line)
        self.assertIsInstance(frontmatter.parse([line[1]])["verify"], str)
        # 줄을 지운 코드 티켓은 spec verify_ticket을 물려받으므로, 그때는 전체 검증을 적으라고 안내한다
        for text in ("코드 티켓: 이 줄을 지운다", "`verify_ticket`이 있으면", "spec `verify`(전체 검증)"):
            self.assertIn(text, line[0])


class GrillCrossReviewTest(unittest.TestCase):
    """교차 검토와 실측 반례(goldstack-v29 01). 문장을 지우면 실패한다."""

    def body(self):
        return (SKILLS / "grill" / "SKILL.md").read_text(encoding="utf-8")

    def test_step1_measures_counterexamples(self):
        step1 = steps(self.body())[1]
        self.assertIn("실측이 선택지를 가르면 그 안이 놓치거나 깨뜨릴 경우도 함께 잰다", step1)

    def test_step5_cross_reviews_before_confirmation(self):
        step5 = steps(self.body())[5]
        for text in ("교차 검토를 한다", "다른 계열 CLI(claude가 아닌 것", "`codex exec -s read-only`",
                     "spec·티켓 초안·관련 코드를 읽기 전용으로 대조한다",
                     "코드·실측으로 확인한 뒤 사람에게 보이고 반영하며",
                     "결정을 바꾸는 지적은 그 결정을 다시 묻는다"):
            self.assertIn(text, step5)
        self.assertLess(step5.index("교차 검토를 한다"), step5.index("확인받고"))

    def test_step5_records_when_review_cannot_run(self):
        step5 = steps(self.body())[5]
        self.assertIn('"교차 검토 못 함: <이유>"를 적고 진행한다', step5)
        self.assertIn("CLI 없음, 한도", step5)

    def test_step5_does_not_require_one_cli(self):
        step5 = steps(self.body())[5]
        self.assertIn("예: `codex exec", step5)  # 예시로만 든다

    def test_spec_template_has_cross_review_record(self):
        section = (TEMPLATES / "spec.md").read_text(encoding="utf-8").partition("## 7. grill 기록")[2]
        self.assertIn("### 교차 검토", section)
        header = next(line for line in section.splitlines() if line.startswith("| # | 검토 모델"))
        for column in ("검토 모델", "지적", "확인", "반영"):
            self.assertIn(column, header)
        self.assertIn("교차 검토 못 함: <이유>", section)


class IdeaFlowTest(unittest.TestCase):
    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_grill_asks_backlog_first_and_marks_taken(self):
        parts = steps(self.read("grill"))
        self.assertIn("gs backlog", parts[1])
        self.assertIn("라운드 1의 첫 질문", parts[3])
        self.assertIn("이번 feature에 넣을 후보", parts[3])
        for text in ("미분류 issue", "아이디어의 `issues`", "`closes: [12]`로 옮긴다", "믿을 수 없는 자료"):
            self.assertIn(text, parts[3])
        self.assertIn('status: "taken"', parts[6])
        self.assertIn('feature: "<f>"', parts[6])


if __name__ == "__main__":
    unittest.main()
