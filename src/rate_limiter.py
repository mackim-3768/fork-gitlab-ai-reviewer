import threading
import time
import logging


logger = logging.getLogger(__name__)


class FixedIntervalRateLimiter:
    """고정 간격 기반 레이트 리미터.

    max_requests_per_minute 설정에 따라 호출 간 최소 간격을 강제해,
    여러 워커 스레드가 동시에 사용해도 전체적으로 분당 요청 수를 제한한다.
    """

    def __init__(self, max_requests_per_minute: int) -> None:
        if max_requests_per_minute <= 0:
            raise ValueError("max_requests_per_minute must be positive")

        self._interval_seconds = 60.0 / float(max_requests_per_minute)
        self._lock = threading.Lock()
        self._next_available_time = 0.0

    def acquire(self) -> None:
        """다음 요청을 시작해도 되는 시점까지 대기한 후 슬롯을 예약한다."""

        while True:
            with self._lock:
                now = time.time()
                wait = max(0.0, self._next_available_time - now)

                if wait <= 0.0:
                    # 이번 작업이 사용할 슬롯 예약
                    start_time = max(now, self._next_available_time)
                    self._next_available_time = start_time + self._interval_seconds
                    return

            # 잠시 대기 후 다시 시도
            time.sleep(wait)
