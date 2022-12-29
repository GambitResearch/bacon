import pytest
import datetime

from bacon.utils.dateutils import date_to_quarter


@pytest.mark.parametrize(
    "start_date, quarter_offset, result",
    [
        (datetime.date(2016, 8, 17), 0, datetime.date(2016, 7, 1)),
        (datetime.date(2016, 1, 17), 0, datetime.date(2016, 1, 1)),
        (datetime.date(2016, 1, 17), -1, datetime.date(2015, 10, 1)),
        (datetime.date(2015, 12, 17), 1, datetime.date(2016, 1, 1)),
    ],
)
def test_quarter(start_date, quarter_offset, result):
    assert date_to_quarter(start_date, quarter_offset) == result
