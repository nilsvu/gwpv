import unittest

from gwpv.scene_configuration import parse_as


class TestParseAs(unittest.TestCase):
    def test_path(self):
        self.assertEqual(parse_as.path("/a/b"), "/a/b")
        self.assertEqual(parse_as.path("/a/b", relative_to="/c"), "/a/b")
        self.assertEqual(parse_as.path("a/b", relative_to="/c"), "/c/a/b")
        self.assertEqual(parse_as.path("../a/b", relative_to="/c"), "/a/b")


if __name__ == "__main__":
    unittest.main()
