"""`gs doctor --write`가 옛 기본값인 모델 칸만 바꾸는지와 `gs init`의 머신 목록 폴백(goldstack-v34 04).

가짜 목록: codex는 CODEX_HOME의 models_cache.json, agy는 GS_AGY 스크립트다. None은 목록 모름(캐시 없음·agy 없음)이다.
"""
import io
import json
import os
import re
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from gs import config, doctor
import test_config
import test_doctor
from test_model_defaults import OLD_TO_NEW, old_config


OLD = {"git.merge_method": "merge", **{key: old for key, (old, _) in OLD_TO_NEW.items()}}
NEW = {"git.merge_method": "squash", **{key: new for key, (_, new) in OLD_TO_NEW.items()}}
CODEX_NEW = {"gpt-6-luna", "gpt-6-astra"}
AGY_NEW = {"gemini-3.8-flash-medium", "gemini-4-carbon-medium", "gemini-4-carbon-high"}

# 머리 주석·주석·다른 문자열에 옛 값을 두어 값 자리만 바뀌는지 본다. `<<'키'>>`는 바꾸기 전 literal string이다.
TAIL = '''
[agy]
max_calls_per_run = 3

[timeouts]
review_minutes = 30
judge_minutes = 10
summary_seconds = 60

[notify]
telegram = false
'''
SUBTABLE = '''# 머리 주석: tiers.codex.large = "gpt-6.1-sol/high"
[git]
remote = "upstream"
base = "release/stable"
merge_method = <<git.merge_method>>  # 병합 방식
direct_push = true
wait_checks = false
checks = []

[worktree]
setup = "echo gpt-6.1-sol/high large = 'gpt-6.1-sol/high'"

[models]
judge = "opus"
claude_review = "opus"
agy = <<models.agy>> # agy 주석 "gemini-4-argon-high"
codex = ""
failure_summary = "haiku"

[tiers]
review = "large"
rereview = "medium"

[tiers.claude]
small = "sonnet/medium"
medium = "sonnet/high"
large = "opus/xhigh"

[tiers.codex]
# 주석 안의 가짜 자리가 진짜 값까지 삼키는 경우: large = """
small = "gpt-6-luna/medium"
# medium = "gpt-6.1-sol/medium"
medium = <<'tiers.codex.medium'>>
large   =   <<tiers.codex.large>>   # 큰 티켓 """

[ tiers . "agy" ]
small = "gemini-3.8-flash-medium"
'medium' = <<tiers.agy.medium>>
large = <<'tiers.agy.large'>>
''' + TAIL
DOTTED = '''# 루트 dotted key
models.judge = "opus"
models.claude_review = "opus"
models.agy = <<models.agy>>  # 주석
models.codex = ""
tiers.review = "large"
tiers.codex.small = "gpt-6-luna/medium"
tiers.codex.medium = <<tiers.codex.medium>>
tiers . codex . large = <<tiers.codex.large>> # 공백 둔 dotted
"tiers".agy.small = "gemini-3.8-flash-medium"
tiers.agy.medium = <<'tiers.agy.medium'>>
tiers.agy.large = <<tiers.agy.large>>
git.remote = "upstream"
git.base = "release/stable"
git.merge_method = <<git.merge_method>>
''' + TAIL
INLINE = '''models = { judge = "opus", claude_review = "opus", agy = <<models.agy>>, codex = "" } # 인라인 models

[git]
remote = "upstream"
base = "release/stable"
merge_method = <<git.merge_method>>

[tiers]
review = "large"
codex = { small = "gpt-6-luna/medium", medium = <<tiers.codex.medium>>, large = <<tiers.codex.large>> } # 인라인
agy = {small="gemini-3.8-flash-medium",medium=<<tiers.agy.medium>>,large=<<'tiers.agy.large'>>}
''' + TAIL


def fill(template, values, changed=()):
    """`<<키>>`는 basic string, `<<'키'>>`는 literal string 자리다. changed의 키는 doctor가 쓰는 basic string이다."""
    def sub(match):
        value = values[match["key"]]
        return f"'{value}'" if match["quote"] and match["key"] not in changed else json.dumps(value)
    return re.sub(r"<<(?P<quote>'?)(?P<key>[\w.]+)'?>>", sub, template)


def fake_lists(test, codex, agy):
    """codex·agy 가짜 목록을 이 시험의 환경에 둔다. None은 목록 모름이다."""
    tmp = tempfile.TemporaryDirectory(prefix="gs-test-lists-")
    test.addCleanup(tmp.cleanup)
    root = Path(tmp.name)
    if codex is not None:
        (root / "models_cache.json").write_text(json.dumps({"models": [{"slug": name} for name in sorted(codex)]}))
    fake = root / "agy"
    if agy is not None:
        fake.write_text(f"#!{sys.executable}\nimport sys\nassert sys.argv[1:] == ['models']\n"
                        + "".join(f"print({name + ' 설명'!r})\n" for name in sorted(agy)))
        fake.chmod(0o755)
    os.environ.update(CODEX_HOME=str(root), GS_AGY=str(fake))  # isolate_git_env가 시험 끝에 되돌린다


def changes(out):
    return [line for line in out.splitlines() if re.match(r"(?:git|models|tiers)\.[\w.]+: |건너뜀: ", line)]


def change(key, old, new, reason="옛 기본값"):
    return f"{key}: {json.dumps(old)} → {json.dumps(new)} ({reason})"


GIT_CHANGE = change("git.merge_method", "merge", "squash", "squash만 허용(gs 지원 방식 중)")


class DoctorWriteModelsTest(unittest.TestCase):
    setUp = test_doctor.DoctorTest.setUp
    command = test_doctor.DoctorTest.command
    protect = test_doctor.DoctorTest.protect

    def write(self, *lists, before):
        fake_lists(self, *lists)
        self.path.write_bytes(before.encode())
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 0, out)
        return out

    def test_subtable_dotted_inline_change_only_the_cell_with_git(self):
        layouts = {"하위 표": SUBTABLE, "하위 표 CRLF": SUBTABLE.replace("\n", "\r\n"), "dotted": DOTTED,
                   "인라인 표": INLINE}
        for name, template in layouts.items():
            for lists in ((CODEX_NEW, AGY_NEW), (None, None)):
                with self.subTest(layout=name, known=lists[0] is not None):
                    before = fill(template, OLD)
                    self.path.write_bytes(before.encode())
                    cfg, problems = config.load(self.repo)
                    self.assertEqual(problems, [])
                    self.assertEqual(config.old_model_defaults(cfg), {key: new for key, (_, new) in OLD_TO_NEW.items()})
                    out = self.write(*lists, before=before)
                    self.assertEqual(self.path.read_bytes(), fill(template, NEW, changed=NEW).encode())
                    self.assertEqual(changes(out), [GIT_CHANGE] + [change(key, old, new)
                                                                   for key, (old, new) in OLD_TO_NEW.items()])
                    cfg, problems = config.load(self.repo)
                    self.assertEqual(problems, [])
                    self.assertEqual(config.old_model_defaults(cfg), {})

    def test_human_values_and_absent_new_models_are_kept_unknown_list_changes(self):
        human = {**OLD, "tiers.codex.medium": "gpt-6.1-sol/xhigh", "tiers.agy.medium": "gemini-4-argon-high"}
        before = fill(SUBTABLE, human)
        # codex 목록에 astra가 없다 → codex 칸은 그대로. agy는 Carbon High가 있다 → 옛 값 칸만 바뀐다.
        out = self.write({"gpt-6-luna", "gpt-6.1-sol"}, {"gemini-4-carbon-high"}, before=before)
        changed = {"git.merge_method": "squash", "models.agy": NEW["models.agy"], "tiers.agy.large": NEW["tiers.agy.large"]}
        self.assertEqual(self.path.read_text(), fill(SUBTABLE, {**human, **changed}, changed))
        self.assertEqual(changes(out), [GIT_CHANGE, change("models.agy", *OLD_TO_NEW["models.agy"]),
                                        change("tiers.agy.large", *OLD_TO_NEW["tiers.agy.large"])])
        # 목록을 모르는 codex는 바꾸고, Carbon이 없는 agy 목록은 바꾸지 않는다.
        out = self.write(None, {"gemini-4-argon-high"}, before=before)
        changed = {"git.merge_method": "squash", "tiers.codex.large": NEW["tiers.codex.large"]}
        self.assertEqual(self.path.read_text(), fill(SUBTABLE, {**human, **changed}, changed))
        self.assertEqual(changes(out), [GIT_CHANGE, change("tiers.codex.large", *OLD_TO_NEW["tiers.codex.large"])])

    def test_unfixable_cell_is_skipped_with_reason_and_others_applied(self):
        template = SUBTABLE.replace("large   =   <<tiers.codex.large>>", '"l\\u0061rge" = <<tiers.codex.large>>')
        out = self.write(None, None, before=fill(template, OLD))
        changed = {key: value for key, value in NEW.items() if key != "tiers.codex.large"}
        self.assertEqual(self.path.read_text(), fill(template, {**OLD, **changed}, changed))
        self.assertEqual(changes(out), [GIT_CHANGE] + [change(key, old, new) for key, (old, new) in OLD_TO_NEW.items()
                                                       if key != "tiers.codex.large"]
                         + ["건너뜀: tiers.codex.large의 값을 주석·다른 줄을 보존하며 바꿀 수 없는 TOML 형식"])

    def test_unfixable_git_key_still_writes_nothing(self):
        before = fill(SUBTABLE.replace("merge_method = <<", '"merge_metho\\u0064" = <<'), OLD)
        fake_lists(self, None, None)
        self.path.write_text(before)
        code, out = self.command("doctor", "--write")
        self.assertEqual(code, 1, out)
        self.assertIn("오류: config를 쓸 수 없다: git.merge_method의 값을 주석·다른 줄을 보존하며 바꿀 수 없는 TOML 형식\n", out)
        self.assertEqual(self.path.read_text(), before)
        self.assertEqual(changes(out), [])

    def test_missing_model_key_is_skipped_not_added(self):
        text = fill(SUBTABLE, OLD)
        text = text.replace("[tiers.codex]", "[tiers.other]").replace("large = 'gemini-4-argon-high'\n", "")
        self.path.write_text(text)
        out = io.StringIO()
        doctor._write(self.repo, {key: (old, new, "옛 기본값") for key, (old, new) in OLD_TO_NEW.items()}, out)
        expected = (text.replace('agy = "gemini-4-argon-high"', 'agy = "gemini-4-carbon-high"')
                    .replace("'medium' = \"gemini-4-argon-medium\"", "'medium' = \"gemini-4-carbon-medium\""))
        self.assertEqual(self.path.read_text(), expected)
        self.assertEqual(changes(out.getvalue()), [
            change("models.agy", *OLD_TO_NEW["models.agy"]),
            change("tiers.agy.medium", *OLD_TO_NEW["tiers.agy.medium"]),
            "건너뜀: tiers.agy.large가 config에 없어 더하지 않는다",
            "건너뜀: tiers.codex.medium가 config에 없어 더하지 않는다",
            "건너뜀: tiers.codex.large가 config에 없어 더하지 않는다",
        ])
        with self.assertRaises(LookupError):
            doctor._edit(text, "models.absent", "x")

    def test_missing_git_keys_are_added_with_model_cells(self):
        self.protect()
        text = (test_config.CONFIG.replace('agy = "agy-model"', 'agy = "gemini-4-argon-high"')
                + '[tiers.codex]\nsmall = "gpt-6-luna/medium"\nmedium = "gpt-6.1-sol/medium"\nlarge = "gpt-6.1-sol/high"\n')
        out = self.write(None, None, before=text)
        cfg, problems = config.load(self.repo)
        self.assertEqual(problems, [])
        self.assertEqual(cfg.git, config.GitConfig("upstream", "release/stable", "squash", False, True))
        self.assertEqual((cfg.models.judge, cfg.models.agy), ("judge-model", "gemini-4-carbon-high"))
        self.assertEqual({tier: config.model_setting(cfg, f"tiers.codex.{tier}") for tier in config.TIERS},
                         {"small": "gpt-6-luna/medium", "medium": "gpt-6-astra/high", "large": "gpt-6-astra/xhigh"})
        self.assertEqual(changes(out), [
            change("git.merge_method", "merge", "squash", "squash만 허용(gs 지원 방식 중)"),
            change("git.direct_push", True, False, "release/stable 직접 push 금지"),
            change("git.wait_checks", False, True, "build, test"),
            change("models.agy", *OLD_TO_NEW["models.agy"]),
            change("tiers.codex.medium", *OLD_TO_NEW["tiers.codex.medium"]),
            change("tiers.codex.large", *OLD_TO_NEW["tiers.codex.large"]),
        ])


class InitModelsTest(unittest.TestCase):
    setUp = test_config.InitTest.setUp

    def init(self, codex, agy):
        fake_lists(self, codex, agy)
        (self.repo / config.CONFIG_PATH).unlink(missing_ok=True)
        out = test_config.InitTest.init(self)
        lines = []
        for line in out.split(f"만듦: {config.CONFIG_PATH}\n", 1)[1].splitlines():
            if line.startswith(("만듦: ", "그대로 둠: ")):
                break
            lines.append(line)
        return lines, (self.repo / config.CONFIG_PATH).read_text()

    @property
    def default(self):
        return config.DEFAULT_CONFIG.format(base='"main"')

    def test_new_defaults_in_list_are_kept(self):
        self.assertEqual(self.init(CODEX_NEW, AGY_NEW), ([], self.default))

    def test_unknown_lists_keep_new_defaults(self):
        self.assertEqual(self.init(None, None), ([], self.default))

    def test_history_fallback_per_family(self):
        old_agy = {"gemini-3.8-flash-medium", "gemini-4-argon-medium", "gemini-4-argon-high"}
        lines, text = self.init({"gpt-6-luna", "gpt-6.1-sol"}, old_agy)
        self.assertEqual(text, old_config(self.default))
        self.assertEqual(lines, [
            "tiers.codex.medium: gpt-6-astra/high가 이 머신 codex 목록에 없어 gpt-6.1-sol/medium로 적었다",
            "tiers.codex.large: gpt-6-astra/xhigh가 이 머신 codex 목록에 없어 gpt-6.1-sol/high로 적었다",
            "models.agy: gemini-4-carbon-high가 이 머신 agy 목록에 없어 gemini-4-argon-high로 적었다",
            "tiers.agy.medium: gemini-4-carbon-medium가 이 머신 agy 목록에 없어 gemini-4-argon-medium로 적었다",
            "tiers.agy.large: gemini-4-carbon-high가 이 머신 agy 목록에 없어 gemini-4-argon-high로 적었다",
        ])
        self.assertEqual(config.load(self.repo)[1], [])
        # 목록을 모르는 codex는 새 기본값, agy만 옛 값으로 적는다.
        lines, text = self.init(None, old_agy)
        expected = self.default
        for key in ("models.agy", "tiers.agy.medium", "tiers.agy.large"):
            expected = expected.replace(f'= "{OLD_TO_NEW[key][1]}"', f'= "{OLD_TO_NEW[key][0]}"')
        self.assertEqual(text, expected)
        self.assertEqual(lines, [f"{key}: {OLD_TO_NEW[key][1]}가 이 머신 agy 목록에 없어 {OLD_TO_NEW[key][0]}로 적었다"
                                 for key in ("models.agy", "tiers.agy.medium", "tiers.agy.large")])

    def test_history_is_read_most_recent_first(self):
        history = ("gemini-4-argon-high", "gemini-3-old-high")
        with mock.patch.dict(config.OLD_DEFAULTS, {"tiers.agy.large": history}):
            for names, chosen in (({"gemini-3-old-high", "gemini-4-argon-high"}, "gemini-4-argon-high"),
                                  ({"gemini-3-old-high"}, "gemini-3-old-high")):
                with self.subTest(names=names):
                    lines, text = self.init(None, names | {"gemini-3.8-flash-medium", "gemini-4-carbon-medium"})
                    self.assertIn(f"tiers.agy.large: gemini-4-carbon-high가 이 머신 agy 목록에 없어 {chosen}로 적었다", lines)
                    self.assertEqual(config.load(self.repo)[0].tiers.agy["large"], config.ModelEffort(chosen))

    def test_absent_from_history_and_empty_lists_warn_and_keep_new_defaults(self):
        lines, text = self.init({"gpt-6-luna"}, {"gemini-4-carbon-high"})
        self.assertEqual(text, self.default)
        self.assertEqual(lines, [
            "경고: tiers.codex.medium: gpt-6-astra/high가 이 머신 codex 목록에 없다. 직접 고친다",
            "경고: tiers.codex.large: gpt-6-astra/xhigh가 이 머신 codex 목록에 없다. 직접 고친다",
            "경고: tiers.agy.small: gemini-3.8-flash-medium가 이 머신 agy 목록에 없다. 직접 고친다",
            "경고: tiers.agy.medium: gemini-4-carbon-medium가 이 머신 agy 목록에 없다. 직접 고친다",
        ])
        lines, text = self.init(set(), set())  # models_cache.json이 {"models": []}, agy models 출력이 빈 경우
        self.assertEqual(json.loads((Path(os.environ["CODEX_HOME"]) / "models_cache.json").read_text()), {"models": []})
        self.assertEqual(text, self.default)
        self.assertEqual(lines, [
            "경고: tiers.codex.small: gpt-6-luna/medium가 이 머신 codex 목록에 없다. 직접 고친다",
            "경고: tiers.codex.medium: gpt-6-astra/high가 이 머신 codex 목록에 없다. 직접 고친다",
            "경고: tiers.codex.large: gpt-6-astra/xhigh가 이 머신 codex 목록에 없다. 직접 고친다",
            "경고: models.agy: gemini-4-carbon-high가 이 머신 agy 목록에 없다. 직접 고친다",
            "경고: tiers.agy.small: gemini-3.8-flash-medium가 이 머신 agy 목록에 없다. 직접 고친다",
            "경고: tiers.agy.medium: gemini-4-carbon-medium가 이 머신 agy 목록에 없다. 직접 고친다",
            "경고: tiers.agy.large: gemini-4-carbon-high가 이 머신 agy 목록에 없다. 직접 고친다",
        ])


if __name__ == "__main__":
    unittest.main()
