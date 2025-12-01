from __future__ import annotations


def format_seconds(seconds: float) -> str:
    """seconds를 사람이 읽기 쉬운 문자열로 변환한다.

    - 0초 미만: "0ms"
    - 1초 미만: "{millis}ms"
    - 60초 미만: "{seconds:.2f}s"
    - 60초 이상 1시간 미만: "{m}m {s}s"
    - 1시간 이상: "{h}h {m}m {s}s"
    """

    if seconds < 0:
        return "0ms"

    if seconds < 1:
        millis = int(seconds * 1000)
        return f"{millis}ms"

    if seconds < 60:
        return f"{seconds:.2f}s"

    total_seconds = int(seconds)
    minutes, seconds = divmod(total_seconds, 60)
    if minutes < 60:
        return f"{minutes}m {seconds}s"

    hours, minutes = divmod(minutes, 60)
    return f"{hours}h {minutes}m {seconds}s"
