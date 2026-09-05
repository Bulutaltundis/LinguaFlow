from collections import defaultdict, deque
from time import monotonic

_hits = defaultdict(deque)

def allowed(key: str, limit: int, window: int) -> bool:
    now = monotonic()
    bucket = _hits[key]
    while bucket and bucket[0] <= now - window:
        bucket.popleft()
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    return True
