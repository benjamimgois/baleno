"""Runnable demo / PoC for the Network Topology Mapper.

Two entry points:

* ``python -m balenolib.topology``        → interactive graph window (synthetic data)
* ``python -m balenolib.topology --parse`` → print the LLDP adjacency parse result
  from a fabricated SNMP walk (proves the parser logic with no network access)
"""

from __future__ import annotations

import sys

from balenolib.topology.collector import LldpCollector, SnmpCredentials
from balenolib.topology.engine import TopologyEngine
from balenolib.topology.models import (
    Device, DeviceRole, Interface, LldpNeighbor, TopologyGraph,
)


def synthetic_graph() -> TopologyGraph:
    """Build a realistic core/dist/access topology with LLDP adjacencies."""
    core = Device(
        id='SW-CORE', ip='10.0.0.1', hostname='sw-core', role=DeviceRole.CORE,
        vendor='Cisco', model='Catalyst 9300', chassis_id='AA:BB:CC:00:00:01',
        sys_descr='Cisco IOS XE Software, Catalyst L3 Switch', status='up', latency_ms=0.4)
    dist = Device(
        id='SW-DIST-1', ip='10.0.1.1', hostname='sw-dist-1', role=DeviceRole.SWITCH,
        vendor='Cisco', model='Catalyst 9200', chassis_id='AA:BB:CC:00:00:02',
        sys_descr='Cisco IOS XE Software, Catalyst L3 Switch', status='up', latency_ms=0.8)
    acc = Device(
        id='SW-ACC-1', ip='10.0.2.1', hostname='sw-acc-1', role=DeviceRole.ACCESS,
        vendor='Cisco', model='Catalyst 2960', chassis_id='AA:BB:CC:00:00:03',
        sys_descr='Cisco IOS Software, C2960 Software', status='up', latency_ms=1.2)
    router = Device(
        id='RTR-EDGE', ip='10.0.0.254', hostname='rtr-edge', role=DeviceRole.ROUTER,
        vendor='MikroTik', model='RouterOS', chassis_id='AA:BB:CC:00:00:04',
        sys_descr='RouterOS RB4011', status='up', latency_ms=0.6)
    server = Device(
        id='SRV-DC', ip='10.0.2.10', hostname='srv-dc', role=DeviceRole.SERVER,
        vendor='Dell', model='PowerEdge', chassis_id='AA:BB:CC:00:00:05',
        sys_descr='Linux srv-dc 6.1.0', status='up', latency_ms=2.0)
    ap = Device(
        id='AP-1', ip='10.0.2.20', hostname='ap-1', role=DeviceRole.AP,
        vendor='Ubiquiti', model='U6-Lite', chassis_id='AA:BB:CC:00:00:06',
        sys_descr='UniFi AP', status='up', latency_ms=1.5)
    host1 = Device(
        id='PC-01', ip='10.0.2.30', hostname='pc-01', role=DeviceRole.HOST,
        status='up', latency_ms=2.4)
    host2 = Device(
        id='PC-02', ip='10.0.2.31', hostname='pc-02', role=DeviceRole.HOST,
        status='down', latency_ms=0.0)

    # Synthetic interfaces so the link states/speeds render in the demo:
    #   green  (10G) → core ⟷ dist
    #   blue   (1G)  → dist ⟷ acc
    #   orange (100M)→ acc ⟷ server / ap
    #   red    (down)→ core ⟷ router (router ether1 is down)
    core.interfaces[1] = Interface(index=1, name='Te1/1/1', oper_status='up',
                                   speed_mbps=10000,
                                   in_rate_bps=45e6, out_rate_bps=12e6)
    core.interfaces[24] = Interface(index=24, name='Te1/0/24', oper_status='up',
                                    speed_mbps=10000)
    dist.interfaces[48] = Interface(index=48, name='Te1/0/48', oper_status='up',
                                    speed_mbps=10000,
                                    in_rate_bps=12e6, out_rate_bps=45e6)
    dist.interfaces[2] = Interface(index=2, name='Gi1/0/1', oper_status='up',
                                   speed_mbps=1000)
    acc.interfaces[1] = Interface(index=1, name='Gi0/1', oper_status='up',
                                  speed_mbps=1000)
    acc.interfaces[10] = Interface(index=10, name='Gi0/10', oper_status='up',
                                   speed_mbps=100)
    acc.interfaces[11] = Interface(index=11, name='Gi0/11', oper_status='up',
                                   speed_mbps=100)
    router.interfaces[1] = Interface(index=1, name='ether1', oper_status='down',
                                     speed_mbps=1000)

    # LLDP adjacencies — each side advertises the other, ports labelled both ends.
    core.lldp_neighbors.append(LldpNeighbor(
        local_port_num=1, local_port_name='Te1/1/1', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:02', remote_port_id='Te1/0/48',
        remote_sys_name='sw-dist-1', remote_mgmt_addr='10.0.1.1'))
    dist.lldp_neighbors.append(LldpNeighbor(
        local_port_num=48, local_port_name='Te1/0/48', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:01', remote_port_id='Te1/1/1',
        remote_sys_name='sw-core', remote_mgmt_addr='10.0.0.1'))

    dist.lldp_neighbors.append(LldpNeighbor(
        local_port_num=2, local_port_name='Gi1/0/1', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:03', remote_port_id='Gi0/1',
        remote_sys_name='sw-acc-1', remote_mgmt_addr='10.0.2.1'))
    acc.lldp_neighbors.append(LldpNeighbor(
        local_port_num=1, local_port_name='Gi0/1', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:02', remote_port_id='Gi1/0/1',
        remote_sys_name='sw-dist-1', remote_mgmt_addr='10.0.1.1'))

    core.lldp_neighbors.append(LldpNeighbor(
        local_port_num=24, local_port_name='Te1/0/24', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:04', remote_port_id='ether1',
        remote_sys_name='rtr-edge', remote_mgmt_addr='10.0.0.254'))
    router.lldp_neighbors.append(LldpNeighbor(
        local_port_num=1, local_port_name='ether1', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:01', remote_port_id='Te1/0/24',
        remote_sys_name='sw-core', remote_mgmt_addr='10.0.0.1'))

    acc.lldp_neighbors.append(LldpNeighbor(
        local_port_num=10, local_port_name='Gi0/10', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:05', remote_port_id='eth0',
        remote_sys_name='srv-dc', remote_mgmt_addr='10.0.2.10'))
    acc.lldp_neighbors.append(LldpNeighbor(
        local_port_num=11, local_port_name='Gi0/11', remote_index=1,
        remote_chassis_id='AA:BB:CC:00:00:06', remote_port_id='eth0',
        remote_sys_name='ap-1', remote_mgmt_addr='10.0.2.20'))
    # orphan hosts (ICMP-only, no LLDP)
    host1.status = 'up'
    host2.status = 'down'

    devices = [core, dist, acc, router, server, ap, host1, host2]
    return TopologyEngine().build(devices)


def demo_parse() -> None:
    """Prove the LLDP parser logic against a fabricated SNMP walk."""
    print("LLDP adjacency parse demo (no network, fabricated SNMP walk):\n")

    # Fabricate what _collect_neighbors would see from _walk() for one device.
    # OID suffix = .timeMark.localPortNum.remIndex
    fake_walk = {
        '1.0.8802.1.1.2.1.4.1.1.5.100.48.1': 'AA:BB:CC:00:00:01',   # chassis id
        '1.0.8802.1.1.2.1.4.1.1.7.100.48.1': 'Te1/1/1',             # port id
        '1.0.8802.1.1.2.1.4.1.1.9.100.48.1': 'sw-core',             # sys name
        '1.0.8802.1.1.2.1.4.2.1.4.100.48.1.1': '10.0.0.1',          # mgmt addr IPv4
        '1.0.8802.1.1.2.1.3.7.1.3.48': 'Te1/0/48',                  # local port id
    }

    from balenolib.topology.collector import (
        _oid_suffix, OID_REM_CHASSIS_ID, OID_REM_PORT_ID, OID_REM_SYS_NAME,
        OID_REM_MAN_ADDR, OID_LOC_PORT_ID,
    )

    print(f"{'OID':<45} {'suffix':<15} value")
    for oid, val in fake_walk.items():
        # match against the column prefix that produced it
        prefix = next(p for p in (
            OID_REM_CHASSIS_ID, OID_REM_PORT_ID, OID_REM_SYS_NAME,
            OID_REM_MAN_ADDR, OID_LOC_PORT_ID) if oid.startswith(p + '.'))
        suffix = _oid_suffix(oid, prefix)
        print(f"{oid:<45} {'.'.join(suffix):<15} {val}")

    print("\n→ parsed adjacency: local port Te1/0/48 → sw-core "
          "(Te1/1/1, 10.0.0.1)")


def demo_gui(layout_mode: str = 'hierarchical', layout_path: str = '') -> None:
    from PyQt6.QtWidgets import QApplication, QMainWindow, QToolBar

    graph = synthetic_graph()
    app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("Baleno — Network Topology Mapper (PoC)")
    window.resize(1100, 750)

    from balenolib.topology.gui.view import TopologyView
    from balenolib.topology.gui.detail import DeviceDetailDialog

    view = TopologyView()
    if layout_path:
        view.set_layout_path(layout_path)
    view.load(graph, layout_mode)
    view._scene.node_double_clicked.connect(
        lambda dev: DeviceDetailDialog(dev, window).show())

    toolbar = QToolBar("Layout")
    toolbar.addAction("Hierarchical", lambda: view.switch_layout('hierarchical'))
    toolbar.addAction("Force", lambda: view.switch_layout('force'))
    toolbar.addAction("Fit", view.fit_in_view)
    window.addToolBar(toolbar)
    window.setCentralWidget(view)

    window.show()
    sys.exit(app.exec())


def main() -> None:
    if '--parse' in sys.argv:
        demo_parse()
        return
    mode = 'force' if '--force' in sys.argv else 'hierarchical'
    layout_path = ''
    if '--save' in sys.argv:
        idx = sys.argv.index('--save')
        if idx + 1 < len(sys.argv):
            layout_path = sys.argv[idx + 1]
        else:
            from balenolib.topology.persistence import default_layout_path
            layout_path = default_layout_path()
    demo_gui(mode, layout_path)


if __name__ == '__main__':
    main()
