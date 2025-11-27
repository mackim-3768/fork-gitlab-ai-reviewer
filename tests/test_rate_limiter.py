import threading
import time

import pytest

from src.rate_limiter import FixedIntervalRateLimiter


def test_fixed_interval_rate_limiter_rejects_non_positive_values() -> None:
    with pytest.raises(ValueError):
        FixedIntervalRateLimiter(0)

    with pytest.raises(ValueError):
        FixedIntervalRateLimiter(-1)


def test_fixed_interval_rate_limiter_enforces_minimum_interval_sequential_calls() -> (
    None
):
    # 300 requests/minute -> 0.2초 간격
    limiter = FixedIntervalRateLimiter(300)

    timestamps = []
    for _ in range(4):
        limiter.acquire()
        timestamps.append(time.time())

    # 첫 호출은 즉시 반환될 수 있으므로 두 번째 호출부터 간격을 체크한다.
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]

    # 타이밍 오차를 고려해 약간의 여유를 둔다 (0.18초 이상).
    for interval in intervals:
        assert interval >= 0.18


def test_fixed_interval_rate_limiter_enforces_interval_with_multiple_threads() -> None:
    # 300 requests/minute -> 0.2초 간격
    limiter = FixedIntervalRateLimiter(300)

    timestamps = []
    lock = threading.Lock()

    def worker() -> None:
        limiter.acquire()
        with lock:
            timestamps.append(time.time())

    threads = [threading.Thread(target=worker) for _ in range(4)]

    start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # 모든 스레드가 완료되었는지 확인
    assert len(timestamps) == 4

    timestamps.sort()
    intervals = [b - a for a, b in zip(timestamps, timestamps[1:])]

    # 전체 테스트 시간이 너무 길어지지 않는지 sanity check (대략 0.6~1초 수준)
    total_duration = max(timestamps) - start
    assert total_duration < 2.0

    # 스레드가 동시에 acquire를 호출해도 최소 간격이 유지되는지 확인 (0.18초 이상).
    for interval in intervals:
        assert interval >= 0.18
