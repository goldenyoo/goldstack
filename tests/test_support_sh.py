import subprocess
import sys
import tempfile
import unittest

from support import sh


class ShTest(unittest.TestCase):
    def test_success_returns_stripped_stdout(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(sh(d, sys.executable, "-c", "print('hi')"), "hi")

    def test_failure_message_has_stderr_and_attributes(self):
        code = "import sys; print('out'); sys.stderr.write('boom-' + 'reason'); sys.exit(3)"
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(subprocess.CalledProcessError) as cm:
                sh(d, sys.executable, "-c", code)
        e = cm.exception
        self.assertIn("boom-reason", str(e))
        self.assertEqual(e.returncode, 3)
        self.assertEqual(e.cmd, (sys.executable, "-c", code))
        self.assertEqual(e.stdout, "out\n")
        self.assertEqual(e.stderr, "boom-reason")


if __name__ == "__main__":
    unittest.main()
