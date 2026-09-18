"""Qt worker bridging discovery + SNMP collection into the GUI thread.

Three phases, matching the spec:
  1. L3 — asynchronous ICMP sweep of the given networks (multi-probe, retried).
  2. L2 — SNMP LLDP walk, seeded by the ping sweep and expanded breadth-first
     through each device's LLDP management addresses (catches devices that
     drop ICMP but speak SNMP/LLDP).
  3. Graph build — every LLDP-advertised neighbour that was never directly
     collected still becomes a placeholder node so links are not dropped.

Emits devices and a final :class:`TopologyGraph` via Qt signals so the UI
thread never blocks.
"""

from __future__ import annotations

import concurrent.futures
import ipaddress
import socket
from collections import deque
from dataclasses import replace
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from balenolib.topology.collector import (
    LldpCollector, SnmpCredentials, SnmpUnavailableError, _guess_role,
)
from balenolib.topology.discovery import PingScanner, expand_networks
from balenolib.topology.engine import TopologyEngine, normalize_port
from balenolib.topology.models import Device, DeviceRole, TopologyGraph

__all__ = ['TopologyDiscoveryWorker']

# Concurrent SNMP collections (the dominant cost is per-device SNMP walks).
MAX_CONCURRENT = 8


class TopologyDiscoveryWorker(QThread):
    """Run discovery + collection in a background thread."""

    progress = pyqtSignal(int, str)      # percent, message
    device_found = pyqtSignal(object)    # Device
    finished = pyqtSignal(object)        # TopologyGraph
    failed = pyqtSignal(str)

    def __init__(self, networks: list[str], credentials: SnmpCredentials,
                 communities: Optional[list[str]] = None, config=None,
                 max_devices: int = 250, layer_name: str = '',
                 mode: str = 'deep', layer_color: str = '', parent=None):
        super().__init__(parent)
        self.networks = networks
        self.credentials = credentials
        self.communities = list(communities) if communities else None
        self.config = config
        self.max_devices = max_devices
        self.layer_name = layer_name
        self.mode = (mode or 'deep').lower()
        self.layer_color = layer_color or ''
        self._stop = False
        self._scanner: Optional[PingScanner] = None

    def stop(self) -> None:
        self._stop = True
        if self._scanner is not None:
            self._scanner.stop()

    def run(self) -> None:
        try:
            targets = expand_networks(self.networks)
            self.progress.emit(3, f"Scanning {len(targets)} hosts (ICMP)…")
            self._scanner = PingScanner()
            reachable = self._scanner.scan_sync(targets)
            if self._stop:
                return

            devices: list[Device] = []

            if self.mode == 'basic':
                self.progress.emit(60, f"Discovered {len(reachable)} active hosts…")
                for ip, rtt in reachable.items():
                    if self._stop:
                        return
                    dev = Device(id=ip, ip=ip, status='up', latency_ms=rtt, role=DeviceRole.HOST)
                    devices.append(dev)
                    self.device_found.emit(dev)
            else:
                worklist = deque(reachable.keys())
                queued = set(worklist)
                seed_total = len(worklist)
                processed = 0

                with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_CONCURRENT) as pool:
                    while worklist:
                        if self._stop:
                            return
                        if len(devices) >= self.max_devices:
                            break
                        wave = []
                        while worklist and len(wave) < MAX_CONCURRENT:
                            wave.append(worklist.popleft())
                        futures = {pool.submit(self._collect_ip, ip): ip for ip in wave}
                        for fut in concurrent.futures.as_completed(futures):
                            if self._stop:
                                return
                            ip = futures[fut]
                            device, community = fut.result()
                            rtt = reachable.get(ip, 0.0)
                            processed += 1
                            frac = processed / max(seed_total, len(worklist) + processed, 1)
                            self.progress.emit(5 + min(70, int(70 * frac)), f"LLDP {ip}…")

                            if device is None:
                                if ip in reachable:
                                    orphan = Device(id=ip, ip=ip, status='up',
                                                    latency_ms=rtt)
                                    devices.append(orphan)
                                    self.device_found.emit(orphan)
                                continue

                            if community and self.config is not None:
                                self.config.set_snmp_ip_community(ip, community)
                            device.latency_ms = rtt
                            if not device.ip:
                                device.ip = ip
                            device.status = 'up'
                            devices.append(device)
                            self.device_found.emit(device)

                            # LLDP-driven expansion: probe neighbour management
                            # addresses even when they never answered ICMP.
                            for n in device.lldp_neighbors:
                                mgmt = n.remote_mgmt_addr
                                if mgmt and mgmt not in queued:
                                    queued.add(mgmt)
                                    worklist.append(mgmt)

                self._add_placeholders(devices)
                self._resolve_missing_ips(devices)

            self.progress.emit(90, "Building topology graph…")
            graph = TopologyEngine().build(devices, seed_networks=self.networks)
            self._assign_layers(graph)
            if self.layer_color:
                name = self.layer_name or (self.networks[0].split('/')[0] if self.networks else 'map')
                graph.layer_colors[name] = self.layer_color
            self.progress.emit(100, f"Done — {len(graph.devices)} nodes, "
                                    f"{len(graph.links)} links")
            self.finished.emit(graph)
        except Exception as exc:
            self.failed.emit(str(exc))

    def _assign_layers(self, graph) -> None:
        """Tag every device with a named layer derived from the discovery name.

        Seeds (hop 1) get ``<name>``; LLDP neighbours at hop N get
        ``<name>-<N>`` (real depth preserved).
        """
        name = self.layer_name or (self.networks[0].split('/')[0] if self.networks else 'map')
        for device in graph.devices.values():
            if device.layer <= 1:
                device.layers.add(name)
            else:
                device.layers.add(f'{name}-{device.layer}')

    # ── SNMP collection with community fallback ──────────────────────────

    def _collect_ip(self, ip: str) -> tuple:
        """Collect one device in a pool thread; returns ``(device, community)``.

        ``community`` is the one that worked (or None).  This is deliberately
        free of config writes so it can run concurrently; the caller records the
        working community on the worker thread.
        """
        creds = self.credentials
        if creds.version in ('1', '2c') and self.communities:
            for community in self._ordered_communities(ip):
                try:
                    device = LldpCollector(replace(creds, community=community)).collect(ip)
                    return device, community
                except Exception:
                    continue
            return None, None
        try:
            return LldpCollector(creds).collect(ip), None
        except Exception:
            return None, None

    def _ordered_communities(self, ip: str) -> list[str]:
        ordered: list[str] = []
        seen: set[str] = set()
        if self.config is not None:
            remembered = self.config.get_snmp_ip_community(ip)
            if remembered and remembered not in seen:
                seen.add(remembered)
                ordered.append(remembered)
        for community in self.communities or []:
            if community and community not in seen:
                seen.add(community)
                ordered.append(community)
        if not ordered:
            ordered.append('public')
        return ordered

    # ── LLDP neighbour placeholders ──────────────────────────────────────

    def _add_placeholders(self, devices: list[Device]) -> None:
        """Create a node for every LLDP neighbour that was never collected.

        Without this, a link pointing at an unprobed neighbour (e.g. a
        switch discovered only through another switch's LLDP table, but which
        refused SNMP) would be silently dropped by the graph builder.
        """
        resolvable: set[str] = set()
        for d in devices:
            if d.id:
                resolvable.add(d.id)
            if d.chassis_id:
                resolvable.add(normalize_port(d.chassis_id))
                resolvable.add(d.chassis_id.lower())
            if d.hostname:
                resolvable.add(d.hostname.lower())
            if d.ip:
                resolvable.add(d.ip)

        added: list[Device] = []
        for d in devices:
            for n in d.lldp_neighbors:
                key = n.remote_chassis_id or n.remote_sys_name or n.remote_mgmt_addr
                if not key:
                    continue
                if (normalize_port(n.remote_chassis_id) in resolvable
                        or (n.remote_chassis_id and n.remote_chassis_id.lower() in resolvable)
                        or (n.remote_sys_name and n.remote_sys_name.lower() in resolvable)
                        or (n.remote_mgmt_addr and n.remote_mgmt_addr in resolvable)):
                    continue

                placeholder = Device(
                    id=key,
                    ip=n.remote_mgmt_addr,
                    hostname=n.remote_sys_name,
                    chassis_id=n.remote_chassis_id,
                    sys_descr=n.remote_sys_desc,
                    role=_guess_role(n.remote_sys_desc) if n.remote_sys_desc else DeviceRole.UNKNOWN,
                    status='unknown',
                )
                # Register so subsequent neighbours matching this one dedupe.
                resolvable.add(placeholder.id)
                if placeholder.chassis_id:
                    resolvable.add(normalize_port(placeholder.chassis_id))
                    resolvable.add(placeholder.chassis_id.lower())
                if placeholder.hostname:
                    resolvable.add(placeholder.hostname.lower())
                if placeholder.ip:
                    resolvable.add(placeholder.ip)

                added.append(placeholder)
                self.device_found.emit(placeholder)

        devices.extend(added)

    # ── IP resolution fallback ────────────────────────────────────────────

    def _resolve_missing_ips(self, devices: list[Device]) -> None:
        """Fill in missing management IPs via DNS, restricted to the seed nets.

        Some devices advertise no LLDP management address (and may drop ICMP),
        so their IP is unknown.  If their hostname resolves to an address inside
        one of the seed networks, assign it — this keeps level-1 devices from
        being misclassified as level 2.
        """
        subnets: list[ipaddress._BaseNetwork] = []
        for entry in self.networks:
            entry = (entry or '').strip()
            if not entry:
                continue
            try:
                subnets.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                try:
                    subnets.append(ipaddress.ip_network(entry + '/32', strict=False))
                except ValueError:
                    continue
        if not subnets:
            return

        for device in devices:
            if device.ip or not device.hostname:
                continue
            resolved = self._dns_resolve(device.hostname)
            if not resolved:
                continue
            try:
                addr = ipaddress.ip_address(resolved)
            except ValueError:
                continue
            if any(addr in subnet for subnet in subnets):
                device.ip = resolved

    @staticmethod
    def _dns_resolve(hostname: str, timeout: float = 2.0) -> str:
        try:
            old = socket.getdefaulttimeout()
            socket.setdefaulttimeout(timeout)
            try:
                return socket.gethostbyname(hostname)
            finally:
                socket.setdefaulttimeout(old)
        except Exception:
            return ''
