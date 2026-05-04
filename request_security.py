from __future__ import annotations

import threading
import time
from collections import defaultdict, deque


_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = defaultdict(deque)


def get_request_client_ip(request) -> str:
    forwarded_for = (request.headers.get('X-Forwarded-For') or '').strip()
    if forwarded_for:
        return forwarded_for.split(',')[0].strip()

    real_ip = (request.headers.get('X-Real-IP') or '').strip()
    if real_ip:
        return real_ip

    return str(request.remote_addr or '').strip() or 'unknown'


def consume_rate_limit(scope: str, key: str, limit: int, window_seconds: int) -> dict[str, int | bool]:
    safe_scope = str(scope or 'default').strip() or 'default'
    safe_key = str(key or 'anonymous').strip() or 'anonymous'
    limit = max(int(limit or 1), 1)
    window_seconds = max(int(window_seconds or 1), 1)
    now = time.time()
    bucket_id = f'{safe_scope}:{safe_key}'

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS[bucket_id]
        cutoff = now - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= limit:
            retry_after = max(1, int(bucket[0] + window_seconds - now))
            return {
                'allowed': False,
                'retry_after': retry_after,
                'remaining': 0,
                'limit': limit,
                'window_seconds': window_seconds,
            }

        bucket.append(now)
        remaining = max(0, limit - len(bucket))
        return {
            'allowed': True,
            'retry_after': 0,
            'remaining': remaining,
            'limit': limit,
            'window_seconds': window_seconds,
        }


def build_compat_csp(*, include_upgrade_insecure_requests: bool = False) -> str:
    directives = [
        "default-src 'self' https: data: blob:",
        "base-uri 'self'",
        "object-src 'none'",
        "frame-ancestors 'self'",
        "form-action 'self'",
        "img-src 'self' data: blob: https:",
        "font-src 'self' data: https:",
        "style-src 'self' 'unsafe-inline' https:",
        "script-src 'self' 'unsafe-inline' https:",
        "connect-src 'self' https:",
        "media-src 'self' data: blob: https:",
        "frame-src 'self' https:",
    ]

    if include_upgrade_insecure_requests:
        directives.append('upgrade-insecure-requests')

    return '; '.join(directives)