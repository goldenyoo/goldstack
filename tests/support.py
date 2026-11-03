"""임시 레포 시험은 바깥 worker의 push·gh 차단 환경을 물려받지 않는다."""
import os
from unittest import mock


def isolate_git_env(test):
    patch = mock.patch.dict(os.environ)
    patch.start()
    test.addCleanup(patch.stop)
    for name in tuple(os.environ):
        if name in ("GIT_CONFIG_COUNT", "GH_TOKEN") or name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            os.environ.pop(name)
