"""/overnight skill(goldstack-v8 09). 실제 밤샘 동작은 첫 사용에서 확인한다. 여기서는 지침이 빠지지 않았는지와, 지침이 말하는 gs 출력이 엔진과 맞는지 본다."""
import unittest
from pathlib import Path

from gs import config, go, notify, overnight, selfupdate
from test_skills import SKILLS, skill_frontmatter

SRC = Path(go.__file__).resolve().parent


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
        self.assertIn("/overnight <feature> … | resume | add <feature>", self.data["description"])
        self.assertEqual(self.data["argument-hint"], "<feature> … | resume | add <feature>")
        self.assertLessEqual(set(self.data), {"name", "description", "argument-hint", "disable-model-invocation"})

    def test_branches_on_resume(self):
        head = self.body.partition("\n## ")[0]
        self.assertIn("`$ARGUMENTS`가 `resume`이면", head)
        self.assertIn("이어받기", self.parts)
        self.assertIn("`add <f>`이면 [대기열에 더하기](#대기열에-더하기)", head)
        self.assertIn("대기열에 더하기", self.parts)

    def test_start_round_is_one_message(self):
        self.assert_all_in("1. 시작 라운드", "한 메시지", "순서와 독립", "사소한 수정 허락 범위", "텔레그램",
                           "yes = 추천 전부 수락", "이렇게 읽었다")

    def test_file_is_only_ground(self):
        self.assert_all_in("2. 파일", ".goldstack/overnight/<날짜>.md", "## 받은 허락", "## 쓴 허락",
                           "## 아침에 물을 것", "## 결과", "이 파일만 근거", "파일에 없는 허락은 없는 것",
                           "Edit 도구로 고친다")
        self.assertIn(".goldstack/overnight/", config.IGNORE_LINES)  # gs init이 넣는 gitignore 줄

    def test_preflight(self):
        self.assert_all_in("3. 사전 점검", "세션 권한 모드", "git push <remote> <base>", "`gs check`",
                           "미커밋 grill", "원격 앞섬", "디스크", "CLI 로그인", "버전 경고", "gs doctor")

    def test_preflight_types_the_night_commands(self):
        """사전 점검이 밤에 칠 명령과 같은 모양으로 친다. /go 2단계의 add 경로와 commit -m, Edit, self-update."""
        section = self.parts["3. 사전 점검"]
        go_step2 = (SKILLS / "go" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("git add -- .goldstack/work/<f> .goldstack/out-of-scope .goldstack/ideas .goldstack/profile.md", go_step2)
        for text in ("git add -- .goldstack/work/<f> .goldstack/out-of-scope .goldstack/ideas .goldstack/profile.md",
                     'git commit -m "grill: <f>" --dry-run', "git pull --ff-only <remote> <base>",
                     "git show gs/<f>/integration:.goldstack/work/<f>/report.md", "Edit 도구",
                     "6단계의 `gs overnight next <f>`", "gs self-update --from <원격 주소>",
                     "`gs overnight disarm`", "`gs overnight add <f>`"):
            with self.subTest(text):
                self.assertIn(text, section)
        self.assertNotIn("git commit --dry-run", section)  # 밤의 `git commit -m …`과 모양이 달라 다른 규칙에 걸린다

    def test_telegram_goes_through_gs_notify(self):
        self.assertIn("`gs notify --check`", self.parts["3. 사전 점검"])
        self.assertIn("`gs notify .goldstack/overnight/<날짜>-telegram.txt`", self.parts["7. 아침 보고"])
        for text in ("curl", "--data-urlencode", "api.telegram.org", "TG_TOKEN=$(", "이 한 줄만 체인"):
            self.assertNotIn(text, self.body)
        self.assertTrue(callable(notify.command))

    def test_no_incident_story_or_self_update_internals(self):
        for text in ("v7", "GitHub 500", "프로세스 확인", "프로세스를", "설치 기록", "설치 commit이 남게"):
            self.assertNotIn(text, self.body)

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

    def test_arms_before_saying_you_can_sleep(self):
        section = self.parts["5. 띄우기"]
        self.assert_in_order(section, "`gs overnight arm`", "자도 된다")
        self.assertIn("사람이 앞에 있으면", section)  # 밤에 다음 feature를 띄울 때는 다시 치지 않는다
        self.assertIn("`gs go`, 묶기 명령, `gs overnight arm`은 5단계가 사람 앞에서 처음", self.parts["3. 사전 점검"])

    def test_disarms_at_the_very_end(self):
        """아침 보고와 알림까지 켠 채로 간다. 멈춘 밤도 7단계로 오므로 여기서 함께 끈다."""
        self.assert_in_order(self.parts["7. 아침 보고"], "`## 아침 보고`", "`gs notify .goldstack", "`gs overnight disarm`")
        self.assertIn("멈춘 밤도", self.parts["7. 아침 보고"])
        self.assertIn("7단계로 간다", self.parts["멈출 조건"])
        self.assert_in_order(self.parts["이어받기"], "`## 아침 보고`", "`gs overnight disarm`")

    def test_refused_disarm_goes_back_to_the_chain(self):
        """보고와 끄기 사이에 더해진 줄. 엔진이 끄기를 거부하므로 skill이 그 말을 듣고 잇는다."""
        section = self.parts["7. 아침 보고"]
        self.assert_in_order(section, "`gs overnight disarm`", f"{overnight.ROWS_LEFT} 거부하면 사이 단계로 돌아간다")
        self.assertIn("`## 아침 보고`에 넣고(있으면 고친다)", section)  # 돌아왔다 다시 오면 보고가 이미 있다
        self.assertIn("7단계 끝처럼 `gs overnight disarm`", self.parts["이어받기"])

    def test_resume_arms_when_it_binds_to_a_running_go(self):
        bound = next(line for line in self.parts["이어받기"].splitlines() if "실행 중이면 다시 띄우지 않는다" in line)
        self.assertIn("`gs overnight arm`", bound)

    def test_chain_picks_up_rows_added_during_the_run(self):
        section = self.parts["6. 잇기"]
        self.assert_in_order(section, "완료 알림에 깨어나면", "파일을 다시 읽고", "판정한다")
        self.assertIn("`<다음>`은 다시 읽은 `결과`의 첫 `대기` 줄이다", section)
        self.assert_in_order(self.parts["7. 아침 보고"], "파일을 다시 읽어 `대기` 줄이 생겼으면 사이 단계로", "한 장을 쓴다")

    def test_morning_report_moves_the_denied_log(self):
        section = self.parts["7. 아침 보고"]
        self.assert_in_order(section, overnight.DENIED_LOG, "`쓴 허락`에 옮긴다", "한 장을 쓴다", "거부된 호출: …")

    def test_add_asks_only_independence_and_does_not_move_base(self):
        section = self.parts["대기열에 더하기"]
        self.assertIn("독립인지만 묻는다", section)
        self.assertIn("base를 움직이지 않는다", section)
        self.assert_in_order(section, "독립인지만", "`gs check <f>`", "디스크", "CLI 로그인", "`gs overnight add <f>`")
        for text in ("git push <remote>", "git pull --", "`gs go <", "텔레그램을"):
            with self.subTest(text):
                self.assertNotIn(text, section)

    def test_add_makes_a_missing_night_file_with_only_what_it_asked(self):
        section = self.parts["대기열에 더하기"]
        self.assert_in_order(section, "없거나 끝났으면 2단계로 만들고", "사소한 수정 B", "다시 친다")

    def test_add_becomes_coordinator_only_when_nobody_carries_on(self):
        section = self.parts["대기열에 더하기"]
        self.assertTrue(overnight.NO_COORDINATOR.startswith("코디네이터: 없음"))
        self.assert_in_order(section, f"`{overnight.NO_COORDINATOR}`이 없으면 끝낸다", "`gs status`에 `실행 중(pid N)`이 없으면",
                             "`/overnight resume`", "있으면 이 세션이 잇는다", "세션 권한 모드(push·`gs overnight next` 빼고)", "4단계 안내",
                             "이어받기의 `실행 중`처럼 묶고", "자도 된다")

    def test_go_points_to_add_instead_of_a_parallel_go(self):
        go_skill = (SKILLS / "go" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("`/overnight add <f>`", go_skill.partition("한계:")[2])

    def test_chain_order(self):
        section = self.parts["6. 잇기"]
        self.assertIn("완료 알림", section)
        between = section.partition("**사이 단계.**")[2]
        self.assert_in_order(between, "`gs overnight next <다음>`", "환경 사실", "`gs check <다음>`", "push", "다음 `gs go`")
        self.assertNotIn("uv tool install --reinstall", between)

    def test_chain_uses_next_and_leaves_judgment_to_the_model(self):
        """묶은 명령을 따로 치지 않는다. §6 재확인과 spec 수정은 명령이 아니라 모델이 한다."""
        between = self.parts["6. 잇기"].partition("**사이 단계.**")[2].partition("`<다음>`은 다시 읽은")[0]
        for text in ("git pull", "`gs self-update`.", "pyproject.toml"):
            with self.subTest(text):
                self.assertNotIn(text, between)
        self.assert_in_order(between, "`gs overnight next <다음>`", "모델이 한다", "환경 사실(§6)", "spec을 고치고")
        self.assert_in_order(between, "spec을 고쳤거나", "`gs check <다음>`이 오류·경고 0")
        self.assertIn("timeout", between)  # 재설치가 Bash 기본 제한(2분)에 잘리지 않는다

    def test_chain_says_what_next_prints(self):
        """skill이 읽는 줄이 엔진에서 바뀌면 여기서 빨개진다."""
        between = self.parts["6. 잇기"].partition("**사이 단계.**")[2]
        self.assertIn(f"`{overnight.STEP_FAILED}` 줄을 이유에 옮긴다", between)
        self.assertIn(f"`{overnight.REBASE_CONFLICT}`이면 `<다음>`은 `미실행`", between)
        self.assertIn("어느 단계든 실패하면 멈출 조건", between)
        self.assertIn("사이 단계 명령 실패", self.parts["멈출 조건"])

    def test_preflight_types_next_but_add_does_not(self):
        """밤에 칠 모양을 사람 앞에서 쳐 본다. 도는 실행에 붙는 add는 base를 움직이므로 치지 않는다."""
        mode = self.parts["3. 사전 점검"].partition("**세션 권한 모드**")[2]
        self.assertIn("`gs overnight next <f>`", mode)
        self.assertIn("`gs overnight next <f>`(셋 다 실패해도 창만 안 뜨면 된다)", mode)  # 도는 `gs go`가 재설치를 거부시킨다
        self.assertNotIn("git pull", mode.partition("**디스크**")[0])  # 밤에는 next가 친다
        add = self.parts["대기열에 더하기"]
        self.assertIn("`gs overnight next` 빼고", add)
        self.assertIn("base를 움직이지 않는다", add)

    def test_reinstall_uses_self_update_which_checks_running_go(self):
        """self-update가 전역 --repo와 python -m으로 뜬 gs go를 찾아 실행 중인 설치본을 바꾸지 않는다."""
        between = self.parts["6. 잇기"].partition("**사이 단계.**")[2]
        for text in ("`gs self-update`", "거부", "--from <원격 주소>"):
            self.assertIn(text, between)
        self.assertNotIn("pgrep", self.body)
        self.assertNotIn("running_go", self.body)
        self.assertIn("6단계의 `gs overnight next <f>`", self.parts["3. 사전 점검"])  # 새 명령 모양도 밤 전에 쳐 본다
        self.assertIn("그 완료 알림 뒤 다시 친다", between)  # 거부되면 끝나기를 기다렸다 다시 친다
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
        self.assertIn("`finish.base_report_tried`", row(section, "verified"))  # 올라가지 않는 보고서를 끝없이 다시 띄우지 않는다
        self.assertIn("`finish.base_report_tried`도 없다", row(section, "덜 끝남"))
        judging = section.partition("**판정.**")[2].partition("| 판정 |")[0]
        for text in ("gs/<f>/integration:.goldstack/work/<f>/report.md", "브랜치가 없으면", "■ integration 준비 실패"):
            self.assertIn(text, judging)  # /go 4단계와 같은 판을 읽는다
        go_step4 = (SKILLS / "go" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("■ integration 준비 실패", go_step4)
        self.assertIn("git show gs/<f>/integration:.goldstack/work/<f>/report.md", go_step4)

    def test_stop_conditions(self):
        self.assert_all_in("멈출 조건", "결정을 바꿔야 하는 어긋남", "경고 남음", "권한 승인 창", go.NETWORK_ABORT,
                           "다음 `gs go`로 다시 잇기를 먼저 시도", "독립", "재개 명령", "미실행")

    def test_never_list(self):
        self.assert_all_in("하지 않는 일", "force push", "원격 브랜치 수동 삭제", "허락에 없는 결정")

    def test_morning_report(self):
        self.assert_all_in("7. 아침 보고", "verified", "멈춤", "PR", "고친 사소한 것", "남은 질문", "피드백",
                           "텔레그램", "요약 한 통", "gs notify")

    def test_morning_table_shows_remaining_high_and_skipped_reviews(self):
        self.assert_all_in("7. 아침 보고", "| feature | 결과 | PR | 남은 high·건너뛴 리뷰 | 이유·재개 명령 |",
                           "남은 high 2(보고만 1 · 확인 못 함 1) · 건너뛴 리뷰: 05", "`verified`는 바꾸지 않는다")

    def test_resume(self):
        self.assert_all_in("이어받기", "/overnight resume", ".goldstack/overnight/", "state.json", "`gs status <f>`",
                           "세션 권한 모드", "다시 띄우지 않는다")

    def test_resume_checks_new_session_without_questions(self):
        """새 세션의 권한 점검과 깨어 있기 안내는 `아침에 물을 것` 조건 밖에서 돈다."""
        section = self.parts["이어받기"]
        steps = [line for line in section.splitlines() if line[:2] in {f"{n}." for n in range(1, 9)}]
        check = next(line for line in steps if "세션 권한 모드" in line)
        self.assertIn("없어도", check)
        self.assertNotIn("남았으면", check)
        asking = next(line for line in steps if "번호 질문" in line)
        self.assertNotIn("세션 권한 모드", asking)
        self.assertLess(steps.index(check), steps.index(asking))

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
