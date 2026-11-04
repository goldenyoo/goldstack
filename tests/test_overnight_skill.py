"""/overnight skill(goldstack-v8 09). 실제 밤샘 동작은 첫 사용에서 확인한다. 여기서는 지침이 빠지지 않았는지와, 지침이 말하는 gs 출력이 엔진과 맞는지 본다."""
import unittest
from pathlib import Path

from gs import config, go, selfupdate
from test_skills import SKILLS, skill_frontmatter

SRC = Path(go.__file__).resolve().parent
WORD_LIMIT = 1700  # 뻗침 방지(표의 `|`도 센다). /go 400, /grill 450보다 넓은 것은 사전 점검부터 이어받기까지 한 문서에 있어서다


def read():
    return skill_frontmatter((SKILLS / "overnight" / "SKILL.md").read_text(encoding="utf-8"))


def sections(body):
    """`## 제목`을 {제목: 글}로 자른다. 코드 블록 안의 `## `(파일 양식)는 제목이 아니다."""
    parts, title, fenced = {}, None, False
    for line in body.splitlines():
        fenced ^= line.startswith("```")
        if line.startswith("## ") and not fenced:
            title = line[3:]
            parts[title] = ""
        elif title:
            parts[title] += line + "\n"
    return parts


def row(section, first_cell):
    """표에서 첫 칸이 first_cell인 줄."""
    return next(line for line in section.splitlines() if line.startswith(f"| {first_cell} |"))


class OvernightSkillTest(unittest.TestCase):
    def setUp(self):
        self.data, self.body = read()
        self.parts = sections(self.body)

    def assert_all_in(self, section, *texts):
        for text in texts:
            with self.subTest(text):
                self.assertIn(text, self.parts[section])

    def assert_in_order(self, text, *needles):
        positions = [text.index(needle) for needle in needles]
        self.assertEqual(positions, sorted(positions), needles)

    def test_frontmatter(self):
        self.assertEqual(self.data["name"], "overnight")
        self.assertEqual(self.data["disable-model-invocation"], "true")
        self.assertIn("/overnight <feature> … | resume", self.data["description"])
        self.assertEqual(self.data["argument-hint"], "<feature> … | resume")
        self.assertLessEqual(set(self.data), {"name", "description", "argument-hint", "disable-model-invocation"})

    def test_short(self):
        self.assertLess(len(self.body.split()), WORD_LIMIT)

    def test_branches_on_resume(self):
        head = self.body.partition("\n## ")[0]
        self.assertIn("`$ARGUMENTS`가 `resume`이면", head)
        self.assertIn("이어받기", self.parts)

    def test_start_round_is_one_message(self):
        self.assert_all_in("1. 시작 라운드", "한 메시지", "순서와 독립", "사소한 수정 허락 범위", "텔레그램",
                           "yes = 추천 전부 수락", "이렇게 읽었다")

    def test_file_is_only_ground(self):
        self.assert_all_in("2. 파일", ".goldstack/overnight/<날짜>.md", "## 받은 허락", "## 쓴 허락",
                           "## 아침에 물을 것", "## 결과", "이 파일만 근거", "파일에 없는 허락은 없는 것",
                           "git check-ignore")
        self.assertIn(".goldstack/overnight/", config.IGNORE_LINES)  # gs init이 넣는 gitignore 줄

    def test_preflight(self):
        self.assert_all_in("3. 사전 점검", "세션 권한 모드", "git push <remote> <base>", "재설치", "`gs check`",
                           "미커밋 grill", "원격 앞섬", "디스크", "CLI 로그인", "버전 경고", "gs doctor")

    def test_keep_awake_per_machine(self):
        section = self.parts["4. 깨어 있기"]
        self.assertIn("`uname -s`", section)
        mac, linux = row(section, "`Darwin`"), row(section, "`Linux`")
        for text in ("caffeinate -dims -w <gs pid>", "맥북", "전원", "덮개"):
            self.assertIn(text, mac)
        for text in ("systemd-inhibit", "tail --pid=<gs pid>", "서버", "tmux"):
            self.assertIn(text, linux)
        self.assertIn("없거나 실패하면 건너뛴다", section)

    def test_launch_one_feature_at_a_time(self):
        self.assert_all_in("5. 띄우기", "`gs go <f>`", "run_in_background", "`gs status <f>`", "실행 중(pid N)",
                           "자도 된다")
        self.assertIn('f"{name}: 실행 중(pid {pid})"', (SRC / "status.py").read_text(encoding="utf-8"))

    def test_chain_order(self):
        section = self.parts["6. 잇기"]
        self.assertIn("완료 알림", section)
        between = section.partition("**사이 단계.**")[2]
        self.assert_in_order(between, "git pull", "uv tool install --reinstall .",
                             "claude plugin marketplace update goldstack", "claude plugin update goldstack@goldstack",
                             "환경 사실", "`gs check <다음>`", "push", "다음 `gs go`")
        self.assertIn("pyproject.toml", between)  # gs 자신을 고친 레포를 가리는 법

    def test_reinstall_checks_running_go_like_self_update(self):
        """문자열 패턴은 전역 --repo와 python -m으로 뜬 gs go를 놓쳐 실행 중인 설치본을 바꾼다."""
        between = self.parts["6. 잇기"].partition("**사이 단계.**")[2]
        self.assert_in_order(between, "uv run python -c 'from gs.selfupdate import running_go; print(*running_go())'",
                             "uv tool install --reinstall .")
        self.assertNotIn("pgrep", self.body)
        self.assertIn("6단계의 실행 확인", self.parts["3. 사전 점검"])  # 새 명령 모양도 밤 전에 쳐 본다
        self.assertTrue(callable(selfupdate.running_go))
        for command in ("gs go demo", "/venv/bin/python /venv/bin/gs --repo /tmp/other go demo",
                        "/venv/bin/python -m gs.cli go demo"):
            with self.subTest(command):
                self.assertTrue(selfupdate._is_go(command))

    def test_verdict_table(self):
        section = self.parts["6. 잇기"]
        verified = row(section, "verified")
        for text in ("`finish.phase`", "`merged`", "`report.md`", "`마무리: verified`", "종료 코드 0"):
            self.assertIn(text, verified)
        self.assertIn("/go` 4단계와 달리", row(section, "중단(네트워크)"))
        self.assertIn("두 번까지", section)

    def test_stop_conditions(self):
        self.assert_all_in("멈출 조건", "결정을 바꿔야 하는 어긋남", "경고 남음", "권한 승인 창", go.NETWORK_ABORT,
                           "다음 `gs go`로 다시 잇기를 먼저 시도", "독립", "재개 명령", "미실행")

    def test_never_list(self):
        self.assert_all_in("하지 않는 일", "force push", "원격 브랜치 수동 삭제", "허락에 없는 결정")

    def test_morning_report(self):
        self.assert_all_in("7. 아침 보고", "verified", "멈춤", "PR", "고친 사소한 것", "남은 질문", "피드백",
                           "텔레그램", "요약 한 통", "--data-urlencode")

    def test_resume(self):
        self.assert_all_in("이어받기", "/overnight resume", ".goldstack/overnight/", "state.json", "`gs status <f>`",
                           "세션 권한 모드", "다시 띄우지 않는다")

    def test_engine_says_what_skill_reads(self):
        """판정 표가 읽는 값이 gs 쪽에서 바뀌면 여기서 빨개진다."""
        self.assertEqual(go.EXIT_NETWORK, 3)
        self.assertIn("종료 코드 3", self.parts["6. 잇기"])
        self.assertEqual(go.NETWORK_ABORT, "중단(네트워크)")
        status = (SRC / "status.py").read_text(encoding="utf-8")
        self.assertIn("중단됨(gs go pid", status)
        self.assertIn("중단됨(", self.parts["6. 잇기"])
        self.assertIn('return " · ".join([f"마무리: {phase}"', (SRC / "report.py").read_text(encoding="utf-8"))
        self.assertIn('".goldstack/work/*/run/"', (SRC / "config.py").read_text(encoding="utf-8"))

    def test_follows_go_skill(self):
        self.assertTrue((SKILLS / "go" / "SKILL.md").is_file())
        self.assertIn("`go/SKILL.md`", self.body)
        self.assertIn("`/go` 2단계", self.parts["6. 잇기"])


if __name__ == "__main__":
    unittest.main()
