#!/usr/bin/env python3
"""Wait a bounded time for an HTTP endpoint and an optional process."""

from __future__ import annotations

import argparse
import os
import sys
import threading
import urllib.error
import urllib.request
from typing import Optional


def process_exists(process_id: Optional[int]) -> bool:
    if process_id is None:
        return True
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--attempts", type=int, default=360)
    parser.add_argument("--interval", type=float, default=5.0)
    parser.add_argument("--request-timeout", type=float, default=3.0)
    parser.add_argument("--process-id", type=int, default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.attempts < 1 or args.interval < 0 or args.request_timeout <= 0:
        raise ValueError("attempts and timeouts must be positive")

    waiter = threading.Event()
    last_error = "endpoint did not respond"
    for attempt in range(1, args.attempts + 1):
        if not process_exists(args.process_id):
            print("server process exited before becoming ready", file=sys.stderr)
            return 1
        try:
            with urllib.request.urlopen(args.url, timeout=args.request_timeout) as response:
                if 200 <= response.status < 300:
                    print(f"[OK] endpoint ready after {attempt} attempt(s): {args.url}")
                    return 0
                last_error = f"HTTP {response.status}"
        except (OSError, urllib.error.URLError) as exc:
            last_error = str(exc)
        if attempt < args.attempts:
            waiter.wait(args.interval)

    print(
        f"endpoint did not become ready after {args.attempts} attempts: {last_error}",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
