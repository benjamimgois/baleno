"""Live performance monitor for the topology map.

Polls each SNMP-reachable device for CPU, memory and interface octet counters
on a fixed interval, computes per-interface and per-device traffic rates
(bits per second) from consecutive samples, and emits the results so the UI
can update tooltips and edge labels.

Polling is concurrent: a single asyncio loop in this thread gathers the
per-device polls with ``asyncio.gather`` (bounded by a semaphore), and each
device's SNMP engine/transport is created once and reused across cycles.
Octet counters are polled every ``interval`` while CPU/memory and
oper-status/speed run on slower cadences, so the traffic labels are never
delayed by unrelated walks.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import replace
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from cetuslib.topology.collector import LldpCollector, SnmpCredentials
from cetuslib.topology.models import Device

__all__ = ['TrafficMonitor']

# Cap concurrent SNMP operations to avoid UDP bursts against large subnets.
MAX_CONCURRENT = 16


class TrafficMonitor(QThread):
    """Poll discovered devices and emit live CPU/memory/traffic rates."""

    # {device_id: {'cpu': float|None, 'memory': float|None,
    #              'in_bps': float, 'out_bps': float,
    #              'if_rates': {ifindex: (in_bps, out_bps)}}}
    updated = pyqtSignal(dict)
    # {device_id: {ifindex: 'up'|'down'|'unknown'}}
    status_updated = pyqtSignal(dict)
    # {device_id: {ifindex: float Mbps}}
    speed_updated = pyqtSignal(dict)

    def __init__(self, devices: list[Device], credentials: SnmpCredentials,
                 interval: float = 5.0, communities: Optional[list[str]] = None,
                 status_interval: float = 60.0, perf_interval: float = 60.0,
                 max_concurrent: int = MAX_CONCURRENT, timeout: float = 1.0,
                 config=None, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.credentials = credentials
        self.interval = interval
        self.status_interval = status_interval
        self.perf_interval = perf_interval
        self.max_concurrent = max_concurrent
        self.timeout = timeout
        self.communities = list(communities) if communities else None
        self.config = config
        self._stop = False
        self._prev: dict[str, tuple[float, dict[int, tuple[int, int]]]] = {}
        self._perf: dict[str, dict] = {}
        self._sessions: dict[str, tuple] = {}
        self._last_status_refresh = 0.0
        self._last_perf_refresh = 0.0

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        await self._open_sessions()
        try:
            while not self._stop:
                start = time.monotonic()
                await self._poll_counters()
                now = time.monotonic()
                if now - self._last_status_refresh >= self.status_interval:
                    await self._refresh_statuses()
                    self._last_status_refresh = now
                if now - self._last_perf_refresh >= self.perf_interval:
                    await self._refresh_perf()
                    self._last_perf_refresh = now
                remaining = self.interval - (time.monotonic() - start)
                await self._sleep(max(0.0, remaining))
        finally:
            self._close_sessions()

    async def _sleep(self, seconds: float) -> None:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline and not self._stop:
            await asyncio.sleep(min(0.1, max(0.0, deadline - time.monotonic())))

    # ── session setup (community resolved once per device) ────────────────

    async def _open_sessions(self) -> None:
        for device in self.devices:
            if self._stop:
                return
            if not device.ip or device.status != 'up':
                continue
            session = await self._setup_session(device)
            if session is not None:
                self._sessions[device.id] = session

    async def _setup_session(self, device: Device):
        creds = self.credentials
        if creds.version in ('1', '2c') and self.communities:
            for community in self._ordered_communities(device.ip):
                collector = LldpCollector(
                    replace(creds, community=community), timeout=self.timeout)
                try:
                    engine, auth, target = await collector.open_session(device.ip)
                except Exception:
                    continue
                if await collector.probe(engine, auth, target):
                    if self.config is not None:
                        self.config.set_snmp_ip_community(device.ip, community)
                    return collector, engine, auth, target
                collector.close_session(engine)
            return None
        try:
            collector = LldpCollector(creds, timeout=self.timeout)
            engine, auth, target = await collector.open_session(device.ip)
            return collector, engine, auth, target
        except Exception:
            return None

    def _close_sessions(self) -> None:
        for collector, engine, auth, target in self._sessions.values():
            collector.close_session(engine)
        self._sessions.clear()

    # ── poll cycles ───────────────────────────────────────────────────────

    async def _poll_counters(self) -> None:
        sem = asyncio.Semaphore(self.max_concurrent)
        ids = list(self._sessions.keys())
        results = await asyncio.gather(
            *[self._poll_counters_one(device_id, sem) for device_id in ids],
            return_exceptions=True,
        )
        snapshot: dict[str, dict] = {}
        for device_id, result in zip(ids, results):
            if isinstance(result, Exception):
                continue
            if result:
                snapshot[device_id] = result
        self._apply(snapshot)

    async def _poll_counters_one(self, device_id: str, sem: asyncio.Semaphore) -> dict:
        collector, engine, auth, target = self._sessions[device_id]
        async with sem:
            return await collector.poll_counters_async(engine, auth, target)

    async def _refresh_perf(self) -> None:
        sem = asyncio.Semaphore(self.max_concurrent)
        ids = list(self._sessions.keys())
        results = await asyncio.gather(
            *[self._poll_perf_one(device_id, sem) for device_id in ids],
            return_exceptions=True,
        )
        for device_id, result in zip(ids, results):
            if isinstance(result, Exception):
                continue
            cpu, mem = result
            self._perf[device_id] = {'cpu': cpu, 'memory': mem}

    async def _poll_perf_one(self, device_id: str, sem: asyncio.Semaphore) -> tuple:
        collector, engine, auth, target = self._sessions[device_id]
        async with sem:
            return await collector.poll_cpu_mem_async(engine, auth, target)

    async def _refresh_statuses(self) -> None:
        sem = asyncio.Semaphore(self.max_concurrent)
        ids = list(self._sessions.keys())
        status_results = await asyncio.gather(
            *[self._poll_status_one(device_id, sem) for device_id in ids],
            return_exceptions=True,
        )
        speed_results = await asyncio.gather(
            *[self._poll_speed_one(device_id, sem) for device_id in ids],
            return_exceptions=True,
        )
        statuses: dict[str, dict] = {}
        speeds: dict[str, dict] = {}
        for device_id, result in zip(ids, status_results):
            if not isinstance(result, Exception) and result:
                statuses[device_id] = result
        for device_id, result in zip(ids, speed_results):
            if not isinstance(result, Exception) and result:
                speeds[device_id] = result
        if statuses:
            self.status_updated.emit(statuses)
        if speeds:
            self.speed_updated.emit(speeds)

    async def _poll_status_one(self, device_id: str, sem: asyncio.Semaphore) -> dict:
        collector, engine, auth, target = self._sessions[device_id]
        async with sem:
            return await collector.poll_status_async(engine, auth, target)

    async def _poll_speed_one(self, device_id: str, sem: asyncio.Semaphore) -> dict:
        collector, engine, auth, target = self._sessions[device_id]
        async with sem:
            return await collector.poll_speed_async(engine, auth, target)

    # ── rate computation ──────────────────────────────────────────────────

    def _apply(self, counters_by_device: dict[str, dict]) -> None:
        now = time.monotonic()
        out: dict[str, dict] = {}
        for device_id, counters in counters_by_device.items():
            prev = self._prev.get(device_id)
            rates: dict[int, tuple[float, float]] = {}
            in_total = 0.0
            out_total = 0.0
            if prev is not None:
                dt = now - prev[0]
                if dt > 0:
                    for idx, (i, o) in counters.items():
                        pi, po = prev[1].get(idx, (0, 0))
                        di = i - pi if i >= pi else i
                        do = o - po if o >= po else o
                        in_bps = di * 8 / dt
                        out_bps = do * 8 / dt
                        rates[idx] = (in_bps, out_bps)
                        in_total += in_bps
                        out_total += out_bps
            self._prev[device_id] = (
                now, {idx: (i, o) for idx, (i, o) in counters.items()})
            perf = self._perf.get(device_id, {})
            out[device_id] = {
                'cpu': perf.get('cpu'),
                'memory': perf.get('memory'),
                'in_bps': in_total,
                'out_bps': out_total,
                'if_rates': rates,
            }
        if out:
            self.updated.emit(out)

    def _ordered_communities(self, ip: str) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        if self.config is not None:
            remembered = self.config.get_snmp_ip_community(ip)
            if remembered and remembered not in seen:
                seen.add(remembered)
                ordered.append(remembered)
        for c in self.communities or []:
            if c and c not in seen:
                seen.add(c)
                ordered.append(c)
        if not ordered:
            ordered.append('public')
        return ordered
