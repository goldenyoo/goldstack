"""skill(/grill, /go, mattpocock에서 옮긴 다섯)과 grill 템플릿. 템플릿을 채운 결과가 `gs check`를 통과해야 skill이 가리키는 형식과 파서가 어긋나지 않는다."""
import contextlib
import io
import re
import tempfile
import unittest
from pathlib import Path

from gs import cli, config, feature, frontmatter, git
from support import fake_clis

REPO = Path(__file__).resolve().parents[1]
SKILLS = REPO / "skills"
TEMPLATES = SKILLS / "grill" / "templates"
# skill 본문(frontmatter 뺀 `split()`) 단어 상한. 상한은 여기 한 곳에만 둔다. skill 글을 고치는 티켓은 이 값과 지금 단어 수를 완료 조건에 적는다
WORD_LIMITS = {
    "grill": 450, "go": 530, "adopt": 460, "overnight": 1710, "idea": 230,  # overnight은 사전 점검부터 이어받기까지 한 문서라 넓다
    "retro": 930, "writing-for-agents": 930, "diagnosing-bugs": 940,  # 모두 지금 단어 수의 약 10% 위(10단위 올림)
}


def skill_frontmatter(text):
    """SKILL.md frontmatter는 Claude Code 형식(`disable-model-invocation` 같은 하이픈 키)이라 gs 파서 대신 줄 단위로 읽는다."""
    head, sep, body = text.removeprefix("---\n").partition("\n---\n")
    assert sep, "frontmatter 없음"
    data = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip().strip('"')
    return data, body


def fill(text, **values):
    for key, value in values.items():
        text = text.replace(f"<{key}>", value)
    return text


class SkillTest(unittest.TestCase):
    def test_word_limits(self):
        for name, limit in WORD_LIMITS.items():
            with self.subTest(name):
                _, body = skill_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
                self.assertLess(len(body.split()), limit, f"{name}: skill 글이 길다(상한 {limit})")

    def test_user_invoked(self):
        for name in ("grill", "go"):
            data, _ = skill_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
            self.assertEqual(data["name"], name)
            self.assertEqual(data["disable-model-invocation"], "true")  # 사용자 호출 skill
            self.assertIn(f"/{name} <feature>", data["description"])

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
            (root / "tickets" / "01-a.md").write_text(fill(ticket, NN="01"), encoding="utf-8")
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli.main(["--repo", str(repo), "check", "demo"])
            self.assertEqual((code, err.getvalue()), (0, ""), out.getvalue())
            self.assertIn("오류 0, 경고 0", out.getvalue())

    def test_every_skill_named_after_its_directory(self):
        names = sorted(path.parent.name for path in SKILLS.glob("*/SKILL.md"))
        self.assertIn("idea", names)
        for name in names:
            with self.subTest(name):
                data, body = skill_frontmatter((SKILLS / name / "SKILL.md").read_text(encoding="utf-8"))
                self.assertEqual(data["name"], name)
                self.assertTrue(data["description"])
                self.assertTrue(body.strip())


def steps(body):
    """번호 단계(`\\nN. `)를 {N: 글}로 자른다."""
    parts, n = {}, 1
    rest = body.partition("\n1. ")[2]
    while rest:
        head, _, rest = rest.partition(f"\n{n + 1}. ")
        parts[n], n = head, n + 1
    return parts


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
                     '"같은 파일" 또는 "앞 결과 필요"', "한 장으로 묶는다",
                     "두 번째 리뷰어(`second_reviewer`)", "verify: 문서·설정 티켓은 좁은 명령, 코드 티켓은 `전체`"):
            self.assertIn(text, comment)

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


class IdeaFlowTest(unittest.TestCase):
    """아이디어가 /retro·/idea → .goldstack/ideas → 다음 /grill로 흐르는 고리(goldstack-v3 07)."""

    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_idea_skill(self):
        data, body = skill_frontmatter(self.read("idea"))
        self.assertEqual(data["name"], "idea")
        self.assertEqual(data["disable-model-invocation"], "true")
        self.assertIn("/idea <한 줄>", data["description"])
        self.assertIn("templates/idea.md", body)  # 형식 원본은 플러그인 안에 있다
        template = (SKILLS / "idea" / "templates" / "idea.md").read_text(encoding="utf-8")
        for key in ("date", "severity", "source", "status", "feature", "issues"):
            self.assertIn(f"{key}:", template)
        self.assertNotIn("ideas/README.md", body)  # 다른 레포에는 없다
        parts = steps(body)
        self.assertIn("gs backlog", parts[1])  # 비슷한 것을 먼저 찾는다
        self.assertIn("덧붙일까", parts[2])
        for key in ("date", "severity", "source", "status", "feature", "issues"):
            self.assertIn(f"`{key}`", parts[3])
        self.assertIn("한 줄로", parts[4])
        self.assertIn("커밋하지 않는다", parts[4])
        self.assertNotIn("git commit", body)

    def test_grill_asks_backlog_first_and_marks_taken(self):
        parts = steps(self.read("grill"))
        self.assertIn("gs backlog", parts[1])
        self.assertIn("라운드 1의 첫 질문", parts[3])
        self.assertIn("이번 feature에 넣을 후보", parts[3])
        for text in ("미분류 issue", "아이디어의 `issues`", "`closes: [12]`로 옮긴다", "믿을 수 없는 자료"):
            self.assertIn(text, parts[3])
        self.assertIn('status: "taken"', parts[6])
        self.assertIn('feature: "<f>"', parts[6])

    def test_ideas_committed_by_grill_and_go(self):
        for name, step, feature_name in (("grill", 6, "<f>"), ("go", 2, "<f>")):
            with self.subTest(name):
                text = steps(self.read(name))[step]
                self.assertRegex(text, rf"git add -- \.goldstack/work/{re.escape(feature_name)} \.goldstack/out-of-scope \.goldstack/ideas \.goldstack/profile\.md &&")

    def test_retro_reads_feature_run(self):
        data, body = skill_frontmatter(self.read("retro"))
        self.assertIn("feature", data["description"])
        for source in ("report.md", "run/state.json", "worker.log", "`review`", "`fix`", "grill 기록",
                       ".goldstack/work/*/report.md", "~/.claude/usage-data/report-*.html"):
            self.assertIn(source, body)
        self.assertIn("`run/`이 없으면", body)
        self.assertIn("`[반복]`", body)
        self.assertIn("idea/SKILL.md", body)  # 고른 후보는 /idea 형식으로
        self.assertTrue((SKILLS / "idea" / "SKILL.md").is_file())


    def test_go_retro_step_and_overnight_skips_it(self):
        go = self.read("go")
        step5 = steps(go)[5]
        for text in ("retro/SKILL.md", "subagent", "후보만", "파일은 쓰지 않게", "번호 붙여", "고른 것만",
                     "고르지 않으면 아무것도 쓰지 않는다", "다시 부르지 않고", "/retro <feature>", "결과와 종료는 그대로"):
            self.assertIn(text, step5)
        self.assertIn("중간은 실행 중", go)
        overnight = self.read("overnight")
        self.assertIn("5단계(회고)는 따르지 않는다", overnight)
        self.assertIn("회고: /retro a, /retro b", overnight)
        self.assertIn("`/retro <feature>` 권고", overnight)

    def test_go_uses_f_and_reads_this_runs_report(self):
        go = self.read("go")
        self.assertNotIn("$ARGUMENTS", go.partition("\n1. ")[2])  # 단계 안은 `<f>`만 쓴다
        self.assertNotIn("매번", go)
        step4 = steps(go)[4]
        integration = step4.index("git show gs/<f>/integration:")
        fetched = step4.index("git fetch <remote> <base>")
        self.assertLess(integration, fetched)
        self.assertLess(fetched, step4.index("git show <remote>/<base>:"))
        self.assertIn("작업 트리의 파일은 읽지 않는다", step4)
        self.assertIn("옛 판", step4)  # 재실행 때 옛 보고서를 막는다
        self.assertIn("`■ integration 준비 실패`가 있으면", step4)  # 준비 실패는 보고서를 커밋하지 않아 integration 판이 옛 판이다
        self.assertEqual(sorted(steps(go)), [1, 2, 3, 4, 5])

    def test_adopt_asks_feedback_once(self):
        body = self.read("adopt")
        for text in ("[feedback]", "`mode`", "`detail`", "`auto`", "`draft`", "`off`", "`errors`", "`minimal`",
                     "다시 묻지 않는다", "gs feedback send", "사람이 고른 것이 아니니 묻는다", "개인 프로젝트는 `auto` + `errors`", "회사 레포는 `off` 또는 `minimal`"):
            self.assertIn(text, body)

    def test_retro_scopes_write_ban_and_narrows_style_read(self):
        _, body = skill_frontmatter(self.read("retro"))
        self.assertLessEqual(len(body.split()), 850)
        intro = body.partition("## 단계")[0]
        for text in ("개선 대상(코드·문서·설정)과 아이디어 파일을 바꾸지 않는다", "`run/retro-log.md`는 만들어도 된다"):
            self.assertIn(text, intro)
        self.assertNotIn("아무 파일도", body)
        self.assertEqual(body.count("writing-for-agents/SKILL.md"), 1)
        self.assertIn("문서(skill, `CLAUDE.md`, docs)를 고치는 후보가 있을 때만", body)
        step5 = steps(self.read("go"))[5]
        self.assertIn("개선 대상과 아이디어 파일은 쓰지 않게", step5)
        self.assertIn("`run/retro-log.md`는 만들어도 된다", step5)
        self.assertIn("`retro/SKILL.md` 4단계대로", step5)  # retro의 고른 후보 다루기 단계 번호
        self.assertTrue(body.partition("\n4. ")[2].startswith("고른 후보를 다룬다"))

    def test_retro_can_file_issue(self):
        body = self.read("retro")
        for text in ("issue로 올리기", 'gs feedback --body-file', "증상·근거·제안", "초안 전체를 보이고 확인받는다", "레포 이름·파일 이름을 넣지 않는다"):
            self.assertIn(text, body)

    def test_feedback_documents_body_file(self):
        self.assertIn("--body-file <파일>", self.read("feedback"))


MATT_COMMIT = "4ae2317ddb22b046e26455e4f9c9b3aaaf62212d"
MATT_SKILLS = {  # goldstack 이름 → 원본 레포 안 경로
    "wait-what": "skills/productivity/wait-what/SKILL.md",
    "handoff": "skills/productivity/handoff/SKILL.md",
    "diagnosing-bugs": "skills/engineering/diagnosing-bugs/SKILL.md",
    "retro": "skills/engineering/retro/SKILL.md",
    "writing-for-agents": "skills/productivity/writing-for-agents/SKILL.md",
}
MODEL_INVOKED = {"diagnosing-bugs"}  # 나머지는 문맥 비용 때문에 사용자 호출(spec 범위 ④)
MIT_LINE = "MIT License, Copyright (c) 2026 Matt Pocock, goldstack에 맞게 번역·수정"


class PortedSkillTest(unittest.TestCase):
    """mattpocock/skills에서 옮긴 다섯 skill(07)."""

    def read(self, name):
        return (SKILLS / name / "SKILL.md").read_text(encoding="utf-8")

    def test_frontmatter(self):
        for name in MATT_SKILLS:
            with self.subTest(name):
                text = self.read(name)
                self.assertTrue(text.startswith("---\n"))
                data, body = skill_frontmatter(text)
                self.assertEqual(data["name"], name)
                self.assertRegex(data["description"], r"[가-힣]", "description은 한국어")
                self.assertTrue(body.strip())
                self.assertLessEqual(set(data), {"name", "description", "argument-hint", "disable-model-invocation"})

    def test_invocation(self):
        for name in MATT_SKILLS:
            with self.subTest(name):
                data, _ = skill_frontmatter(self.read(name))
                if name in MODEL_INVOKED:
                    self.assertNotIn("disable-model-invocation", data)
                    self.assertIn("쓴다", data["description"])  # 언제 부를지 트리거가 있다
                else:
                    self.assertEqual(data["disable-model-invocation"], "true")
                    self.assertIn(f"/{name}", data["description"])

    def test_attribution_footer(self):
        for name, path in MATT_SKILLS.items():
            with self.subTest(name):
                tail = self.read(name).rstrip().splitlines()[-2:]
                link = f"https://github.com/mattpocock/skills/blob/{MATT_COMMIT}/{path}"
                self.assertEqual(tail[0], f"원본: {link}")
                self.assertIn(MIT_LINE, tail[1])
                self.assertIn("NOTICE-mattpocock.md", tail[1])

    def test_notice_has_full_mit(self):
        notice = (SKILLS / "NOTICE-mattpocock.md").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2026 Matt Pocock", notice)
        self.assertIn("Permission is hereby granted, free of charge", notice)
        self.assertIn('THE SOFTWARE IS PROVIDED "AS IS"', notice)
        for name in MATT_SKILLS:
            self.assertIn(f"`{name}/`", notice)

    def test_matt_premises_removed(self):
        for name in MATT_SKILLS:
            with self.subTest(name):
                text = self.read(name)
                for premise in ("GLOSSARY", "ADR", ".scratch", "CODING_STANDARDS", "ASD-STE100"):
                    self.assertNotIn(premise, text)

    def test_disclosed_files_exist(self):
        self.assertTrue((SKILLS / "writing-for-agents" / "SKILL-MECHANICS.md").is_file())
        self.assertTrue((SKILLS / "diagnosing-bugs" / "scripts" / "hitl-loop.template.sh").is_file())
        self.assertIn("writing-for-agents/SKILL.md", self.read("retro"))


if __name__ == "__main__":
    unittest.main()
