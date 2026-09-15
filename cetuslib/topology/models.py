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
    SERVER = 'server'
    AP = 'ap'                # wireless access point
    HOST = 'host'            # generic endpoint (PC, printer, IP phone...)
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
    interfaces: dict[int, Interface] = field(default_factory=dict)
    lldp_neighbors: list[LldpNeighbor] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def label(self) -> str:
        return self.hostname or self.ip or self.id

    @property
    def up(self) -> bool:
        return self.status in ('up', 'active')


@dataclass
class PortLink:
    """A physical L2 link between two devices, with both endpoint ports."""

    source_id: str
    source_port: str
    target_id: str
    target_port: str
    lag: bool = False                # bundled into a LAG (multiple parallel links)
    weight: int = 1
    status: str = 'up'

    def key(self) -> tuple:
        """Order-independent key for deduplication."""
        a = (self.source_id, self.source_port)
        b = (self.target_id, self.target_port)
        return tuple(sorted((a, b)))

    def touches(self, device_id: str) -> bool:
        return device_id in (self.source_id, self.target_id)


@dataclass
class TopologyGraph:
    """Container for the resolved topology."""

    devices: dict[str, Device] = field(default_factory=dict)
    links: list[PortLink] = field(default_factory=list)
    orphans: list[str] = field(default_factory=list)      # ICMP-only, no LLDP link
    loops: list[list[str]] = field(default_factory=list)  # detected cycles
    lags: list[list[PortLink]] = field(default_factory=list)

    def add_device(self, device: Device) -> None:
        self.devices[device.id] = device

    def get_device(self, device_id: str) -> Optional[Device]:
        return self.devices.get(device_id)
