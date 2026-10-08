"""Reject malformed event timing rather than displaying fabricated durations."""

import pytest

from ui.frontend.timing import event_timestamp


@pytest.mark.parametrize("timestamp", [None, "bad", "nan", "inf", -1])
def test_invalid_event_timestamps_are_unavailable(timestamp):
    assert event_timestamp(timestamp) is None


def test_numeric_event_timestamp_is_preserved():
    assert event_timestamp("104.2") == 104.2
