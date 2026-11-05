import contextlib
import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import cli, config, git
from gs import feature as featmod
from support import isolate_git_env

REPO = Path(__file__).resolve().parents[1]

SPEC = """---
feature: demo
verify: "true"
---
# demo
"""


def ticket(tid, blocked_by="[]", model="claude", reviewer="codex", extra=""):
    return f'---\nid: "{tid}"\ntitle: t{tid}\nblocked_by: {blocked_by}\nmodel: {model}\nreviewer: {reviewer}\n{extra}---\n## 목표\n'


class CheckTest(unittest.TestCase):
    def setUp(self):
        isolate_git_env(self)
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git.run(self.repo, "init", "-q")
        git.run(self.repo, "remote", "add", "origin", "https://github.com/owner/repo.git")
        self.bin = self.repo / "bin"
        self.bin.mkdir()
        (self.bin / "git").symlink_to(shutil.which("git"))
        for name in ("gh", "claude", "codex", "agy"):
            path = self.bin / name
            path.write_text("#!/bin/sh\nexit 0\n")
            path.chmod(0o755)
        patch = mock.patch.dict(os.environ, {"PATH": str(self.bin)})
        patch.start()
        self.addCleanup(patch.stop)
        (self.repo / ".goldstack").mkdir()
        (self.repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
        self.tickets = self.repo / ".goldstack/work" / "demo" / "tickets"
        self.tickets.mkdir(parents=True)
        (self.repo / ".goldstack/work" / "demo" / "spec.md").write_text(SPEC)

    def tearDown(self):
        self.tmp.cleanup()

    def write(self, name, text):
        (self.tickets / name).write_text(text)

    def run_check(self, *extra):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = cli.main(["--repo", str(self.repo), "check", "demo", *extra])
        return code, out.getvalue(), err.getvalue()

    def assert_error(self, needle, *extra):
        code, out, err = self.run_check(*extra)
        self.assertEqual(code, 1, out + err)
        self.assertIn(needle, err)
        return err

    def test_ok(self):
        self.write("01-a.md", ticket("01"))
        self.write("02-b.md", ticket("02", '["01"]', model="codex", reviewer="claude"))
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""))
        self.assertIn("순서: 01 02", out)
        self.assertIn("지금 시작 가능: 01", out)

    def model_lines(self, out):
        return [line for line in out.splitlines() if " · 리뷰 " in line]

    def test_actual_models_with_tiers(self):
        self.write("01-a.md", ticket("01", extra="tier: large\n"))
        self.write("02-b.md", ticket("02", model="codex", reviewer="claude", extra="tier: small\n"))
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('review = "large"', 'review = "medium"'))
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.model_lines(out), [
            "01 large claude opus/xhigh · 리뷰 codex gpt-6.1-sol/medium",
            "02 small codex gpt-6-luna/medium · 리뷰 claude sonnet/high",
        ])
        self.assertLess(out.index("지금 시작 가능:"), out.index("01 large"))

    def test_actual_models_without_tiers(self):
        self.write("01-a.md", ticket("01", extra="tier: large\nsecond_reviewer: agy\n"))
        self.write("02-b.md", ticket("02", model="codex", reviewer="claude"))
        path = self.repo / config.CONFIG_PATH
        text = path.read_text()
        path.write_text(text[:text.index("[tiers]")] + text[text.index("[agy]"):])
        code, out, err = self.run_check()
        self.assertEqual(code, 0, err)
        self.assertEqual(self.model_lines(out), [
            "01 large claude CLI 기본값 · 리뷰 codex CLI 기본값 + agy gemini-4-argon-high",
            "02 medium codex CLI 기본값 · 리뷰 claude opus",
        ])

    def test_actual_models_second_reviewer_and_no_effort(self):
        self.write("01-a.md", ticket("01", extra="tier: large\nsecond_reviewer: agy\n"))
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.model_lines(out), [
            "01 large claude opus/xhigh · 리뷰 codex gpt-6.1-sol/high + agy gemini-4-argon-high",
        ])

    def test_actual_models_only_selected_tickets(self):
        self.write("01-a.md", ticket("01", extra="tier: large\n"))
        self.write("02-b.md", ticket("02", '["01"]', extra="tier: small\n"))
        code, out, err = self.run_check("--only", "02")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(self.model_lines(out), [
            "02 small claude sonnet/medium · 리뷰 codex gpt-6.1-sol/high",
        ])

    def test_actual_models_hidden_on_errors(self):
        self.write("01-a.md", ticket("01", extra="tier: large\n"))
        path = self.repo / config.CONFIG_PATH
        for change in ('large = "opus/xhigh"', 'review = "large"'):
            with self.subTest(change=change):
                original = path.read_text()
                path.write_text(original.replace(change, change.split(" = ")[0] + ' = "invalid/bad"'))
                code, out, err = self.run_check()
                self.assertEqual(code, 1, out + err)
                self.assertEqual(self.model_lines(out), [])
                path.write_text(original)
        (self.bin / "codex").unlink()
        code, out, err = self.run_check()
        self.assertEqual(code, 1, out + err)
        self.assertEqual(self.model_lines(out), [])

    def test_telegram_without_secrets_warns(self):
        self.write("01-a.md", ticket("01"))
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace("telegram = false", "telegram = true"))
        warn = "경고: notify.telegram이 켜져 있지만 .goldstack/local.env에 {}(예시: .goldstack/local.env.example)"
        code, out, err = self.run_check()
        self.assertEqual(code, 0, out + err)
        self.assertIn(warn.format("TG_TOKEN이 없다"), err.splitlines())
        self.assertIn(warn.format("TG_CHAT_ID가 없다"), err.splitlines())
        self.assertIn("경고 2", out)

        (self.repo / ".goldstack/local.env").write_text("TG_TOKEN=\nTG_CHAT_ID=42\n")  # 빈 값도 없는 것
        code, out, err = self.run_check()
        self.assertEqual(err.splitlines(), [warn.format("TG_TOKEN이 없다")])

        (self.repo / ".goldstack/local.env").write_text("TG_TOKEN=1:abc\nTG_CHAT_ID=42\n")
        self.assertEqual(self.run_check()[2], "")

    def test_telegram_off_does_not_need_secrets(self):
        self.write("01-a.md", ticket("01"))
        self.assertEqual(self.run_check()[2], "")

    def test_missing_field(self):
        self.write("01-a.md", '---\nid: "01"\ntitle: t\nblocked_by: []\nmodel: claude\n---\n')
        self.assert_error("`reviewer`가 없다")

    def test_same_family_review(self):
        self.write("01-a.md", ticket("01", reviewer="claude"))
        self.assert_error("리뷰는 다른 계열")

    def test_unknown_family(self):
        self.write("01-a.md", ticket("01", model="gpt"))
        self.assert_error("`model` 값 `gpt`")

    def test_duplicate_id(self):
        self.write("01-a.md", ticket("01"))
        self.write("01-b.md", ticket("01"))
        self.assert_error("겹친다")

    def test_filename_mismatch(self):
        self.write("02-a.md", ticket("01"))
        self.assert_error("파일 이름")

    def test_unknown_ref(self):
        self.write("01-a.md", ticket("01", '["09"]'))
        self.assert_error("없는 티켓이 있다: 09")

    def test_cycle_shows_path(self):
        self.write("01-a.md", ticket("01", '["02"]'))
        self.write("02-b.md", ticket("02", '["01"]'))
        self.assert_error("순환: 01 → 02 → 01")

    def test_bad_value_does_not_cascade_into_unknown_ref(self):
        self.write("01-a.md", ticket("01", model="gpt"))
        self.write("02-b.md", ticket("02", '["01"]'))
        err = self.assert_error("`gpt`")
        self.assertNotIn("없는 티켓", err)

    def test_frontmatter_error_has_line(self):
        self.write("01-a.md", ticket("01", blocked_by="\n- 02"))
        self.assert_error("01-a.md:4: 값이 비어 있다")  # 4번 줄 = `blocked_by:`

    def test_unknown_key_is_warning(self):
        self.write("01-a.md", ticket("01", extra="owner: me\n"))
        code, out, err = self.run_check()
        self.assertEqual(code, 0)
        self.assertIn("경고:", err)
        self.assertIn("경고 1", out)

    def test_spec_errors(self):
        self.write("01-a.md", ticket("01"))
        (self.repo / ".goldstack/work" / "demo" / "spec.md").write_text("---\nfeature: other\nmax_workers: 0\n---\n")
        err = self.assert_error("`verify`가 없거나")
        self.assertIn("디렉터리 이름", err)
        self.assertIn("`max_workers`", err)

    def test_spec_verify_must_be_one_nonempty_line(self):  # codex 리뷰 지적 1
        self.write("01-a.md", ticket("01"))
        for verify in ('""', '"   "', r'"echo a\nfalse"'):
            with self.subTest(verify):
                (self.repo / ".goldstack/work" / "demo" / "spec.md").write_text(f"---\nfeature: demo\nverify: {verify}\n---\n")
                self.assert_error("`verify`는 비어 있지 않은 한 줄")

    def test_spec_non_ascii_digit_is_error_not_crash(self):  # codex 리뷰 지적 3
        self.write("01-a.md", ticket("01"))
        (self.repo / ".goldstack/work" / "demo" / "spec.md").write_text('---\nfeature: demo\nverify: "true"\nmax_workers: ²\n---\n')
        self.assert_error("`max_workers`는 1 이상의 정수")

    def test_spec_verify_minutes(self):
        self.write("01-a.md", ticket("01"))
        spec = self.repo / ".goldstack/work" / "demo" / "spec.md"
        for value in ("0", "abc"):
            with self.subTest(value):
                spec.write_text(f'---\nfeature: demo\nverify: "true"\nverify_minutes: {value}\n---\n')
                self.assert_error("`verify_minutes`는 1 이상의 정수")
        spec.write_text('---\nfeature: demo\nverify: "true"\nverify_minutes: 7\n---\n')
        self.assertEqual(featmod.load(self.repo, "demo").spec.verify_minutes, 7)
        self.assertEqual(self.run_check()[::2], (0, ""))
        spec.write_text(SPEC)  # 키가 없으면 기본 20, 경고 없음
        self.assertEqual(featmod.load(self.repo, "demo").spec.verify_minutes, 20)
        self.assertEqual(self.run_check()[::2], (0, ""))

    def test_no_tickets(self):
        self.assert_error("티켓이 없다")

    def test_missing_feature(self):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()) as e:
            self.assertEqual(cli.main(["--repo", str(self.repo), "check", "nope"]), 1)
        self.assertIn("feature 디렉터리가 없다", e.getvalue())

    def test_only_marks_external_deps(self):
        self.write("01-a.md", ticket("01"))
        self.write("02-b.md", ticket("02", '["01"]'))
        self.write("03-c.md", ticket("03", '["02"]'))
        code, out, _ = self.run_check("--only", "02,03")
        self.assertEqual(code, 0)
        self.assertIn("범위: 02 03", out)
        self.assertIn("범위 밖 의존(끝났다고 가정): 02 ← 01", out)
        self.assertIn("지금 시작 가능: 02", out)

    def test_only_unknown_id(self):
        self.write("01-a.md", ticket("01"))
        self.assert_error("없는 티켓: 99", "--only", "01,99")

    def test_required_clis_missing_from_path(self):
        self.write("01-a.md", ticket("01"))
        self.write("02-b.md", ticket("02", model="agy", reviewer="codex"))
        for name in ("git", "gh", "claude", "codex", "agy"):
            with self.subTest(name=name):
                path = self.bin / name
                hidden = self.repo / name
                path.rename(hidden)
                try:
                    self.assert_error(f"CLI `{name}`가 PATH에 없다")
                finally:
                    hidden.rename(path)

    def test_cli_checks_only_selected_tickets(self):
        self.write("01-a.md", ticket("01"))
        self.write("02-b.md", ticket("02", model="agy", reviewer="codex"))
        (self.bin / "agy").unlink()
        code, out, err = self.run_check("--only", "01")
        self.assertEqual((code, err), (0, ""), out)
        self.assert_error("CLI `agy`가 PATH에 없다", "--only", "02")

    def test_reviewer_cli_is_required(self):
        self.write("01-a.md", ticket("01", model="codex", reviewer="agy"))
        (self.bin / "agy").unlink()
        self.assert_error("CLI `agy`가 PATH에 없다")

    def test_non_github_remote_error_uses_configured_remote(self):
        self.write("01-a.md", ticket("01"))
        path = self.repo / config.CONFIG_PATH
        path.write_text(path.read_text().replace('remote = "origin"', 'remote = "upstream"'))
        git.run(self.repo, "remote", "add", "upstream", "https://gitlab.com/owner/repo.git")
        for url in ("https://gitlab.com/owner/repo.git", "git@gitlab.com:owner/repo.git",
                    "https://github.com.example.org/owner/repo.git", "/tmp/github.com/repo.git"):
            with self.subTest(url=url):
                git.run(self.repo, "remote", "set-url", "upstream", url)
                code, out, err = self.run_check()
                self.assertEqual(code, 1, out + err)
                self.assertIn(f"오류: 원격 `upstream`의 URL `{url}`은 GitHub 저장소 형식이 아니다", err)
        for url in ("https://github.com/owner/repo.git", "git@github.com:owner/repo.git",
                    "ssh://git@github.com/owner/repo.git"):
            with self.subTest(url=url):
                git.run(self.repo, "remote", "set-url", "upstream", url)
                self.assertEqual(self.run_check()[::2], (0, ""))


class RealRepoTest(unittest.TestCase):
    def test_goldstack_v0_passes(self):
        out, err = io.StringIO(), io.StringIO()
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            # 이 레포는 병합 뒤 손으로 gs migrate한다(goldstack-v2 1-1). 그 전에는 옛 위치에서 복사한다.
            src = next(p for p in (REPO / ".goldstack/work/goldstack-v0", REPO / ".work/goldstack-v0") if p.is_dir())
            shutil.copytree(src, repo / ".goldstack/work/goldstack-v0")
            (repo / ".goldstack").mkdir(exist_ok=True)
            (repo / config.CONFIG_PATH).write_text(config.DEFAULT_CONFIG.format(base='"main"'))
            git.run(repo, "init", "-q")
            git.run(repo, "remote", "add", "origin", "https://github.com/owner/repo.git")
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err), \
                    mock.patch("gs.check.shutil.which", return_value="/test/cli"):
                code = cli.main(["--repo", str(repo), "check", "goldstack-v0"])
        self.assertEqual(code, 0, err.getvalue())
        self.assertIn("지금 시작 가능: 01 11", out.getvalue())


if __name__ == "__main__":
    unittest.main()
