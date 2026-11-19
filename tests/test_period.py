import datetime as dt

import pytest

from citrine import period


def test_year_month_day_cover_the_whole_period():
    assert period.parse_range("2020", "2021") == (dt.date(2020, 1, 1), dt.date(2021, 12, 31))
    assert period.parse_range("2020-02", "2020-02") == (dt.date(2020, 2, 1), dt.date(2020, 2, 29))
    assert period.parse_range("2020-05-17", None) == (dt.date(2020, 5, 17), None)
    assert period.parse_range() == (None, None)


def test_bad_input_says_what_to_type():
    for bad in ("last week", "2020-13", "20", "2020-02-30"):
        with pytest.raises(ValueError):
            period.parse_range(bad)
    with pytest.raises(ValueError, match="after the end"):
        period.parse_range("2021", "2020")


def test_milliseconds_bracket_the_day():
    d = dt.date(2020, 1, 1)
    assert period.to_ms(d) == 1577836800000 and period.to_ms(d, end=True) == 1577923199999
