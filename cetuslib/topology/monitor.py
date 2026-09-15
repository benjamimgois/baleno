"""Live performance monitor for the topology map.

Polls each SNMP-reachable device for CPU, memory and interface octet counters
on a fixed interval, computes per-interface and per-device traffic rates
(bits per second) from consecutive samples, and emits the results so the UI
can update tooltips and edge labels.
"""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from cetuslib.topology.collector import LldpCollector, SnmpCredentials
from cetuslib.topology.models import Device

__all__ = ['TrafficMonitor']


class TrafficMonitor(QThread):
    """Poll discovered devices and emit live CPU/memory/traffic rates."""

    # {device_id: {'cpu': float|None, 'memory': float|None,
    #              'in_bps': float, 'out_bps': float,
    #              'if_rates': {ifindex: (in_bps, out_bps)}}}
    updated = pyqtSignal(dict)

    def __init__(self, devices: list[Device], credentials: SnmpCredentials,
                 interval: float = 5.0, communities: Optional[list[str]] = None,
                 config=None, parent=None):
        super().__init__(parent)
        self.devices = devices
        self.credentials = credentials
        self.interval = interval
        self.communities = list(communities) if communities else None
        self.config = config
        self._stop = False
        self._prev: dict[str, tuple[float, dict[int, tuple[int, int]]]] = {}

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        while not self._stop:
            start = time.monotonic()
            snapshot: dict[str, dict] = {}
            for device in self.devices:
                if self._stop:
                    return
                if not device.ip or device.status != 'up':
                    continue
                result = self._poll_device(device)
                if result['counters']:
                    snapshot[device.id] = result
            self._apply(snapshot)

            remaining = self.interval - (time.monotonic() - start)
            deadline = time.monotonic() + max(0.0, remaining)
            while time.monotonic() < deadline and not self._stop:
                time.sleep(0.1)

    def _poll_device(self, device: Device) -> dict:
        creds = self.credentials
        if creds.version in ('1', '2c') and self.communities:
            ordered: list[str] = []
            seen: set[str] = set()
            if self.config is not None:
                remembered = self.config.get_snmp_ip_community(device.ip)
                if remembered and remembered not in seen:
                    seen.add(remembered)
                    ordered.append(remembered)
            for c in self.communities:
                if c and c not in seen:
                    seen.add(c)
                    ordered.append(c)
            if not ordered:
                ordered.append('public')
            for community in ordered:
                try:
                    result = LldpCollector(
                        replace(creds, community=community)).poll(device.ip)
                except Exception:
                    continue
                if result['counters']:
                    if self.config is not None:
                        self.config.set_snmp_ip_community(device.ip, community)
                    return result
            return {'cpu': None, 'memory': None, 'counters': {}}
        try:
            return LldpCollector(creds).poll(device.ip)
        except Exception:
            return {'cpu': None, 'memory': None, 'counters': {}}

    def _apply(self, snapshot: dict[str, dict]) -> None:
        now = time.monotonic()
        out: dict[str, dict] = {}
        for device_id, result in snapshot.items():
            counters = result['counters']
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
            out[device_id] = {
                'cpu': result['cpu'],
                'memory': result['memory'],
                'in_bps': in_total,
                'out_bps': out_total,
                'if_rates': rates,
            }
        if out:
            self.updated.emit(out)
