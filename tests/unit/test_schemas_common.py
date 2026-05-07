"""Tests for src.schemas.common (CASEBaseSchema serializers)."""

from datetime import date, datetime, timedelta, timezone

from src.schemas.common import CASEBaseSchema


class _DummySchema(CASEBaseSchema):
    last_change_date_time: datetime | None = None
    status_start_date: date | None = None
    status_end_date: date | None = None


class TestSerializeDatetime:
    def test_naive_datetime_treated_as_utc(self):
        obj = _DummySchema(last_change_date_time=datetime(2025, 10, 8, 12, 0, 0))
        assert obj.model_dump()["last_change_date_time"] == "2025-10-08T12:00:00Z"

    def test_utc_aware_datetime(self):
        obj = _DummySchema(last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=timezone.utc))
        assert obj.model_dump()["last_change_date_time"] == "2025-10-08T12:00:00Z"

    def test_non_utc_aware_datetime_converted_to_utc(self):
        # JST (+09:00) noon → 03:00 UTC
        jst = timezone(timedelta(hours=9))
        obj = _DummySchema(last_change_date_time=datetime(2025, 10, 8, 12, 0, 0, tzinfo=jst))
        assert obj.model_dump()["last_change_date_time"] == "2025-10-08T03:00:00Z"

    def test_negative_offset_aware_datetime_converted_to_utc(self):
        # PST (-08:00) 20:00 → next day 04:00 UTC
        pst = timezone(timedelta(hours=-8))
        obj = _DummySchema(last_change_date_time=datetime(2025, 10, 8, 20, 0, 0, tzinfo=pst))
        assert obj.model_dump()["last_change_date_time"] == "2025-10-09T04:00:00Z"

    def test_none_returns_none(self):
        obj = _DummySchema(last_change_date_time=None)
        assert obj.model_dump()["last_change_date_time"] is None


class TestSerializeDate:
    def test_status_start_date(self):
        obj = _DummySchema(status_start_date=date(2025, 10, 8))
        assert obj.model_dump()["status_start_date"] == "2025-10-08"

    def test_none_returns_none(self):
        obj = _DummySchema(status_start_date=None)
        assert obj.model_dump()["status_start_date"] is None
