"""Network Topology Mapper for Cetus.

Subpackages:
    models     — dataclasses: Device, Interface, LldpNeighbor, PortLink, TopologyGraph
    discovery  — L3 reachability (async ICMP scanner)
    collector  — L2 LLDP discovery via SNMP (pysnmp)
    engine     — topology graph building, layouts, anomaly detection
    gui        — interactive QGraphicsView rendering (The Dude / ZabFox style)
"""

from cetuslib.topology.models import (
    Device,
    DeviceRole,
    Interface,
    LldpNeighbor,
    PortLink,
    TopologyGraph,
)
from cetuslib.topology.engine import TopologyEngine
from cetuslib.topology.persistence import (
    save_layout,
    load_layout,
    apply_layout,
    default_layout_path,
)

__all__ = [
    'Device',
    'DeviceRole',
    'Interface',
    'LldpNeighbor',
    'PortLink',
    'TopologyGraph',
    'TopologyEngine',
    'save_layout',
    'load_layout',
    'apply_layout',
    'default_layout_path',
]
