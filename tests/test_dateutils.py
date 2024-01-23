from unittest import TestCase
import datetime

from bacon.utils.dateutils import date_to_quarter


class TestQuarters(TestCase):
    def _test_quarter(self, start_date, quarter_offset, result):
        self.assertEqual(result, date_to_quarter(start_date, quarter_offset))

    def test_1(self):
        self._test_quarter(datetime.date(2016, 8, 17), 0, datetime.date(2016, 7, 1))

    def test_2(self):
        self._test_quarter(datetime.date(2016, 1, 17), 0, datetime.date(2016, 1, 1))

    def test_3(self):
        self._test_quarter(datetime.date(2016, 1, 17), -1, datetime.date(2015, 10, 1))

    def test_4(self):
        self._test_quarter(datetime.date(2015, 12, 17), 1, datetime.date(2016, 1, 1))
