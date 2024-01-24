#!/usr/bin/env python

import unittest

from bacon.cubedef import CubeDef, Label
from bacon.errors import DataError


class LabelTestCase(unittest.TestCase):
    def test_eq(self):
        """Labels can be compared between them and to strings."""
        l1 = Label("foo")
        l2 = Label("foo")
        l3 = Label("bar")
        self.assertEqual(l1, l2)
        self.assertNotEqual(l1, l3)
        self.assertEqual(l1, "foo")
        self.assertNotEqual(l1, "bar")
        self.assertEqual(l3, "bar")

    def test_hash(self):
        """Labels can be hashed consistently with their names."""
        l1 = Label("foo")
        l2 = Label("foo")
        l3 = Label("bar")
        self.assertEqual(hash(l1), hash(l2))
        self.assertNotEqual(hash(l1), hash(l3))
        self.assertEqual(hash(l1), hash("foo"))
        self.assertNotEqual(hash(l1), hash("bar"))
        self.assertEqual(hash(l3), hash("bar"))


class CubeDefTestCase(unittest.TestCase):
    def test_labels_must_be_labels(self):
        cd = CubeDef()
        self.assertRaises(TypeError, cd.add_label, "year")

    def test_get_label(self):
        cd = CubeDef()
        cd.add_label(Label("year"))
        cd.add_measure(Label("num"))
        self.assertEqual("year", cd.get_label("year"))
        self.assertRaises(DataError, cd.get_label, "num")
        self.assertRaises(DataError, cd.get_label, "missing")

    def test_labels(self):
        cd = CubeDef()
        cd.add_label(Label("year", dimension="time"))
        cd.add_label(Label("month", child_of="year"))
        cd.add_label(Label("foo", dimension="other"))
        cd.add_measure(Label("num"))
        self.assertEqual(set(cd.get_labels()), set(["foo", "month", "year"]))

    def test_measures_must_be_labels(self):
        cd = CubeDef()
        self.assertRaises(TypeError, cd.add_measure, "num")
        cd.add_measure(Label("year"))

    def test_get_measure(self):
        cd = CubeDef()
        cd.add_label(Label("year"))
        cd.add_measure(Label("num"))
        self.assertEqual(
            "year",
            cd.get_measure("year"),
            "It should be possible to use labels as measures",
        )
        self.assertEqual("num", cd.get_measure("num"))
        self.assertRaises(DataError, cd.get_measure, "missing")

    def test_build_hierarchy(self):
        cd = CubeDef()
        cd.add_label(Label("year"))
        cd.add_label(Label("month"))
        cd.add_label(Label("foo"))
        cd.add_measure(Label("num"))
        cd.add_hierarchy("year", "month")
        self.assertEqual(set(cd.get_connected("year")), set(["month", "year"]))
        self.assertEqual(set(cd.get_connected("month")), set(["month", "year"]))

    def test_labels_with_hierarchy(self):
        cd = CubeDef()
        cd.add_label(Label("year", dimension="time"))
        cd.add_label(Label("month", child_of="year"))
        cd.add_label(Label("foo", dimension="other"))
        cd.add_measure(Label("num"))
        self.assert_(isinstance(next(iter(cd.get_connected("month"))), Label))
        self.assertEqual(set(cd.get_connected("year")), set(["month", "year"]))
        self.assertEqual(set(cd.get_connected("month")), set(["month", "year"]))

    def test_ancestors(self):
        cd = CubeDef()
        cd.add_label(Label("year", dimension="time"))
        cd.add_label(Label("month", child_of="year"))
        cd.add_label(Label("week", child_of="year"))
        cd.add_label(Label("day", child_of="month"))
        cd.add_hierarchy("week", "day")
        self.assert_(isinstance(next(iter(cd.get_ancestors("day"))), Label))
        self.assertEqual(set(cd.get_ancestors("year")), set())
        self.assertEqual(set(cd.get_ancestors("month")), set(["year"]))
        self.assertEqual(set(cd.get_ancestors("week")), set(["year"]))
        self.assertEqual(set(cd.get_ancestors("day")), set(["year", "month", "week"]))

    def test_descendants(self):
        cd = CubeDef()
        cd.add_label(Label("year", dimension="time"))
        cd.add_label(Label("month", child_of="year"))
        cd.add_label(Label("day", child_of="month"))
        cd.add_label(Label("week", child_of="year"))
        cd.add_label(Label("day", child_of="month"))
        cd.add_hierarchy("week", "day")
        self.assert_(isinstance(next(iter(cd.get_descendants("year"))), Label))
        self.assertEqual(set(cd.get_descendants("year")), set(["month", "week", "day"]))
        self.assertEqual(set(cd.get_descendants("month")), set(["day"]))
        self.assertEqual(set(cd.get_descendants("month")), set(["day"]))
        self.assertEqual(set(cd.get_descendants("day")), set([]))


def test_suite():
    return unittest.TestLoader().loadTestsFromName(__name__)


if __name__ == "__main__":
    unittest.main()
