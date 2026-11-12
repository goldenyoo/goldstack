"""모델 기본값 이력과 doctor 제안·check 요약. 목록을 모르면 제안한다. --write는 test_doctor_write_models가 본다."""
import tomllib
import unittest
from unittest import mock

from gs import config, git
import test_check
import test_doctor
import test_tiers


OLD_TO_NEW = {
    "models.agy": ("gemini-4-argon-high", "gemini-4-carbon-high"),
    "tiers.agy.medium": ("gemini-4-argon-medium", "gemini-4-carbon-medium"),
    "tiers.agy.large": ("gemini-4-argon-high", "gemini-4-carbon-high"),
    "tiers.codex.medium": ("gpt-6.1-sol/medium", "gpt-6-astra/high"),
    "tiers.codex.large": ("gpt-6.1-sol/high", "gpt-6-astra/xhigh"),
}


def old_config(text):
    for old, new in OLD_TO_NEW.values():
        text = text.replace(new, old)
    return text


class HistoryTest(unittest.TestCase):
    setUp = test_tiers.TiersTest.setUp
    load = test_tiers.TiersTest.load

    def test_history_keys_exist_and_exclude_current_defaults(self):
        defaults = tomllib.loads(self.default)
        self.assertEqual(set(config.OLD_DEFAULTS), set(OLD_TO_NEW))
        for key, history in config.OLD_DEFAULTS.items():
            with self.subTest(key=key):
                parts = key.split('.')
                self.assertTrue(parts[0] == 'models' or parts[:2] in
                                [['tiers', family] for family in ('claude', 'codex', 'agy')])
                current = defaults
                for part in parts:
                    current = current[part]
                self.assertNotIn(current, history)
                old, new = OLD_TO_NEW[key]
                self.assertIn(old, history)
                self.assertEqual(current, new)

    def test_old_values_match_by_key_and_effort(self):
        cfg, problems = self.load(old_config(self.default))
        self.assertEqual(problems, [])
        self.assertEqual(config.old_model_defaults(cfg), {k: v[1] for k, v in OLD_TO_NEW.items()})
        # 같은 모델이라도 effort가 다르면 사용자 설정이다. 다른 키의 옛 값도 대상이 아니다.
        text = old_config(self.default).replace('gpt-6.1-sol/medium', 'gpt-6.1-sol/xhigh')
        text = text.replace('gemini-4-argon-medium', 'gemini-4-argon-high')
        cfg, problems = self.load(text)
        self.assertEqual(problems, [])
        expected = {k: v[1] for k, v in OLD_TO_NEW.items()
                    if k not in ('tiers.codex.medium', 'tiers.agy.medium')}
        self.assertEqual(config.old_model_defaults(cfg), expected)

    def test_new_custom_and_absent_tiers_are_not_upgrades(self):
        for text in (self.default, self.default.split('[tiers]')[0] + '[agy]' + self.default.split('[agy]')[1]):
            cfg, problems = self.load(text)
            self.assertEqual(problems, [])
            self.assertEqual(config.old_model_defaults(cfg), {})
        text = old_config(self.default)
        for old, _ in OLD_TO_NEW.values():
            text = text.replace(old, 'custom-model')
        cfg, problems = self.load(text)
        self.assertEqual(problems, [])
        self.assertEqual(config.old_model_defaults(cfg), {})


class DoctorDefaultsTest(unittest.TestCase):
    setUp = test_doctor.DoctorTest.setUp
    command = test_doctor.DoctorTest.command

    def rows(self):
        before = self.path.read_bytes()
        code, out = self.command('doctor')
        self.assertEqual(code, 0, out)
        self.assertEqual(self.path.read_bytes(), before)
        return [line for line in out.splitlines() if line.startswith('모델 기본값  ')]

    def test_old_cells_proposed_with_known_and_unknown_lists(self):
        self.path.write_text(old_config(self.original))
        for known in (True, False):
            with self.subTest(known=known), \
                    mock.patch('gs.models.codex_models', return_value={'gpt-6-astra'} if known else None) as codex, \
                    mock.patch('gs.models.agy_models', return_value={'gemini-4-carbon-high', 'gemini-4-carbon-medium'} if known else None) as agy:
                suffix = '' if known else ' (목록 확인 못 함)'
                self.assertEqual(self.rows(), [f'모델 기본값  {key}가 옛 기본값이다 → {key} = "{new}"{suffix}'
                                               for key, (_, new) in OLD_TO_NEW.items()])
                codex.assert_called_once_with()
                agy.assert_called_once_with(timeout=15)

    def test_absent_new_models_and_empty_lists_do_not_propose(self):
        self.path.write_text(old_config(self.original))
        for names in (set(), {'gpt-6.1-sol', 'gemini-4-argon-high', 'gemini-4-carbon-medium'}):
            with self.subTest(names=names), mock.patch('gs.models.codex_models', return_value=names), \
                    mock.patch('gs.models.agy_models', return_value=names):
                expected = []
                for key, (_, new) in OLD_TO_NEW.items():
                    if new in names:
                        expected.append(f'모델 기본값  {key}가 옛 기본값이다 → {key} = "{new}"')
                    else:
                        expected.append(f'모델 기본값  {key}가 옛 기본값이다; 새 기본값 {new}이 이 머신 {key.split(".")[1]} 목록에 없다')
                self.assertEqual(self.rows(), expected)

    def test_custom_and_current_values_have_no_rows_or_extra_queries(self):
        text = old_config(self.original)
        for old, _ in OLD_TO_NEW.values():
            text = text.replace(old, 'custom-model')
        for text in (self.original, text):
            self.path.write_text(text)
            with mock.patch('gs.models.codex_models') as codex, mock.patch('gs.models.agy_models') as agy:
                self.assertEqual(self.rows(), [])
                codex.assert_not_called()
                agy.assert_not_called()

    def test_non_github_repo_still_proposes_and_writes_models(self):
        git.run(self.repo, 'remote', 'set-url', 'upstream', 'https://gitlab.com/owner/project.git')
        text = old_config(self.original)
        self.path.write_text(text)
        with mock.patch('gs.models.codex_models', return_value=None), mock.patch('gs.models.agy_models', return_value=None):
            code, out = self.command('doctor', '--write')
        self.assertEqual(code, 0, out)
        self.assertIn('모델 기본값  tiers.codex.large가 옛 기본값이다 → tiers.codex.large = "gpt-6-astra/xhigh" (목록 확인 못 함)\n', out)
        self.assertIn('tiers.codex.large: "gpt-6.1-sol/high" → "gpt-6-astra/xhigh" (옛 기본값)\n', out)
        self.assertEqual(self.path.read_text(), self.original)  # GitHub 원격이 아니어도 모델 칸은 쓴다(04)


class CheckDefaultsTest(unittest.TestCase):
    setUp, tearDown = test_check.CheckTest.setUp, test_check.CheckTest.tearDown
    write, run_check = test_check.CheckTest.write, test_check.CheckTest.run_check

    def test_single_count_warning_independent_of_inventory(self):
        self.write('01-a.md', test_check.ticket('01'))
        path = self.repo / config.CONFIG_PATH
        path.write_text(old_config(path.read_text()))
        for names in (None, set(), {'gpt-6-luna', 'gpt-6.1-sol'}):
            with self.subTest(names=names), mock.patch('gs.models.codex_models', return_value=names) as codex, \
                    mock.patch('gs.models.agy_models') as agy:
                code, out, err = self.run_check()
                self.assertEqual(code, 0, out + err)
                self.assertEqual([line for line in err.splitlines() if '옛 모델 기본값' in line],
                                 ['경고: 옛 모델 기본값 5칸(gs doctor로 확인)'])
                codex.assert_called_once_with()  # 기존 없는 모델 검사만 조회한다.
                agy.assert_not_called()
        path.write_text(path.read_text().replace('gemini-4-argon-high', 'custom-model'))
        with mock.patch('gs.models.codex_models', return_value=None):
            self.assertEqual(self.run_check()[2], '경고: 옛 모델 기본값 3칸(gs doctor로 확인)\n')

    def test_current_defaults_have_no_warning(self):
        self.write('01-a.md', test_check.ticket('01'))
        code, out, err = self.run_check()
        self.assertEqual((code, err), (0, ''))
        self.assertIn('오류 0, 경고 0', out)


if __name__ == '__main__':
    unittest.main()
