#!/usr/bin/env python

import unittest
from math import sqrt

from bacon import accumulators


class AccumulatorsTestCase(unittest.TestCase):
    def test_avg_0(self):
        acc = accumulators.Average()
        self.assertEqual(None, acc.get())

    def test_avg_1(self):
        acc = accumulators.Average()
        acc.add(10, None)
        self.assertEqual(10, acc.get())

    def test_avg_n(self):
        data = [2, 4, 4, 4, 5, 5, 7, 9]
        acc = accumulators.Average()
        for x in data:
            acc.add(x, None)

        self.assertEqual(5.0, acc.get())

    def test_stddev_0(self):
        acc = accumulators.StdDev()
        self.assertEqual(None, acc.get())

    def test_stddev_1(self):
        acc = accumulators.StdDev()
        acc.add(10, None)
        self.assertEqual(None, acc.get())

    def test_stddev_2(self):
        acc = accumulators.StdDev()
        acc.add(10, None)
        acc.add(10, None)
        self.assertEqual(0.0, acc.get())

    def test_stddev_n(self):
        data = [2, 4, 4, 4, 5, 5, 7, 9]
        acc = accumulators.StdDev()
        for x in data:
            acc.add(x, None)

        self.assertAlmostEqual(sqrt(32 / 7.0), acc.get())


if __name__ == "__main__":
    unittest.main()
