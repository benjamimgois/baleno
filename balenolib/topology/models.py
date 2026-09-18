"""Data models for the Network Topology Mapper.

Plain dataclasses kept free of any Qt / SNMP / networkx dependency so the
discovery, collection and rendering layers stay decoupled and testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class DeviceRole(str, Enum):
    """Coarse device classification used to pick an icon and a layer strategy."""

    ROUTER = 'router'
    SWITCH = 'switch'        # L2/L3 switch
    CORE = 'core'            # core/distribution switch
    ACCESS = 'access'        # access switch
    FIREWALL = 'firewall'
    SERVER = 'server'
    AP = 'ap'                # wireless access point
    CAMERA = 'camera'        # surveillance / IP camera / NVR
    CLOUD = 'cloud'          # WAN / internet / cloud appliance
    CLOUD2 = 'cloud2'        # cloud service variant
    CLOUD3 = 'cloud3'        # cloud service variant
    CLOUD4 = 'cloud4'        # cloud service variant
    INTERNET = 'internet'    # internet / WAN uplink
    HOST = 'host'            # generic endpoint (PC, printer, IP phone...)
    PHONE = 'phone'          # IP phone / VoIP endpoint
    UNKNOWN = 'unknown'


@dataclass
class Interface:
    """A single physical/logical interface of a device (from IF-MIB)."""

    index: int
    name: str = ''
    descr: str = ''
    alias: str = ''
    mac: str = ''
    oper_status: str = 'up'          # 'up' | 'down' | 'unknown'
    speed: str = ''
    speed_mbps: float = 0.0          # link capacity in Mbps (ifHighSpeed)
    in_octets: int = 0               # cumulative received octets (64-bit if HC)
    out_octets: int = 0              # cumulative transmitted octets
    in_rate_bps: float = 0.0         # live rate (computed by the monitor poller)
    out_rate_bps: float = 0.0


@dataclass
class LldpNeighbor:
    """One LLDP remote-system entry, as learned on a local port."""

    local_port_num: int = 0          # lldpRemLocalPortNum (== ifIndex usually)
    local_port_name: str = ''
    remote_index: int = 0            # lldpRemIndex
    remote_chassis_id: str = ''      # lldpRemChassisId (decoded)
    remote_chassis_subtype: str = ''
    remote_port_id: str = ''         # lldpRemPortId (decoded)
    remote_port_subtype: str = ''
    remote_port_desc: str = ''       # lldpRemPortDesc
    remote_sys_name: str = ''        # lldpRemSysName
    remote_sys_desc: str = ''        # lldpRemSysDesc
    remote_mgmt_addr: str = ''       # lldpRemManAddr (IPv4)
    remote_mgmt_addr_oid: str = ''   # lldpRemManAddrOID
    time_mark: int = 0               # lldpRemTimeMark


@dataclass
class Device:
    """A discovered network node (switch/router/server/host/AP)."""

    id: str                          # stable node key: chassis_id or mgmt IP
    ip: str = ''                     # management / discovered IP
    hostname: str = ''
    role: DeviceRole = DeviceRole.UNKNOWN
    vendor: str = ''
    model: str = ''
    sys_descr: str = ''
    chassis_id: str = ''
    chassis_subtype: str = ''
    status: str = 'unknown'          # 'up' | 'down' | 'unknown'
    latency_ms: float = 0.0
    uptime: str = ''
    layer: int = 0                   # 1-based hop level from the seed networks (0 = unassigned)
    cpu_usage: float = -1.0          # percent, -1 = unknown
    memory_usage: float = -1.0       # percent used, -1 = unknown
    in_rate_bps: float = 0.0         # total received rate across interfaces
    out_rate_bps: float = 0.0        # total transmitted rate across interfaces
    interfaces: dict[int, Interface] = field(default_factory=dict)
    lldp_neighbors: list[LldpNeighbor] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)
    layers: set[str] = field(default_factory=set)  # named map layers (visibility groups)

    @property
    def label(self) -> str:
        return self.hostname or self.ip or self.id

    @property
    def up(self) -> bool:
        return self.status in ('up', 'active')

    def to_dict(self) -> dict[str, Any]:
        """Identity fields plus a minimal interface summary (name, oper_status,
        speed) so link state/colour survive a restart.  Ephemeral runtime data
        (octet counters, live rates, CPU/memory, LLDP neighbours) is excluded.
        """
        interfaces: dict[str, dict[str, Any]] = {}
        for idx, iface in self.interfaces.items():
            if iface.name or iface.descr:
                interfaces[str(idx)] = {
                    'name': iface.name,
                    'descr': iface.descr,
                    'alias': iface.alias,
                    'oper_status': iface.oper_status,
                    'speed_mbps': iface.speed_mbps,
                }
        neighbors: list[dict[str, Any]] = []
        for n in self.lldp_neighbors:
            neighbors.append({
                'local_port_num': n.local_port_num,
                'local_port_name': n.local_port_name,
                'remote_index': n.remote_index,
                'remote_chassis_id': n.remote_chassis_id,
                'remote_chassis_subtype': n.remote_chassis_subtype,
                'remote_port_id': n.remote_port_id,
                'remote_port_subtype': n.remote_port_subtype,
                'remote_port_desc': n.remote_port_desc,
                'remote_sys_name': n.remote_sys_name,
                'remote_sys_desc': n.remote_sys_desc,
                'remote_mgmt_addr': n.remote_mgmt_addr,
                'remote_mgmt_addr_oid': n.remote_mgmt_addr_oid,
                'time_mark': n.time_mark,
            })
        return {
            'id': self.id,
            'ip': self.ip,
            'hostname': self.hostname,
            'role': self.role.value,
            'vendor': self.vendor,
            'model': self.model,
            'sys_descr': self.sys_descr,
            'chassis_id': self.chassis_id,
            'status': self.status,
            'uptime': self.uptime,
            'latency_ms': self.latency_ms,
            'layer': self.layer,
            'layers': sorted(self.layers),
            'interfaces': interfaces,
            'lldp_neighbors': neighbors,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'Device':
        try:
            role = DeviceRole(data.get('role', DeviceRole.UNKNOWN.value))
        except ValueError:
            role = DeviceRole.UNKNOWN
        device = cls(
            id=str(data.get('id', '')),
            ip=str(data.get('ip', '') or ''),
            hostname=str(data.get('hostname', '') or ''),
            role=role,
            vendor=str(data.get('vendor', '') or ''),
            model=str(data.get('model', '') or ''),
            sys_descr=str(data.get('sys_descr', '') or ''),
            chassis_id=str(data.get('chassis_id', '') or ''),
            status=str(data.get('status', 'unknown') or 'unknown'),
            uptime=str(data.get('uptime', '') or ''),
            latency_ms=float(data.get('latency_ms', 0.0) or 0.0),
            layer=int(data.get('layer', 0) or 0),
            layers=set(data.get('layers') or []),
        )
        for idx_str, ifdata in (data.get('interfaces') or {}).items():
            try:
                idx = int(idx_str)
            except (ValueError, TypeError):
                continue
            device.interfaces[idx] = Interface(
                index=idx,
                name=str(ifdata.get('name', '')),
                descr=str(ifdata.get('descr', '') or ''),
                alias=str(ifdata.get('alias', '') or ''),
                oper_status=str(ifdata.get('oper_status', 'up') or 'up'),
                speed_mbps=float(ifdata.get('speed_mbps', 0) or 0),
            )
        for ndata in data.get('lldp_neighbors') or []:
            if isinstance(ndata, dict):
                device.lldp_neighbors.append(LldpNeighbor(
                    local_port_num=int(ndata.get('local_port_num', 0) or 0),
                    local_port_name=str(ndata.get('local_port_name', '') or ''),
                    remote_index=int(ndata.get('remote_index', 0) or 0),
                    remote_chassis_id=str(ndata.get('remote_chassis_id', '') or ''),
                    remote_chassis_subtype=str(ndata.get('remote_chassis_subtype', '') or ''),
                    remote_port_id=str(ndata.get('remote_port_id', '') or ''),
                    remote_port_subtype=str(ndata.get('remote_port_subtype', '') or ''),
                    remote_port_desc=str(ndata.get('remote_port_desc', '') or ''),
                    remote_sys_name=str(ndata.get('remote_sys_name', '') or ''),
                    remote_sys_desc=str(ndata.get('remote_sys_desc', '') or ''),
                    remote_mgmt_addr=str(ndata.get('remote_mgmt_addr', '') or ''),
                    remote_mgmt_addr_oid=str(ndata.get('remote_mgmt_addr_oid', '') or ''),
                    time_mark=int(ndata.get('time_mark', 0) or 0),
                ))
        return device


@dataclass
class PortLink:
    """A physical L2 link between two devices, with both endpoint ports."""

    source_id: str
    source_port: str
    target_id: str
    target_port: str
    source_ifindex: int = 0          # ifIndex of the source-side interface (0 = unknown)
    lag: bool = False                # bundled into a LAG (multiple parallel links)
    weight: int = 2
    status: str = 'up'
    override_status: Optional[str] = None   # None=auto | 'up' | 'down'
    override_speed: Optional[float] = None  # None=auto | Mbps
    manual: bool = False             # created manually by the operator

    def key(self) -> tuple:
        """Order-independent key for deduplication."""
        a = (self.source_id, self.source_port)
        b = (self.target_id, self.target_port)
        return tuple(sorted((a, b)))

    def touches(self, device_id: str) -> bool:
        return device_id in (self.source_id, self.target_id)

    @property
    def overridden(self) -> bool:
        """True when any manual override is active."""
        return self.override_status is not None or self.override_speed is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            'source_id': self.source_id,
            'source_port': self.source_port,
            'target_id': self.target_id,
            'target_port': self.target_port,
            'source_ifindex': self.source_ifindex,
            'lag': self.lag,
            'weight': self.weight,
            'status': self.status,
            'override_status': self.override_status,
            'override_speed': self.override_speed,
            'manual': self.manual,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'PortLink':
        return cls(
            source_id=str(data.get('source_id', '')),
            source_port=str(data.get('source_port', '') or ''),
            target_id=str(data.get('target_id', '')),
            target_port=str(data.get('target_port', '') or ''),
            source_ifindex=int(data.get('source_ifindex', 0) or 0),
            lag=bool(data.get('lag', False)),
            weight=int(data.get('weight', 2) or 2),
            status=str(data.get('status', 'up') or 'up'),
            override_status=data.get('override_status') or None,
            override_speed=(float(data.get('override_speed'))
                            if data.get('override_speed') is not None else None),
            manual=bool(data.get('manual', False)),
        )


@dataclass
class TopologyGraph:
    """Container for the resolved topology."""

    devices: dict[str, Device] = field(default_factory=dict)
    links: list[PortLink] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)      # ICMP-only, no LLDP link
    loops: list[list[str]] = field(default_factory=list)  # detected cycles
    lags: list[list[PortLink]] = field(default_factory=list)
    layer_colors: dict[str, str] = field(default_factory=dict)

    def add_device(self, device: Device) -> None:
        self.devices[device.id] = device

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            'devices': {did: dev.to_dict() for did, dev in self.devices.items()},
            'links': [link.to_dict() for link in self.links],
            'layer_colors': dict(self.layer_colors),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> 'TopologyGraph':
        graph = cls()
        graph.layer_colors = dict(data.get('layer_colors') or {})
        for did, ddata in (data.get('devices') or {}).items():
            device = Device.from_dict(ddata)
            if device.id:
                graph.devices[did] = device
        for ldata in data.get('links') or []:
            link = PortLink.from_dict(ldata)
            if link.source_id in graph.devices and link.target_id in graph.devices:
                graph.links.append(link)

        # Reconstruct lldp_neighbors for devices where lldp_neighbors was empty
        # (e.g. legacy maps saved before neighbor persistence was introduced)
        for did, dev in graph.devices.items():
            if not dev.lldp_neighbors:
                seen: set[tuple[str, str, str]] = set()
                for link in graph.links:
                    if link.source_id == did:
                        tgt = graph.devices.get(link.target_id)
                        key = (link.source_port, link.target_id, link.target_port)
                        if key not in seen:
                            seen.add(key)
                            dev.lldp_neighbors.append(LldpNeighbor(
                                local_port_num=link.source_ifindex,
                                local_port_name=link.source_port,
                                remote_chassis_id=tgt.chassis_id if tgt else link.target_id,
                                remote_port_id=link.target_port,
                                remote_sys_name=tgt.hostname or (tgt.label if tgt else link.target_id),
                                remote_mgmt_addr=tgt.ip if tgt else '',
                            ))
                    elif link.target_id == did:
                        src = graph.devices.get(link.source_id)
                        key = (link.target_port, link.source_id, link.source_port)
                        if key not in seen:
                            seen.add(key)
                            dev.lldp_neighbors.append(LldpNeighbor(
                                local_port_name=link.target_port,
                                remote_chassis_id=src.chassis_id if src else link.source_id,
                                remote_port_id=link.source_port,
                                remote_sys_name=src.hostname or (src.label if src else link.source_id),
                                remote_mgmt_addr=src.ip if src else '',
                            ))
        return graph
