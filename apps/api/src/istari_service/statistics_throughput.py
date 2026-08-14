"""Time-zone-aware throughput bucketing for operational statistics."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, date, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

from istari_service.schemas.statistics import DailyThroughput
from istari_service.statistics_records import StatisticsFact

ThroughputResolution = Literal["DAILY", "WEEKLY", "MONTHLY"]


def throughput_rows(
    facts: tuple[StatisticsFact, ...],
    from_date: date,
    to_date: date,
    time_zone: ZoneInfo,
    resolution: ThroughputResolution,
) -> list[DailyThroughput]:
    received = Counter(
        _throughput_bucket(local_date(fact.received_at, time_zone), resolution)
        for fact in facts
    )
    completed = Counter(
        _throughput_bucket(local_date(fact.completed_at, time_zone), resolution)
        for fact in facts
        if fact.completed_at is not None
    )
    first = _throughput_bucket(from_date, resolution)
    last = _throughput_bucket(to_date, resolution)
    buckets: list[date] = []
    current = first
    while current <= last:
        buckets.append(current)
        current = _next_throughput_bucket(current, resolution)
    return [
        DailyThroughput(
            date=bucket,
            received=received[bucket],
            completed=completed[bucket],
        )
        for bucket in buckets
    ]


def throughput_resolution(from_date: date, to_date: date) -> ThroughputResolution:
    days = (to_date - from_date).days + 1
    return "DAILY" if days <= 31 else "WEEKLY" if days <= 120 else "MONTHLY"


def local_date(value: datetime, time_zone: ZoneInfo) -> date:
    aware = value if value.tzinfo else value.replace(tzinfo=UTC)
    return aware.astimezone(time_zone).date()


def _throughput_bucket(value: date, resolution: ThroughputResolution) -> date:
    if resolution == "WEEKLY":
        return value - timedelta(days=value.weekday())
    if resolution == "MONTHLY":
        return value.replace(day=1)
    return value


def _next_throughput_bucket(value: date, resolution: ThroughputResolution) -> date:
    if resolution == "WEEKLY":
        return value + timedelta(days=7)
    if resolution == "MONTHLY":
        return (value.replace(day=28) + timedelta(days=4)).replace(day=1)
    return value + timedelta(days=1)
