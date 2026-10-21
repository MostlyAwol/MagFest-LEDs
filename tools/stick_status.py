#!/usr/bin/env python3
"""Query one or more sticks: python tools/stick_status.py pi01 pi02 ..."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
import socket
import sys


def query(host, port, timeout):
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.settimeout(timeout)
            sock.connect((host, port))
            sock.send(b"STATUS")
            data = json.loads(sock.recv(8192))
            if not isinstance(data, dict) or not isinstance(data.get("state"), str):
                raise ValueError("invalid status reply")
            return dict(data, target=host)
    except (OSError, ValueError, TypeError) as error:
        return {"target": host, "state": "unreachable", "last_error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("hosts", nargs="+")
    parser.add_argument("--port", type=int, default=42424)
    parser.add_argument("--timeout", type=float, default=3)
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda host: query(host, args.port, args.timeout), args.hosts))
    for result in results:
        print(json.dumps(result, sort_keys=True))
    return int(any(result["state"] in {"unreachable", "snmp_error", "discovery", "starting", "exited"}
                   for result in results))


if __name__ == "__main__":
    sys.exit(main())
