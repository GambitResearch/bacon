import datetime


def date_to_quarter(start_date, quarter_offset=0):
    # type: (datetime.date, int) -> datetime.date
    nmonths = start_date.year * 12 + start_date.month - 1
    nmonths = (nmonths // 3) * 3
    year, month = divmod(nmonths + quarter_offset * 3, 12)
    return datetime.date(year, month + 1, 1)


def date_to_half(start_date, half_offset=0):
    # type: (datetime.date, int) -> datetime.date
    nmonths = start_date.year * 12 + start_date.month - 1
    nmonths = (nmonths // 6) * 6
    year, month = divmod(nmonths + half_offset * 6, 12)
    return datetime.date(year, month + 1, 1)
