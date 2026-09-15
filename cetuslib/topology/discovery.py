"""Layer 3 discovery — asynchronous ICMP reachability scan.

The rest of the project uses ``subprocess.run(['ping', ...])`` from a
``QThread`` with a ``ThreadPoolExecutor``.  Here we provide a pure-``asyncio``
scanner that is drop-in usable from the topology engine or any ``QThread``,
avoiding a thread per host while still giving high concurrency.

No Qt imports here — keep this layer testable without a display.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import platform
import re
import threading
import time
from typing import Iterable, Optional

__all__ = ['PingScanner', 'expand_networks']

# 'time=' (EN), 'tempo=' (PT), 'tiempo=' (ES), 'zeit=' (DE), 'temps=' (FR).
_RTT_RE = re.compile(r'(?:time|tempo|tiempo|zeit|temps)[=<>]([0-9.]+)\s*ms')

# Force an English/neutral locale for the ping subprocess so its output (and
# the RTT values above) are parseable regardless of the user's LANG.
_PING_ENV = {**os.environ, 'LC_ALL': 'C', 'LANG': 'C'}


def expand_networks(networks: Iterable[str]) -> list[str]:
    """Expand a list of CIDR blocks / IPs into a flat list of host IPs."""
    hosts: list[str] = []
    seen: set[str] = set()
    for entry in networks:
        entry = entry.strip()
        if not entry:
            continue
        try:
            net = ipaddress.ip_network(entry, strict=False)
        except ValueError:
            # bare IP or hostname
            if entry not in seen:
                seen.add(entry)
                hosts.append(entry)
            continue
        for host in net.hosts():
            ip = str(host)
            if ip not in seen:
                seen.add(ip)
                hosts.append(ip)
    return hosts


class PingScanner:
    """Fast asynchronous ICMP scanner over a set of targets.

    Uses the system ``ping`` binary (mirrors the rest of Cetus) but runs many
    probes concurrently through ``asyncio.create_subprocess_exec``.  To avoid
    false negatives from ARP warm-up or a single lost probe, each host is
    probed ``count`` times per attempt, and hosts that never answer are retried
    ``retries`` additional times.

    The measured RTT is the mean of the ``time=`` values reported by ``ping``
    (falling back to elapsed/count when the output cannot be parsed).
    """

    def __init__(self, concurrency: int = 100, timeout: float = 1.0,
                 count: int = 2, retries: int = 1):
        self.concurrency = concurrency
        self.timeout = timeout
        self.count = max(1, int(count))
        self.retries = max(0, int(retries))
        self._stop_event = threading.Event()

    def stop(self) -> None:
        """Signal an in-flight scan to abort (cooperative cancellation)."""
        self._stop_event.set()

    async def _ping_one(self, ip: str, semaphore: asyncio.Semaphore) -> Optional[float]:
        if self._stop_event.is_set():
            return None
        async with semaphore:
            if self._stop_event.is_set():
                return None
            count_flag = '-n' if platform.system() == 'Windows' else '-c'
            wait_flag = '-w' if platform.system() == 'Windows' else '-W'
            cmd = ['ping', count_flag, str(self.count), wait_flag,
                   str(int(self.timeout)), ip]
            try:
                start = time.perf_counter()
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.DEVNULL,
                    env=_PING_ENV,
                )
                out, _ = await proc.communicate()
                rc = proc.returncode
            except (OSError, asyncio.TimeoutError, asyncio.CancelledError):
                return None
            if rc != 0:
                return None
            rtts = _RTT_RE.findall(out.decode('utf-8', 'replace') if out else '')
            if rtts:
                return round(sum(float(x) for x in rtts) / len(rtts), 1)
            return round((time.perf_counter() - start) * 1000.0 / self.count, 1)

    async def scan(self, targets: list[str]) -> dict[str, float]:
        """Return ``{ip: rtt_ms}`` for every host that answered.

        Cooperatively cancellable: :meth:`stop` aborts the remaining probes and
        returns the results collected so far.
        """
        self._stop_event.clear()
        remaining = list(targets)
        results: dict[str, float] = {}
        for _ in range(self.retries + 1):
            if not remaining or self._stop_event.is_set():
                break
            batch = await self._scan_once(remaining)
            results.update(batch)
            remaining = [ip for ip in remaining if ip not in batch]
        return results

    async def _scan_once(self, targets: list[str]) -> dict[str, float]:
        semaphore = asyncio.Semaphore(self.concurrency)
        tasks = {asyncio.ensure_future(self._ping_one(ip, semaphore)): ip
                 for ip in targets}
        pending = set(tasks)
        results: dict[str, float] = {}

        while pending:
            if self._stop_event.is_set():
                for task in pending:
                    task.cancel()
                break
            done, pending = await asyncio.wait(
                pending, timeout=0.05, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                ip = tasks[task]
                try:
                    rtt = task.result()
                except (asyncio.CancelledError, Exception):
                    continue
                if rtt is not None:
                    results[ip] = rtt
        return results

    def scan_sync(self, targets: list[str]) -> dict[str, float]:
        """Convenience wrapper for use inside a QThread.run()."""
        try:
            return asyncio.run(self.scan(targets))
        except RuntimeError:
            # already inside a running loop (unlikely from a QThread)
            return {}
