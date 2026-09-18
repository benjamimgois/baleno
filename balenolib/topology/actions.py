"""Context-menu actions that invoke other Baleno modules from the topology map.

The topology canvas knows each node's IP and role.  This module turns that into
one-click access to the other Baleno tools (terminal, IP scanner, SNMP, file
transfer) by pre-filling their UI fields and calling their existing public
flows — the same pattern the SSH-profile tree already uses.

Credentials are resolved from saved SSH profiles by IP.  When no profile
matches, the target module is opened pre-filled and the user completes the
remaining fields.  This keeps the dispatcher isolated from ``main.py``.
"""

from __future__ import annotations

import base64
from typing import Any, Optional

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMenu, QStyle

from balenolib.utils import load_svg_icon_dual

DEFAULT_SCAN_PORTS = '22,23,80,443,3389,8080,8443,161'

# Icon filename per menu entry.  Icons are recoloured to a light tone so they
# stay visible on the dark context-menu background.
_ICONS = {
    'ping': 'proto_icmp.svg',
    'access': 'remote.svg',
    'ssh': 'ssh2.svg',
    'telnet': 'telnet.svg',
    'scan': 'ipscan.svg',
    'tcp': 'proto_tcp.svg',
    'udp': 'proto_udp.svg',
    'icmp': 'proto_icmp.svg',
    'traceroute': 'traceroute.svg',
    'snmp': 'snmp.svg',
    'walk': 'snmp_walk.svg',
    'get': 'snmp_get.svg',
    'getnext': 'snmp_getnext.svg',
    'transfer': 'filetransfer.svg',
    'smb': 'smb.svg',
    'ftp': 'ftp.svg',
    'tftp': 'TFTP.svg',
}

_MENU_STYLE = """
    QMenu {
        background-color: #161B22;
        border: 1px solid #30363D;
        color: #C9D1D9;
        padding: 4px 0px;
    }
    QMenu::item {
        padding: 6px 22px 6px 14px;
    }
    QMenu::item:selected {
        background-color: #4169E1;
        color: #ffffff;
    }
    QMenu::item:disabled {
        color: #6E7681;
    }
    QMenu::separator {
        height: 1px;
        background: #30363D;
        margin: 4px 8px;
    }
"""


class TopologyActions:
    """Builder/dispatcher for node and group context menus."""

    @staticmethod
    def _dark_menu() -> QMenu:
        menu = QMenu()
        menu.setStyleSheet(_MENU_STYLE)
        return menu

    @staticmethod
    def _icon(main_window, name: str, size: int = 16):
        """Load an icon by its ``_ICONS`` key, recoloured to a light tone."""
        filename = _ICONS.get(name)
        if not filename:
            return None
        path = main_window.get_icon_path(filename)
        if not path:
            return None
        return load_svg_icon_dual(path, size, '#e6edf3', '#e6edf3')

    @staticmethod
    def _trash_icon():
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon)

    @staticmethod
    def _resolve_profile(main_window, ip: str) -> Optional[dict[str, Any]]:
        """Return the saved SSH profile whose host equals ``ip`` (or None)."""
        if not ip:
            return None
        try:
            profiles = main_window.config.get_ssh_profiles()
        except Exception:
            return None
        for profile in profiles or []:
            if str(profile.get('host', '')).strip() == ip:
                return profile
        return None

    @staticmethod
    def _decoded_password(profile: dict[str, Any]) -> str:
        saved = profile.get('password', '') or ''
        try:
            return base64.b64decode(saved.encode()).decode()
        except Exception:
            return ''

    # ── menu entry points ────────────────────────────────────────────────

    @staticmethod
    def show_node_menu(main_window, device, pos) -> None:
        """Show the context menu for a device node."""
        TopologyActions._show_menu(main_window, device, pos, include_remove=True)

    @staticmethod
    def show_group_menu(main_window, group, pos) -> None:
        """Show the context menu for a collapsed group (acts on parent device)."""
        device = group.graph.devices.get(group.parent_id) if group.graph else None
        if device is None:
            return
        TopologyActions._show_menu(main_window, device, pos, include_remove=False)

    @staticmethod
    def _show_menu(main_window, device, pos, include_remove: bool) -> None:
        has_ip = bool(device.ip)
        menu = TopologyActions._dark_menu()

        ping_act = menu.addAction('Ping')
        ping_act.setIcon(TopologyActions._icon(main_window, 'ping'))
        menu.addSeparator()

        access = menu.addMenu('Access')
        access.setIcon(TopologyActions._icon(main_window, 'access'))
        a_ssh = access.addAction('SSH')
        a_ssh.setIcon(TopologyActions._icon(main_window, 'ssh'))
        a_telnet = access.addAction('Telnet')
        a_telnet.setIcon(TopologyActions._icon(main_window, 'telnet'))

        scan = menu.addMenu('Scan')
        scan.setIcon(TopologyActions._icon(main_window, 'scan'))
        s_tcp = scan.addAction('TCP')
        s_tcp.setIcon(TopologyActions._icon(main_window, 'tcp'))
        s_udp = scan.addAction('UDP')
        s_udp.setIcon(TopologyActions._icon(main_window, 'udp'))

        traceroute = menu.addMenu('Traceroute')
        traceroute.setIcon(TopologyActions._icon(main_window, 'traceroute'))
        tr_icmp = traceroute.addAction('ICMP')
        tr_icmp.setIcon(TopologyActions._icon(main_window, 'icmp'))
        tr_tcp = traceroute.addAction('TCP')
        tr_tcp.setIcon(TopologyActions._icon(main_window, 'tcp'))
        tr_udp = traceroute.addAction('UDP')
        tr_udp.setIcon(TopologyActions._icon(main_window, 'udp'))

        snmp = menu.addMenu('SNMP')
        snmp.setIcon(TopologyActions._icon(main_window, 'snmp'))
        n_walk = snmp.addAction('Walk')
        n_walk.setIcon(TopologyActions._icon(main_window, 'walk'))
        n_get = snmp.addAction('Get')
        n_get.setIcon(TopologyActions._icon(main_window, 'get'))
        n_next = snmp.addAction('GetNext')
        n_next.setIcon(TopologyActions._icon(main_window, 'getnext'))

        transfer = menu.addMenu('Transfer')
        transfer.setIcon(TopologyActions._icon(main_window, 'transfer'))
        t_ssh = transfer.addAction('SSH')
        t_ssh.setIcon(TopologyActions._icon(main_window, 'ssh'))
        t_smb = transfer.addAction('SMB')
        t_smb.setIcon(TopologyActions._icon(main_window, 'smb'))
        t_ftp = transfer.addAction('FTP')
        t_ftp.setIcon(TopologyActions._icon(main_window, 'ftp'))
        t_tftp = transfer.addAction('TFTP')
        t_tftp.setIcon(TopologyActions._icon(main_window, 'tftp'))

        if not has_ip:
            ping_act.setEnabled(False)
            for sub in (access, scan, traceroute, snmp, transfer):
                sub.setEnabled(False)

        menu.addSeparator()

        # Device Type submenu
        type_menu = menu.addMenu('Device Type')
        from balenolib.topology.models import DeviceRole
        from balenolib.topology.gui.view import make_role_icon
        from balenolib.topology.gui.layers import make_color_icon

        _ROLE_ITEMS = [
            (DeviceRole.ROUTER, 'Router'),
            (DeviceRole.CORE, 'Core Switch (L3)'),
            (DeviceRole.SWITCH, 'Switch (L2)'),
            (DeviceRole.ACCESS, 'Access Switch'),
            (DeviceRole.FIREWALL, 'Firewall'),
            (DeviceRole.SERVER, 'Server'),
            (DeviceRole.AP, 'Access Point (Wi-Fi)'),
            (DeviceRole.HOST, 'Host (PC)'),
            (DeviceRole.PHONE, 'IP Phone'),
            (DeviceRole.CAMERA, 'Camera'),
            (DeviceRole.CLOUD, 'Cloud'),
            (DeviceRole.INTERNET, 'Internet'),
        ]

        type_actions: list[tuple[Any, DeviceRole]] = []
        for role, label in _ROLE_ITEMS:
            act = type_menu.addAction(label)
            icon = make_role_icon(role, 16)
            if not icon.isNull():
                act.setIcon(icon)
            act.setCheckable(True)
            if device.role == role:
                act.setChecked(True)
            type_actions.append((act, role))

        # Layer submenu
        layer_menu = menu.addMenu('Layer')
        topo_page = getattr(main_window, 'topology_page', None)
        graph = getattr(topo_page, '_graph', None) if topo_page else None
        known_layers: set[str] = set()
        if topo_page and hasattr(topo_page, 'layer_tree') and hasattr(topo_page.layer_tree, '_all_layers'):
            known_layers.update(topo_page.layer_tree._all_layers)
        if graph:
            if hasattr(graph, 'layer_colors') and graph.layer_colors:
                known_layers.update(graph.layer_colors.keys())
            if hasattr(graph, 'devices'):
                for d in graph.devices.values():
                    known_layers.update(d.layers)

        act_new_layer = layer_menu.addAction('+ Move to New Layer…')
        layer_menu.addSeparator()

        layer_actions: list[tuple[Any, str]] = []
        for layer_name in sorted(known_layers):
            act = layer_menu.addAction(layer_name)
            act.setCheckable(True)
            if layer_name in device.layers:
                act.setChecked(True)
            color_hex = None
            if topo_page and hasattr(topo_page, 'layer_tree'):
                color_hex = topo_page.layer_tree.get_layer_color(layer_name)
            elif graph and hasattr(graph, 'layer_colors'):
                color_hex = graph.layer_colors.get(layer_name)
            if color_hex:
                act.setIcon(make_color_icon(color_hex, 14))
            layer_actions.append((act, layer_name))

        remove_act = None
        if include_remove:
            menu.addSeparator()
            remove_act = menu.addAction('Remove')
            remove_act.setIcon(TopologyActions._trash_icon())

        chosen = menu.exec(pos)
        if chosen is None:
            return
        if chosen is ping_act:
            TopologyActions._invoke_ping(main_window, device)
        elif include_remove and chosen is remove_act:
            TopologyActions._remove_node(main_window, device)
        elif chosen is a_ssh:
            TopologyActions._invoke_ssh(main_window, device, 'SSH')
        elif chosen is a_telnet:
            TopologyActions._invoke_ssh(main_window, device, 'Telnet')
        elif chosen is s_tcp:
            TopologyActions._invoke_scan(main_window, device, 'TCP')
        elif chosen is s_udp:
            TopologyActions._invoke_scan(main_window, device, 'UDP')
        elif chosen is tr_icmp:
            TopologyActions._invoke_traceroute(main_window, device, 'ICMP')
        elif chosen is tr_tcp:
            TopologyActions._invoke_traceroute(main_window, device, 'TCP')
        elif chosen is tr_udp:
            TopologyActions._invoke_traceroute(main_window, device, 'UDP')
        elif chosen is n_walk:
            TopologyActions._invoke_snmp(main_window, device, 'snmpwalk')
        elif chosen is n_get:
            TopologyActions._invoke_snmp(main_window, device, 'snmpget')
        elif chosen is n_next:
            TopologyActions._invoke_snmp(main_window, device, 'snmpgetnext')
        elif chosen is t_ssh:
            TopologyActions._invoke_transfer(main_window, device, 'SSH')
        elif chosen is t_smb:
            TopologyActions._invoke_transfer(main_window, device, 'SMB')
        elif chosen is t_ftp:
            TopologyActions._invoke_transfer(main_window, device, 'FTP')
        elif chosen is t_tftp:
            TopologyActions._invoke_transfer(main_window, device, 'TFTP')
        else:
            for act, role in type_actions:
                if chosen is act:
                    TopologyActions._change_device_role(main_window, device, role)
                    return
            if chosen is act_new_layer:
                TopologyActions._move_device_to_new_layer(main_window, device)
                return
            for act, layer_name in layer_actions:
                if chosen is act:
                    TopologyActions._change_device_layer(main_window, device, layer_name)
                    return

    # ── invokers ─────────────────────────────────────────────────────────

    @staticmethod
    def _change_device_role(main_window, device, new_role: DeviceRole) -> None:
        device.role = new_role
        topo_page = getattr(main_window, 'topology_page', None)
        view = getattr(topo_page, 'view', None) if topo_page else None
        if view is not None:
            view.change_device_role(device.id, new_role)
        if topo_page is not None and hasattr(topo_page, 'layer_tree') and topo_page._graph is not None:
            topo_page.layer_tree.populate(topo_page._graph, topo_page._hidden_layers())

    @staticmethod
    def _change_device_layer(main_window, device, new_layer: str) -> None:
        import re
        m = re.search(r'-(\d+)$', new_layer)
        device.layer = int(m.group(1)) if m else 1
        device.layers = {new_layer}
        topo_page = getattr(main_window, 'topology_page', None)
        view = getattr(topo_page, 'view', None) if topo_page else None
        if view is not None:
            view.change_device_layer(device.id, new_layer)
        if topo_page is not None and hasattr(topo_page, 'layer_tree') and topo_page._graph is not None:
            topo_page.layer_tree.populate(topo_page._graph, topo_page._hidden_layers())
            if view is not None:
                view.set_visible_layers(topo_page.layer_tree._visible_layers)

    @staticmethod
    def _move_device_to_new_layer(main_window, device) -> None:
        from PyQt6.QtWidgets import QInputDialog, QColorDialog
        from PyQt6.QtGui import QColor

        name, ok = QInputDialog.getText(
            main_window, 'Move to New Layer', 'New layer name:'
        )
        name = name.strip()
        if not ok or not name:
            return

        color = QColorDialog.getColor(QColor('#3B82F6'), main_window, f'Select Color for Layer {name}')
        color_hex = color.name() if color.isValid() else '#3B82F6'

        topo_page = getattr(main_window, 'topology_page', None)
        if topo_page is not None:
            if topo_page._graph is not None:
                if not hasattr(topo_page._graph, 'layer_colors') or topo_page._graph.layer_colors is None:
                    topo_page._graph.layer_colors = {}
                topo_page._graph.layer_colors[name] = color_hex
            if hasattr(topo_page, 'layer_tree'):
                topo_page.layer_tree.set_layer_color(name, color_hex)
        TopologyActions._change_device_layer(main_window, device, name)

    @staticmethod
    def _remove_node(main_window, device) -> None:
        view = getattr(getattr(main_window, 'topology_page', None), 'view', None)
        if view is not None:
            view.remove_node(device)

    @staticmethod
    def _invoke_ping(main_window, device) -> None:
        """Open a ping to the device IP in the system's native terminal."""
        if not device.ip:
            return
        main_window._launch_native_terminal(['ping', device.ip])

    @staticmethod
    def _invoke_ssh(main_window, device, protocol: str) -> None:
        profile = TopologyActions._resolve_profile(main_window, device.ip)
        main_window.switch_tab(0)
        main_window._ssh_protocol_btn_clicked(protocol)
        main_window.ssh_host.setText(device.ip)
        if profile:
            main_window.ssh_port.setText(str(profile.get('port', '22')))
            main_window.ssh_username.setText(str(profile.get('username', '') or ''))
            if profile.get('auth_method') == 'key':
                main_window.use_ssh_key.setChecked(True)
                main_window.ssh_key_path.setText(str(profile.get('key_path', '') or ''))
                main_window.ssh_password.clear()
            else:
                main_window.use_ssh_key.setChecked(False)
                main_window.ssh_password.setText(TopologyActions._decoded_password(profile))
            main_window._pending_profile_name = profile.get('name', '')
            main_window._pending_vendor = profile.get('vendor', 'Default')
            main_window._pending_terminal_mode = profile.get('terminal_mode', 'auto')
            QTimer.singleShot(50, main_window.connect_ssh)
        elif protocol == 'Telnet':
            QTimer.singleShot(50, main_window.connect_ssh)
        # SSH without a matching profile: stay on the SSH tab, host pre-filled.

    @staticmethod
    def _invoke_scan(main_window, device, method: str) -> None:
        main_window.switch_tab(2)
        main_window._scan_method_btn_clicked(method)
        main_window.scan_mask_combo.setCurrentText('32')
        main_window.scan_network_input.setText(device.ip)
        if method in ('TCP', 'UDP'):
            main_window.scan_ports_input.setText(DEFAULT_SCAN_PORTS)
        main_window._start_scan()

    @staticmethod
    def _invoke_traceroute(main_window, device, method: str) -> None:
        main_window.switch_tab(3)
        main_window.traceroute_target_input.setText(device.ip)
        main_window.traceroute_current_method = method
        main_window._traceroute_method_changed(method)
        main_window._start_traceroute()

    @staticmethod
    def _invoke_snmp(main_window, device, qtype: str) -> None:
        main_window.switch_tab(4)
        main_window._snmp_type_btn_clicked(qtype)
        main_window.snmp_host_input.setText(device.ip)
        try:
            history = main_window.config.get_vuln_community_history()
        except Exception:
            history = []
        main_window.snmp_community_input.setText(history[0] if history else 'public')
        if qtype == 'snmpwalk':
            main_window.snmp_oid_input.clear()
            QTimer.singleShot(50, main_window.execute_snmp_query)
        # get/getnext need an OID: open the module pre-filled, let the user type it.

    @staticmethod
    def _invoke_transfer(main_window, device, proto: str) -> None:
        profile = TopologyActions._resolve_profile(main_window, device.ip)
        main_window.switch_tab(7)
        main_window._ft_proto_changed(proto)
        main_window._ft_host_input.setText(device.ip)
        if proto in ('SSH', 'FTP') and profile:
            main_window._ft_user_input.setText(str(profile.get('username', '') or ''))
            main_window._ft_pass_input.setText(TopologyActions._decoded_password(profile))
            QTimer.singleShot(50, main_window._ft_client_connect)
        # SMB/TFTP client mode is not implemented, and SSH/FTP without a profile
        # need credentials: leave the module open pre-filled for the user.
