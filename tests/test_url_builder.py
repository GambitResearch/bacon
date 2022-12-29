#!/usr/bin/env python

import unittest

from bacon.cubedef import CubeDef, Label
from bacon.cubequery import CubeQuery


class UrlQueryBuilderTestCase(unittest.TestCase):
    def get_test_querydef(self):
        cd = CubeDef()
        cd.add_label(Label("foo"))
        cd.add_label(Label("bar"))
        cd.add_label(Label("baz"))
        cd.add_label(Label("qux"))
        return cd

    def get_test_builder(self):
        from bacon.builders.url import UrlQueryBuilder

        cd = self.get_test_querydef()
        b = UrlQueryBuilder(None, cd)
        return b

    def test_string(self):
        b = self.get_test_builder()
        query = CubeQuery().add_filter("foo", "bar").add_axis("baz")
        self.assertEqual("f:foo:bar/a:baz", b.to_string(query, name="test"))

    def test_string_separators_in_values(self):
        b = self.get_test_builder()
        query = CubeQuery().add_filter("foo", "bar/baz").add_filter("qux", r"q\u:x")
        self.assertEqual(
            r"f:foo:bar\/baz/f:qux:q\\u\:x", b.to_string(query, name="test")
        )

    def test_unicode(self):
        b = self.get_test_builder()
        query = CubeQuery().add_filter("foo", "\u20ac")
        self.assertEqual("f:foo:\u20ac", b.to_string(query, name="test"))

    def test_invert(self):
        b = self.get_test_builder()
        query = (
            CubeQuery().add_filter("foo", "bar", "eq").invert_filter("foo", "bar", "eq")
        )
        self.assertEqual(r"f:foo:ne:bar", b.to_string(query, name="test"))


def test_suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main()
