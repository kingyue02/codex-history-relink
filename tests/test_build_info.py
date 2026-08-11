import unittest

from codex_history_relink.build_info import build_info


class BuildInfoTests(unittest.TestCase):
    def test_build_info_has_version_and_platform(self):
        info = build_info()
        self.assertTrue(info["version"])
        self.assertTrue(info["python"])
        self.assertTrue(info["platform"])


if __name__ == "__main__":
    unittest.main()
