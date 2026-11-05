"""텔레그램 알림(06): localhost 가짜 Bot API 서버로 전송·재시도·잘림·토큰 가림, `gs go` 끝 알림을 본다."""
import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest import mock

import support
from gs import config, notify, state

TOKEN = "123456:SECRET-token_value"


class FakeTelegram:
    """받은 요청(path, body)을 쌓는다. statuses를 앞에서부터 하나씩 응답 코드로 쓰고, 다 쓰면 200."""

    def __init__(self, statuses=(), echo_path=False):
        self.requests = []
        self.statuses = list(statuses)
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                fake.requests.append((self.path, json.loads(body)))
                code = fake.statuses.pop(0) if fake.statuses else 200
                if code == 200:
                    reply = {"ok": True, "result": {"message_id": len(fake.requests)}}
                else:  # 오류 설명에 경로(토큰 포함)를 그대로 되돌려 가림을 시험한다
                    reply = {"ok": False, "error_code": code,
                             "description": f"bad {self.path}" if echo_path else "server error"}
                data = json.dumps(reply).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    def texts(self):
        return [body["text"] for _, body in self.requests]


class FakeServerMixin:
    def serve(self, statuses=(), echo_path=False):
        fake = FakeTelegram(statuses, echo_path)
        self.addCleanup(fake.close)
        patch = mock.patch.dict(os.environ, {"GS_TELEGRAM_API": fake.url})
        patch.start()
        self.addCleanup(patch.stop)
        return fake


@mock.patch.object(notify, "RETRY_DELAY", 0)
class SendTest(FakeServerMixin, unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_ROLE", None)

    def test_success_posts_send_message(self):
        fake = self.serve()
        self.assertEqual(notify.send(TOKEN, "42", "안녕"), (True, ""))
        self.assertEqual(len(fake.requests), 1)
        path, body = fake.requests[0]
        self.assertEqual(path, f"/bot{TOKEN}/sendMessage")
        self.assertEqual((body["chat_id"], body["text"]), ("42", "안녕"))

    def test_retries_server_errors_three_times(self):
        fake = self.serve([500, 502])
        self.assertEqual(notify.send(TOKEN, "42", "x"), (True, ""))
        self.assertEqual(len(fake.requests), 3)

        fake = self.serve([500, 500, 500, 500])
        ok, error = notify.send(TOKEN, "42", "x")
        self.assertFalse(ok)
        self.assertEqual(len(fake.requests), 3)
        self.assertIn("HTTP 500", error)

    def test_error_body_read_failure_still_retries(self):
        def http_500(req, timeout):
            err = urllib.error.HTTPError(req.full_url, 500, "Internal Server Error", {}, None)
            err.read = mock.Mock(side_effect=TimeoutError("error response body timed out"))
            raise err

        self.serve()
        with mock.patch.object(urllib.request, "urlopen", side_effect=http_500) as urlopen:
            ok, error = notify.send(TOKEN, "42", "x")
        self.assertFalse(ok)
        self.assertEqual(urlopen.call_count, 3)
        self.assertIn("HTTP 500", error)
        self.assertNotIn(TOKEN, error)

    def test_client_error_is_not_retried(self):
        fake = self.serve([400])
        self.assertFalse(notify.send(TOKEN, "42", "x")[0])
        self.assertEqual(len(fake.requests), 1)

    def test_long_text_is_truncated_with_mark(self):
        fake = self.serve()
        self.assertTrue(notify.send(TOKEN, "42", "가" * 5000)[0])
        text = fake.texts()[0]
        self.assertLessEqual(len(text), 3900)
        self.assertTrue(text.endswith("… (잘림)"))
        self.assertTrue(text.startswith("가" * 3000))
        self.assertTrue(notify.send(TOKEN, "42", "나" * 3900)[0])
        self.assertEqual(fake.texts()[1], "나" * 3900)  # 정확히 한도면 그대로

    def test_token_is_masked_in_errors(self):
        self.serve([404], echo_path=True)
        ok, error = notify.send(TOKEN, "42", "x")
        self.assertFalse(ok)
        self.assertIn("/bot***/sendMessage", error)
        self.assertNotIn(TOKEN, error)
        # 연결 실패(서버 없음)와 잘못된 주소도 예외 없이 실패를 돌려준다
        for api in ("http://127.0.0.1:1", f"not-a-url-{TOKEN}"):
            with mock.patch.dict(os.environ, {"GS_TELEGRAM_API": api}):
                ok, error = notify.send(TOKEN, "42", "x")
            self.assertFalse(ok)
            self.assertTrue(error)
            self.assertNotIn(TOKEN, error)

    def test_never_raises(self):
        with mock.patch.object(notify, "_send", side_effect=RuntimeError(f"boom {TOKEN}")):
            self.assertEqual(notify.send(TOKEN, "42", "x"), (False, "RuntimeError: boom ***"))

    def test_worker_does_not_send(self):
        fake = self.serve()
        with mock.patch.dict(os.environ, {"GS_ROLE": "worker"}):
            self.assertFalse(notify.send(TOKEN, "42", "x")[0])
        self.assertEqual(fake.requests, [])


@mock.patch.object(notify, "RETRY_DELAY", 0)
class GoNotifyTest(FakeServerMixin, unittest.TestCase):
    """가짜 worker `gs go` + 가짜 Bot API 서버로 실행 끝 알림 본문을 본다."""
    BASE, REMOTE = "main", "origin"
    tearDown, go = support.GoTest.tearDown, support.GoTest.go
    rundir, parallel, integration = support.GoTest.rundir, support.GoTest.parallel, support.GoTest.integration
    final_report = support.GoTest.final_report

    def setUp(self):
        support.GoTest.setUp(self)
        os.environ.pop("GS_ROLE", None)  # gs go는 코디네이터로 돈다(GoTest의 환경 패치가 끝나면 되돌아온다)

    def enable(self, env=f"TG_TOKEN={TOKEN}\nTG_CHAT_ID=42\n"):
        sh = support.sh
        sh(self.repo, "git", "pull", "-q", "--ff-only", self.REMOTE, self.BASE)
        cfg = self.repo / config.CONFIG_PATH
        cfg.write_text(cfg.read_text().replace("telegram = false", "telegram = true"))
        (self.repo / ".gitignore").write_text(".goldstack/work/*/run/\n.goldstack/local.env\n")
        sh(self.repo, "git", "add", "-A")
        sh(self.repo, "git", "commit", "-qm", "notify on")
        sh(self.repo, "git", "push", "-q", self.REMOTE, self.BASE)
        if env is not None:
            (self.repo / ".goldstack/local.env").write_text(env)

    def test_success_message(self):
        fake = self.serve()
        self.enable()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(fake.texts(), ["✅ demo · main 병합\n티켓 1/1 병합 · 0분 · 남은 지적 0\n"
                                        "PR https://example.test/pr/1"])
        path, body = fake.requests[0]
        self.assertEqual((path, body["chat_id"]), (f"/bot{TOKEN}/sendMessage", "42"))
        self.assertNotIn(TOKEN, out + err)
        self.assertTrue(out.strip().splitlines()[-1].startswith("■ PR:"))  # 요약 뒤에 보낸다(출력 없음)

    def test_failure_message(self):
        fake = self.serve()
        self.enable()
        code, out, err = self.go("--only", "02,03")
        self.assertEqual(code, 1, out + err)
        self.assertEqual(fake.texts(), ["❌ demo · merged 티켓 없음 → 병합 안 함 · 티켓 0/2 "
                                        "(02 실패: worker 종료 코드 1) · 보고서 .goldstack/work/demo/report.md"])

    def test_revert_message(self):
        fake = self.serve()
        self.enable()
        self.parallel(1, verify='test "$(git log -1 --format=%s)" != "Merge feature"')
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 1, out + err)
        f = state.load(self.rundir, "demo").finish
        self.assertEqual(fake.texts(), [f"❌ demo · {f['outcome']} · 티켓 1/1 · 보고서 .goldstack/work/demo/report.md"])
        self.assertIn("revert", f["outcome"])

    def test_disabled_sends_nothing(self):
        fake = self.serve()
        (self.repo / ".goldstack/local.env").write_text(f"TG_TOKEN={TOKEN}\nTG_CHAT_ID=42\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(fake.requests, [])
        self.assertNotIn("텔레그램", err)

    def test_send_failure_only_warns(self):
        fake = self.serve([500] * 5, echo_path=True)
        self.enable()
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(len(fake.requests), 3)
        warnings = [line for line in err.splitlines() if "텔레그램" in line]
        self.assertEqual(len(warnings), 1, err)
        self.assertTrue(warnings[0].startswith("경고: 텔레그램 알림 전송 실패: HTTP 500"))
        self.assertNotIn(TOKEN, out + err)
        self.assertEqual(state.load(self.rundir, "demo").finish["phase"], "verified")
        self.assertNotIn("텔레그램", self.final_report())

    def test_missing_token_only_warns(self):
        fake = self.serve()
        self.enable(env="TG_CHAT_ID=42\n")
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(fake.requests, [])
        self.assertIn("경고: 텔레그램 알림을 보내지 않았다: .goldstack/local.env에 TG_TOKEN 값이 없다", err)


    def test_unreadable_local_env_only_warns(self):
        fake = self.serve()
        self.enable(env=None)
        (self.repo / ".goldstack/local.env").mkdir()  # 읽으면 IsADirectoryError
        code, out, err = self.go("--only", "01")
        self.assertEqual(code, 0, out + err)
        self.assertEqual(fake.requests, [])
        self.assertIn("경고: .goldstack/local.env: 읽을 수 없다(IsADirectoryError)", err)  # 시작 검사(gs check와 같다)
        self.assertEqual(len([line for line in err.splitlines() if line.startswith("경고: 텔레그램")]), 1, err)
        self.assertIn("경고: 텔레그램 알림 실패: IsADirectoryError", err)


@mock.patch.object(notify, "RETRY_DELAY", 0)
class CommandTest(FakeServerMixin, unittest.TestCase):
    def setUp(self):
        patch = mock.patch.dict(os.environ)
        patch.start()
        self.addCleanup(patch.stop)
        os.environ.pop("GS_ROLE", None)
        import io
        import tempfile
        from pathlib import Path
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.repo = Path(tmp.name)
        (self.repo / ".goldstack").mkdir()
        self.file = self.repo / "msg.txt"
        self.file.write_text("안녕 " + "가" * 4000, encoding="utf-8")
        self.io = io

    def env(self, text):
        (self.repo / ".goldstack/local.env").write_text(text, encoding="utf-8")

    def run_cmd(self, *args):
        out, err = self.io.StringIO(), self.io.StringIO()
        code = notify.command(self.repo, list(args), out, err)
        return code, out.getvalue(), err.getvalue()

    def test_sends_file_truncated_without_printing_secrets(self):
        fake = self.serve()
        self.env(f"TG_TOKEN={TOKEN}\nTG_CHAT_ID=42\n")  # notify.telegram은 기본 꺼짐
        code, out, err = self.run_cmd(str(self.file))
        self.assertEqual(code, 0, err)
        self.assertEqual(len(fake.requests), 1)
        self.assertEqual(fake.requests[0][0], f"/bot{TOKEN}/sendMessage")
        self.assertEqual(fake.requests[0][1]["chat_id"], "42")
        self.assertEqual(fake.texts()[0], notify.truncate(self.file.read_text(encoding="utf-8")))
        self.assertNotIn(TOKEN, out + err)

    def test_cli_check_option_is_accepted(self):
        from gs import cli
        fake = self.serve()
        self.env(f"TG_TOKEN={TOKEN}\nTG_CHAT_ID=42\n")
        with mock.patch("sys.stdout", self.io.StringIO()), mock.patch("sys.stderr", self.io.StringIO()):
            code = cli.main(["--repo", str(self.repo), "notify", "--check"])
        self.assertEqual(code, 0)
        self.assertEqual([r for r in fake.requests if r[0].endswith("sendMessage")], [])

    def test_missing_values(self):
        fake = self.serve()
        self.env("TG_CHAT_ID=42\n")
        code, out, err = self.run_cmd(str(self.file))
        self.assertEqual(code, 1)
        self.assertIn("TG_TOKEN", err)
        self.assertEqual(fake.requests, [])
        code, out, err = self.run_cmd("--check")
        self.assertEqual(code, 1)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertEqual(fake.requests, [])

    def test_api_error_masks_token(self):
        self.serve([404], echo_path=True)
        self.env(f"TG_TOKEN={TOKEN}\nTG_CHAT_ID=42\n")
        code, out, err = self.run_cmd(str(self.file))
        self.assertEqual(code, 1)
        self.assertIn("HTTP 404", err)
        self.assertNotIn(TOKEN, out + err)
        fake = self.serve([401], echo_path=True)
        code, out, err = self.run_cmd("--check")
        self.assertEqual(code, 1)
        self.assertEqual(len(err.strip().splitlines()), 1)
        self.assertNotIn(TOKEN, out + err)

    def test_check_sends_no_message(self):
        fake = self.serve()
        self.env(f"TG_TOKEN={TOKEN}\n")  # 채팅 ID 없이도 토큰은 확인한다
        code, out, err = self.run_cmd("--check")
        self.assertEqual(code, 0, err)
        self.assertEqual([path for path, _ in fake.requests], [f"/bot{TOKEN}/getMe"])
        self.assertNotIn(TOKEN, out + err)

    def test_unreadable_file(self):
        self.serve()
        self.env(f"TG_TOKEN={TOKEN}\nTG_CHAT_ID=42\n")
        code, out, err = self.run_cmd(str(self.repo / "nope.txt"))
        self.assertEqual(code, 1)
        self.assertNotIn(TOKEN, err)


if __name__ == "__main__":
    unittest.main()
