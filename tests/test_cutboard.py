#!/usr/bin/env python

import unittest
from collections import namedtuple
from datetime import date

from bacon.cubedef import CubeDef, Label, Measure
from bacon.cubequery import CubeQuery
from bacon.cutting import CuttingBoard


class CubeDefTestCase(unittest.TestCase):
    def get_data_1(self):
        Sell = namedtuple("Sell", "date item place number")
        return [
            Sell(date(2010, 1, 1), "apples", "italy", 100),
            Sell(date(2010, 1, 1), "pears", "italy", 101),
            Sell(date(2010, 1, 1), "apples", "england", 80),
            Sell(date(2010, 2, 1), "apples", "italy", 50),
        ]

    def get_cubedef_1(self):
        cd = CubeDef()
        cd.add_label(Label("year", lambda r: r.date.year))
        cd.add_label(Label("month", lambda r: r.date.month))
        cd.add_label(Label("date"))
        cd.add_hierarchy("year", "month")
        cd.add_hierarchy("month", "date")

        cd.add_label(Label("item"))
        cd.add_label(Label("place"))

        cd.add_measure(Label("number"))
        cd.add_measure(Measure("twice", lambda r: 2 * r.number))

        return cd

    def test_slice_access(self):
        cd = self.get_cubedef_1()
        cb = CuttingBoard(cd, self.get_data_1())
        cq = CubeQuery().row("month").col("item").value("number")

        slice = cb.slice(cq)
        self.assertEqual(180, slice[1]["apples"])
        self.assertEqual(101, slice[1]["pears"])
        self.assertEqual(50, slice[2]["apples"])

        slice = cb.slice(cq, flat=False)
        self.assertEqual(
            (180,),
            slice[1,]["apples",],
        )
        self.assertEqual(
            (101,),
            slice[1,]["pears",],
        )
        self.assertEqual(
            (50,),
            slice[2,]["apples",],
        )
        self.assertEqual(
            50,
            slice[2,]["apples",].number,
            "not a namedtuple",
        )

    def test_1d_slice_access(self):
        cd = self.get_cubedef_1()
        cb = CuttingBoard(cd, self.get_data_1())
        cq = CubeQuery().row("month").value("number")

        slice = cb.slice(cq)
        self.assertEqual(281, slice[1])
        self.assertEqual(50, slice[2])

        slice = cb.slice(cq, flat=False)
        self.assertEqual(
            (281,),
            slice[1,],
        )
        self.assertEqual(
            (50,),
            slice[2,],
        )
        self.assertEqual(
            50,
            slice[2,].number,
            "not a namedtuple",
        )

    def test_multirow_slice(self):
        cd = self.get_cubedef_1()
        cb = CuttingBoard(cd, self.get_data_1())
        cq = CubeQuery().row("month").row("place").col("item").value("number")

        slice = cb.slice(cq)
        self.assertEqual(100, slice[1, "italy"]["apples"])
        self.assertEqual(50, slice[2, "italy"]["apples"])

        slice = cb.slice(cq, flat=False)
        self.assertEqual(
            100,
            slice[1, "italy"]["apples",].number,
        )
        self.assertEqual(
            50,
            slice[2, "italy"]["apples",].number,
        )

    def test_slice_iteration(self):
        cd = self.get_cubedef_1()
        cb = CuttingBoard(cd, self.get_data_1())
        cq = CubeQuery().row("date").col("item").value("number")
        slice = cb.slice(cq)

        # simulate how i would use this object to build a response
        self.assertEqual(list(slice.value_labels()), ["number"])
        self.assertEqual(list(slice.col_labels()), ["apples", "pears"])

        data = list(slice.rows())
        self.assertEqual([180, 101], list(data[0]))
        self.assertEqual([50, None], list(data[1]))

        data = list(slice.rows_with_label())
        self.assertEqual(date(2010, 1, 1), data[0][0])
        self.assertEqual([180, 101], list(data[0][1]))
        self.assertEqual(date(2010, 2, 1), data[1][0])
        self.assertEqual([50, None], list(data[1][1]))

        # on the other side, e.g. for plotting:
        data = list(slice.row_labels())
        self.assertEqual(data, [date(2010, 1, 1), date(2010, 2, 1)])

        data = list(slice.cols_with_label())
        self.assertEqual("apples", data[0][0])
        self.assertEqual([180, 50], list(data[0][1]))
        self.assertEqual("pears", data[1][0])
        self.assertEqual([101, None], list(data[1][1]))

    def test_slice_iteration_nonflat(self):
        cd = self.get_cubedef_1()
        cb = CuttingBoard(cd, self.get_data_1())
        cq = CubeQuery().row("date").col("item").value("number")
        slice = cb.slice(cq, flat=False)

        # simulate how i would use this object to build a response
        self.assertEqual(list(slice.value_labels()), ["number"])
        self.assertEqual(list(slice.col_labels()), [("apples",), ("pears",)])

        data = list(slice.rows())
        self.assertEqual([(180,), (101,)], list(data[0]))
        self.assertEqual([(50,), None], list(data[1]))

        data = list(slice.rows_with_label())
        for i, (l, d) in enumerate(data):  # consolidate iterators
            data[i] = l, list(d)

        self.assertEqual((date(2010, 1, 1),), data[0][0])
        self.assertEqual([(180,), (101,)], data[0][1])
        self.assertEqual((date(2010, 2, 1),), data[1][0])
        self.assertEqual([(50,), None], data[1][1])
        self.assertEqual(50, data[1][1][0].number, "not a namedtuple")

        # on the other side, e.g. for plotting:
        data = list(slice.row_labels())
        self.assertEqual(data, [(date(2010, 1, 1),), (date(2010, 2, 1),)])

        data = list(slice.cols_with_label())
        for i, (l, d) in enumerate(data):  # consolidate iterators
            data[i] = l, list(d)

        self.assertEqual(("apples",), data[0][0])
        self.assertEqual([(180,), (50,)], list(data[0][1]))
        self.assertEqual(("pears",), data[1][0])
        self.assertEqual([(101,), None], list(data[1][1]))
        self.assertEqual(101, data[1][1][0].number, "not a namedtuple")

    def test_series(self):
        cd = self.get_cubedef_1()
        cb = CuttingBoard(cd, self.get_data_1())

        cq = CubeQuery().row("date").value("number")
        slice = cb.slice(cq)
        series = list(slice.series())
        self.assertEqual(series, [281, 50])
        labels = list(slice.series_labels())
        self.assertEqual(labels, [date(2010, 1, 1), date(2010, 2, 1)])

        cq = CubeQuery().row("date").value("number")
        slice = cb.slice(cq, flat=False)
        series = list(slice.series())
        self.assertEqual(series, [(281,), (50,)])
        self.assertEqual(series[0].number, 281)
        labels = list(slice.series_labels())
        self.assertEqual(labels, [(date(2010, 1, 1),), (date(2010, 2, 1),)])

        cq = CubeQuery().row("date").value("number").value("twice")
        slice = cb.slice(cq)
        series = list(slice.series())
        self.assertEqual(series, [(281, 562), (50, 100)])
        self.assertEqual(series[0].number, 281)
        self.assertEqual(series[1].twice, 100)
        labels = list(slice.series_labels())
        self.assertEqual(labels, [date(2010, 1, 1), date(2010, 2, 1)])
