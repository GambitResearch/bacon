#!/usr/bin/env python

import unittest

from bacon.utils import strings


class StringsTestCase(unittest.TestCase):
    def test_bsescape(self):
        self.assertEqual(r"foo\:bar/baz", strings.bsescape("foo:bar/baz", ":"))
        self.assertEqual(r"foo\:", strings.bsescape("foo:", ":"))
        self.assertEqual(r"\:foo", strings.bsescape(":foo", ":"))
        self.assertEqual(r"foo\:bar\/baz", strings.bsescape("foo:bar/baz", ":/"))
        self.assertEqual(r"foo\\bar\/baz", strings.bsescape(r"foo\bar/baz", "/"))

    def test_bsunescape(self):
        self.assertEqual("foo/bar", strings.bsunescape("foo\/bar"))
        self.assertEqual(r"foo/bar\baz", strings.bsunescape(r"foo\/bar\\baz"))

    def test_bssplit(self):
        self.assertEqual(["foo", "bar"], strings.bssplit("foo:bar", ":"))
        self.assertEqual(["foo", "bar:baz"], strings.bssplit(r"foo:bar\:baz", ":"))
        self.assertEqual(["foo", r"bar\baz"], strings.bssplit(r"foo:bar\baz", ":"))
        self.assertEqual(["foo", ""], strings.bssplit("foo:", ":"))
        self.assertEqual(["", "foo"], strings.bssplit(":foo", ":"))
        self.assertEqual([""], strings.bssplit("", ":"))


def test_suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main()
