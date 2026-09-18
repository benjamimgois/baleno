#!/usr/bin/env python3
"""Unit tests for discovery modes, layer colors, and node context actions."""

import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from balenolib.topology.models import Device, DeviceRole, TopologyGraph
from balenolib.topology.persistence import save_map, load_map
from balenolib.topology.worker import TopologyDiscoveryWorker
from balenolib.topology.collector import SnmpCredentials
from balenolib.topology.gui.layers import parse_layer_prefix


class TestDiscoveryModesAndLayers(unittest.TestCase):

    def test_layer_colors_model_and_persistence(self):
        """Test layer_colors serialization, deserialization and persistence in v3 map."""
        graph = TopologyGraph()
        graph.devices['192.168.1.1'] = Device(
            id='192.168.1.1', ip='192.168.1.1', role=DeviceRole.ROUTER,
            layers={'Core-Net'}
        )
        graph.layer_colors = {
            'Core-Net': '#3B82F6',
            'DMZ': '#EF4444',
        }

        d = graph.to_dict()
        self.assertIn('layer_colors', d)
        self.assertEqual(d['layer_colors']['Core-Net'], '#3B82F6')

        # Test from_dict restores layer_colors
        restored = TopologyGraph.from_dict(d)
        self.assertEqual(restored.layer_colors.get('Core-Net'), '#3B82F6')
        self.assertEqual(restored.layer_colors.get('DMZ'), '#EF4444')

        # Test backward compatibility: JSON without layer_colors
        legacy_dict = graph.to_dict()
        del legacy_dict['layer_colors']
        legacy_restored = TopologyGraph.from_dict(legacy_dict)
        self.assertEqual(legacy_restored.layer_colors, {})

        # Test save_map and load_map with temporary file
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
            temp_path = tf.name
        try:
            positions = {'192.168.1.1': (100.0, 200.0)}
            save_map(graph, positions, temp_path)

            loaded_graph, loaded_pos, loaded_groups = load_map(temp_path)
            self.assertEqual(loaded_graph.layer_colors.get('Core-Net'), '#3B82F6')
            self.assertEqual(loaded_graph.layer_colors.get('DMZ'), '#EF4444')
            self.assertEqual(loaded_pos['192.168.1.1'], (100.0, 200.0))
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def test_layer_prefix_and_inheritance(self):
        """Test hop-layer naming decomposition for color inheritance."""
        self.assertEqual(parse_layer_prefix('Rede-A'), ('Rede-A', 1))
        self.assertEqual(parse_layer_prefix('Rede-A-2'), ('Rede-A', 2))
        self.assertEqual(parse_layer_prefix('backbone-infra-3'), ('backbone-infra', 3))
        self.assertEqual(parse_layer_prefix('SingleName'), ('SingleName', 1))

    @patch('balenolib.topology.worker.PingScanner')
    @patch('balenolib.topology.worker.LldpCollector')
    def test_worker_basic_mode_skips_snmp(self, mock_lldp_cls, mock_ping_cls):
        """Verify that basic mode executes only ICMP and creates Host devices without SNMP."""
        # Mock PingScanner instance method scan_sync
        mock_instance = MagicMock()
        mock_instance.scan_sync.return_value = {
            '10.0.0.1': 1.5,
            '10.0.0.2': 3.2,
        }
        mock_ping_cls.return_value = mock_instance

        creds = SnmpCredentials(version='v2c', community='public')
        worker = TopologyDiscoveryWorker(
            networks=['10.0.0.0/30'],
            credentials=creds,
            mode='basic',
            layer_name='TestLayer',
            layer_color='#10B981',
        )

        devices_found = []
        worker.device_found.connect(devices_found.append)

        finished_graphs = []
        worker.finished.connect(finished_graphs.append)

        # Run synchronously
        worker.run()

        # Check LLDP/SNMP was never instantiated or invoked
        mock_lldp_cls.assert_not_called()

        # Check results
        self.assertEqual(len(finished_graphs), 1)
        graph = finished_graphs[0]
        self.assertEqual(len(graph.devices), 2)
        self.assertIn('10.0.0.1', graph.devices)
        self.assertIn('10.0.0.2', graph.devices)

        dev1 = graph.devices['10.0.0.1']
        self.assertEqual(dev1.role, DeviceRole.HOST)
        self.assertEqual(dev1.status, 'up')
        self.assertIn('TestLayer', dev1.layers)

        # Check layer color was attached to graph
        self.assertEqual(graph.layer_colors.get('TestLayer'), '#10B981')

    def test_device_role_and_layer_mutation(self):
        """Verify modifying device role and layer correctly reassigns attributes."""
        dev = Device(id='node-1', role=DeviceRole.HOST, layers={'Old-Layer'}, layer=1)
        self.assertEqual(dev.role, DeviceRole.HOST)
        self.assertIn('Old-Layer', dev.layers)

        # Reassign role
        dev.role = DeviceRole.SWITCH
        self.assertEqual(dev.role, DeviceRole.SWITCH)

        # Move to new layer
        new_layer = 'New-Layer-2'
        import re
        m = re.search(r'-(\d+)$', new_layer)
        dev.layer = int(m.group(1)) if m else 1
        dev.layers = {new_layer}

        self.assertEqual(dev.layers, {'New-Layer-2'})
        self.assertEqual(dev.layer, 2)

    def test_manual_layer_population(self):
        """Verify LayerTreeWidget includes manual layers with 0 nodes."""
        from PyQt6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        from balenolib.topology.gui.layers import LayerTreeWidget

        graph = TopologyGraph()
        graph.devices['10.0.0.1'] = Device(id='10.0.0.1', layers={'Active-Layer'})
        graph.layer_colors = {
            'Active-Layer': '#3B82F6',
            'Manual-VLAN': '#10B981',
        }

        tree = LayerTreeWidget()
        tree.populate(graph)

        self.assertIn('Active-Layer', tree._all_layers)
        self.assertIn('Manual-VLAN', tree._all_layers)
        self.assertEqual(tree._layer_counts.get('Active-Layer'), 1)
        self.assertEqual(tree._layer_counts.get('Manual-VLAN'), 0)

    def test_topology_view_interaction_modes(self):
        """Verify TopologyView defaults to RubberBandDrag and toggles modes correctly."""
        from PyQt6.QtWidgets import QApplication, QGraphicsView
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        from balenolib.topology.gui.view import TopologyView

        view = TopologyView()
        # Default should be RubberBandDrag (selection mode)
        self.assertEqual(view.dragMode(), QGraphicsView.DragMode.RubberBandDrag)
        self.assertEqual(view._interaction_mode, 'select')

        # Switch to pan mode
        view.set_interaction_mode('pan')
        self.assertEqual(view.dragMode(), QGraphicsView.DragMode.ScrollHandDrag)
        self.assertEqual(view._interaction_mode, 'pan')

        # Switch back to select mode
        view.set_interaction_mode('select')
        self.assertEqual(view.dragMode(), QGraphicsView.DragMode.RubberBandDrag)

        # Toggle link mode and restore
        view.set_link_mode(True)
        self.assertEqual(view.dragMode(), QGraphicsView.DragMode.NoDrag)
        view.set_link_mode(False)
        self.assertEqual(view.dragMode(), QGraphicsView.DragMode.RubberBandDrag)

    def test_batch_device_role_and_layer_mutation(self):
        """Verify batch mutating layers and roles on multiple devices."""
        from PyQt6.QtWidgets import QApplication
        import sys
        app = QApplication.instance() or QApplication(sys.argv)
        from balenolib.topology.gui.view import TopologyView
        from balenolib.topology.actions import TopologyActions

        graph = TopologyGraph()
        dev1 = Device(id='d1', role=DeviceRole.ROUTER, layers={'Net-A'}, layer=1)
        dev2 = Device(id='d2', role=DeviceRole.SWITCH, layers={'Net-A'}, layer=1)
        dev3 = Device(id='d3', role=DeviceRole.HOST, layers={'Net-B'}, layer=1)
        graph.devices['d1'] = dev1
        graph.devices['d2'] = dev2
        graph.devices['d3'] = dev3

        view = TopologyView()
        view.load(graph)

        # Batch change layer for d1 and d2
        view.change_devices_layer(['d1', 'd2'], 'VLAN-50-3')
        self.assertEqual(dev1.layers, {'VLAN-50-3'})
        self.assertEqual(dev1.layer, 3)
        self.assertEqual(dev2.layers, {'VLAN-50-3'})
        self.assertEqual(dev2.layer, 3)
        # d3 should remain unchanged
        self.assertEqual(dev3.layers, {'Net-B'})
        self.assertEqual(dev3.layer, 1)

        # Batch change role for d1 and d2
        view.change_devices_role(['d1', 'd2'], DeviceRole.FIREWALL)
        self.assertEqual(dev1.role, DeviceRole.FIREWALL)
        self.assertEqual(dev2.role, DeviceRole.FIREWALL)
        self.assertEqual(dev3.role, DeviceRole.HOST)

        # Test TopologyActions batch layer helper
        mock_main = MagicMock()
        mock_topo_page = MagicMock()
        mock_topo_page.view = view
        mock_topo_page._graph = graph
        mock_main.topology_page = mock_topo_page

        TopologyActions._change_devices_layer(mock_main, [dev1, dev2, dev3], 'All-Net')
        self.assertEqual(dev1.layers, {'All-Net'})
        self.assertEqual(dev2.layers, {'All-Net'})
        self.assertEqual(dev3.layers, {'All-Net'})

    def test_device_details_model_persistence_and_dialog_styling(self):
        """Test device interface/sys_descr persistence and dialog dark theme styling."""
        import sys
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from balenolib.topology.models import Interface, LldpNeighbor
        from balenolib.topology.gui.detail import (
            DeviceDetailDialog, GroupDevicesDialog, LinkCreationDialog, LinkEditDialog,
            _DARK_DIALOG_STYLE,
        )

        dev = Device(
            id='sw1', ip='10.0.0.1', hostname='Core-SW', role=DeviceRole.SWITCH,
            sys_descr='MikroTik RouterOS 7.12', uptime='42 days', latency_ms=1.5,
        )
        dev.interfaces[1] = Interface(
            index=1, name='ether1', descr='GigabitEthernet1', alias='Uplink to ISP', oper_status='up'
        )
        dev.interfaces[2] = Interface(
            index=2, name='ether2', descr='GigabitEthernet2', alias='', oper_status='down'
        )
        dev.lldp_neighbors.append(LldpNeighbor(
            local_port_num=1, local_port_name='ether1', remote_sys_name='Edge-Rtr',
            remote_port_id='ether5',
        ))

        # Test round-trip persistence
        d = dev.to_dict()
        self.assertEqual(d['sys_descr'], 'MikroTik RouterOS 7.12')
        self.assertEqual(d['uptime'], '42 days')
        self.assertEqual(d['latency_ms'], 1.5)
        self.assertIn('1', d['interfaces'])
        self.assertEqual(d['interfaces']['1']['descr'], 'GigabitEthernet1')
        self.assertEqual(d['interfaces']['1']['alias'], 'Uplink to ISP')
        self.assertEqual(len(d['lldp_neighbors']), 1)

        restored = Device.from_dict(d)
        self.assertEqual(restored.sys_descr, 'MikroTik RouterOS 7.12')
        self.assertEqual(restored.uptime, '42 days')
        self.assertEqual(restored.interfaces[1].alias, 'Uplink to ISP')
        self.assertEqual(restored.interfaces[1].descr, 'GigabitEthernet1')
        self.assertEqual(restored.interfaces[2].oper_status, 'down')
        self.assertEqual(len(restored.lldp_neighbors), 1)
        self.assertEqual(restored.lldp_neighbors[0].remote_sys_name, 'Edge-Rtr')

        # Test dialogs apply dark theme
        dlg = DeviceDetailDialog(dev)
        self.assertEqual(dlg.styleSheet(), _DARK_DIALOG_STYLE)
        link_dlg = LinkCreationDialog('A', [], 'B', [])
        self.assertEqual(link_dlg.styleSheet(), _DARK_DIALOG_STYLE)
        grp_dlg = GroupDevicesDialog([dev])
        self.assertEqual(grp_dlg.styleSheet(), _DARK_DIALOG_STYLE)
        edit_dlg = LinkEditDialog('A', 'p1', 'B', 'p2')
        self.assertEqual(edit_dlg.styleSheet(), _DARK_DIALOG_STYLE)

    def test_legacy_map_lldp_neighbor_reconstruction(self):
        """Verify that legacy maps with empty lldp_neighbors reconstruct them from links."""
        import sys
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance() or QApplication(sys.argv)
        from balenolib.topology.gui.detail import DeviceDetailDialog

        # Simulate legacy map dict where lldp_neighbors is empty or omitted
        legacy_data = {
            'version': 3,
            'devices': {
                'dev1': {
                    'id': 'dev1', 'ip': '10.0.0.1', 'hostname': 'Switch1',
                    'role': 'switch', 'chassis_id': '00:11:22:33:44:55',
                    'interfaces': {'1': {'name': 'Gi0/1', 'descr': '', 'alias': '', 'oper_status': 'up'}},
                    'lldp_neighbors': [],
                },
                'dev2': {
                    'id': 'dev2', 'ip': '10.0.0.2', 'hostname': 'Switch2',
                    'role': 'switch', 'chassis_id': '66:77:88:99:AA:BB',
                    'interfaces': {'1': {'name': 'Gi0/24', 'descr': '', 'alias': '', 'oper_status': 'up'}},
                    'lldp_neighbors': [],
                }
            },
            'links': [
                {
                    'source_id': 'dev1', 'source_port': 'Gi0/1',
                    'target_id': 'dev2', 'target_port': 'Gi0/24',
                    'source_ifindex': 1, 'lag': False, 'weight': 1, 'status': 'up'
                }
            ]
        }

        graph = TopologyGraph.from_dict(legacy_data)
        d1 = graph.devices['dev1']
        d2 = graph.devices['dev2']

        # Both devices must have reconstructed their lldp_neighbors from the link
        self.assertEqual(len(d1.lldp_neighbors), 1)
        self.assertEqual(d1.lldp_neighbors[0].local_port_name, 'Gi0/1')
        self.assertEqual(d1.lldp_neighbors[0].remote_sys_name, 'Switch2')
        self.assertEqual(d1.lldp_neighbors[0].remote_port_id, 'Gi0/24')
        self.assertEqual(d1.lldp_neighbors[0].remote_chassis_id, '66:77:88:99:AA:BB')
        self.assertEqual(d1.lldp_neighbors[0].remote_mgmt_addr, '10.0.0.2')

        self.assertEqual(len(d2.lldp_neighbors), 1)
        self.assertEqual(d2.lldp_neighbors[0].local_port_name, 'Gi0/24')
        self.assertEqual(d2.lldp_neighbors[0].remote_sys_name, 'Switch1')
        self.assertEqual(d2.lldp_neighbors[0].remote_port_id, 'Gi0/1')
        self.assertEqual(d2.lldp_neighbors[0].remote_chassis_id, '00:11:22:33:44:55')
        self.assertEqual(d2.lldp_neighbors[0].remote_mgmt_addr, '10.0.0.1')

        # Test that DeviceDetailDialog shows the reconstructed neighbor in LLDP tab
        dlg = DeviceDetailDialog(d1, graph=graph)
        tabs = dlg.findChild(QApplication.instance().allWidgets()[0].__class__, '')
        # Verify dialog table has row populated
        from PyQt6.QtWidgets import QTableWidget
        tables = dlg.findChildren(QTableWidget)
        self.assertGreaterEqual(len(tables), 2)  # Interfaces and Neighbors
        # The neighbors table should have 1 row
        nbr_table = next(t for t in tables if t.horizontalHeaderItem(0) and t.horizontalHeaderItem(0).text() == 'Local Port')
        self.assertEqual(nbr_table.rowCount(), 1)
        self.assertEqual(nbr_table.item(0, 0).text(), 'Gi0/1')
        self.assertEqual(nbr_table.item(0, 1).text(), 'Switch2')
        self.assertEqual(nbr_table.item(0, 2).text(), 'Gi0/24')

    def test_line_thickness_and_column_resize_and_confirm_deletion(self):
        """Test edge line thickness mapping, interactive column resize mode, and deletion confirmation."""
        import sys
        from PyQt6.QtWidgets import QApplication, QHeaderView, QMessageBox, QTableWidget
        from balenolib.topology.gui.view import EdgeItem, TopologyView
        from balenolib.topology.gui.detail import DeviceDetailDialog
        from balenolib.topology.models import PortLink, Device, DeviceRole, TopologyGraph
        from balenolib.topology.actions import TopologyActions

        app = QApplication.instance() or QApplication(sys.argv)

        # 1. Test EdgeItem line thickness mapping
        from balenolib.topology.gui.view import NodeItem
        d_src = Device(id='s1', ip='10.0.0.1', hostname='S1')
        d_tgt = Device(id='s2', ip='10.0.0.2', hostname='S2')
        n_src = NodeItem(d_src)
        n_tgt = NodeItem(d_tgt)
        link = PortLink(source_id='s1', target_id='s2', source_port='p1', target_port='p2', weight=1)
        edge = EdgeItem(link, n_src, n_tgt)
        self.assertEqual(edge._pen_width(), 1.0)
        self.assertEqual(edge._pen().widthF(), 1.0)

        link.weight = 3
        self.assertEqual(edge._pen_width(), 3.0)
        self.assertEqual(edge._pen().widthF(), 3.0)

        link.weight = 5
        self.assertEqual(edge._pen_width(), 6.0)
        self.assertEqual(edge._pen().widthF(), 6.0)

        # 2. Test DeviceDetailDialog tables have Interactive resize mode
        dev = Device(id='dev_test', ip='10.0.0.1', hostname='Router1', role=DeviceRole.ROUTER)
        dlg = DeviceDetailDialog(dev, graph=TopologyGraph())
        tables = dlg.findChildren(QTableWidget)
        self.assertGreaterEqual(len(tables), 2)
        for table in tables:
            self.assertEqual(table.horizontalHeader().sectionResizeMode(0), QHeaderView.ResizeMode.Interactive)
            self.assertFalse(table.horizontalHeader().stretchLastSection())

        # 3. Test Deletion confirmation dialog
        view = TopologyView()
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Yes):
            self.assertTrue(view._confirm_deletion("Remover?"))

        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.No):
            self.assertFalse(view._confirm_deletion("Remover?"))

        # 4. Test TopologyActions._remove_nodes respects cancellation
        main_win = MagicMock()
        main_win.topology_page.view = view
        view.remove_nodes = MagicMock()

        # When user cancels (exec -> No)
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.No):
            TopologyActions._remove_nodes(main_win, [dev])
            view.remove_nodes.assert_not_called()

        # When user confirms (exec -> Yes)
        with patch.object(QMessageBox, 'exec', return_value=QMessageBox.StandardButton.Yes):
            TopologyActions._remove_nodes(main_win, [dev])
            view.remove_nodes.assert_called_once_with([dev])

    def test_default_thickness_and_lldp_thickness(self):
        """Verify that default link/node thickness is 2 and LLDP-detected devices/links have thickness 1."""
        from balenolib.topology.models import PortLink, Device, DeviceRole, LldpNeighbor
        from balenolib.topology.engine import TopologyEngine
        from balenolib.topology.gui.view import EdgeItem, NodeItem

        # 1. Default PortLink weight is 2
        default_link = PortLink(source_id='a', target_id='b', source_port='p1', target_port='p2')
        self.assertEqual(default_link.weight, 2)

        d1 = Device(id='d1', ip='10.0.0.1', hostname='Seed1')
        d2 = Device(id='d2', ip='10.0.0.2', hostname='Seed2')
        n1 = NodeItem(d1)
        n2 = NodeItem(d2)
        edge = EdgeItem(default_link, n1, n2)
        self.assertEqual(edge._pen_width(), 2.0)

        # 2. TopologyEngine assigns weight=2 to seed links and weight=1 to LLDP neighbor links
        # d1 and d2 in seed network 10.0.0.0/24
        # d3 in 192.168.1.1 (LLDP neighbor)
        d3 = Device(id='d3', ip='192.168.1.1', hostname='Neighbor3')
        d1.lldp_neighbors.append(LldpNeighbor(
            local_port_name='Gi0/1', remote_sys_name='Seed2', remote_port_id='Gi0/1',
            remote_mgmt_addr='10.0.0.2', remote_chassis_id='d2'
        ))
        d1.lldp_neighbors.append(LldpNeighbor(
            local_port_name='Gi0/2', remote_sys_name='Neighbor3', remote_port_id='Gi0/24',
            remote_mgmt_addr='192.168.1.1', remote_chassis_id='d3'
        ))

        engine = TopologyEngine()
        graph = engine.build([d1, d2, d3], seed_networks=['10.0.0.0/24'])

        # Seed1 (10.0.0.1) is layer 1, Seed2 (10.0.0.2) is layer 1
        # Neighbor3 (192.168.1.1) is layer 2
        self.assertEqual(graph.devices['d1'].layer, 1)
        self.assertEqual(graph.devices['d2'].layer, 1)
        self.assertEqual(graph.devices['d3'].layer, 2)

        # Link between d1 and d2 (both seeds) -> weight 2 (default)
        link_seed = next(l for l in graph.links if l.touches('d1') and l.touches('d2'))
        self.assertEqual(link_seed.weight, 2)

        # Link between d1 and d3 (LLDP neighbor) -> weight 1
        link_lldp = next(l for l in graph.links if l.touches('d1') and l.touches('d3'))
        self.assertEqual(link_lldp.weight, 1)

        # 3. NodeItem border thickness
        node_seed = NodeItem(graph.devices['d1'])
        node_lldp = NodeItem(graph.devices['d3'])

        # Seeds have layer=1 (border width 2.0), LLDP neighbors have layer>1 (border width 1.0)
        is_seed_lldp = getattr(node_seed.device, 'layer', 1) > 1
        self.assertFalse(is_seed_lldp)

        is_nbr_lldp = getattr(node_lldp.device, 'layer', 1) > 1
        self.assertTrue(is_nbr_lldp)

    def test_context_menu_icons_and_ping_suboptions(self):
        """Verify device context menu has icons for Device Type, Layer, Ping and 3 ping sub-options."""
        from PyQt6.QtWidgets import QApplication, QMenu
        from balenolib.topology.actions import TopologyActions, _ICONS

        app = QApplication.instance() or QApplication([])

        class MockMainWindow:
            def __init__(self):
                self.config = MagicMock()
                self.switch_tab = MagicMock()
                self.traceroute_target_input = MagicMock()
                self.traceroute_port_input = MagicMock()
                self._traceroute_method_btns = {}
                self._traceroute_method_changed = MagicMock()
                self._start_ping = MagicMock()

            def get_icon_path(self, name):
                base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                p = os.path.join(base, 'assets', 'icons', name)
                return p if os.path.exists(p) else None

        main_win = MockMainWindow()

        # 1. Verify icons exist and load as valid QIcons
        for icon_key in ('ping', 'ping_icmp', 'ping_tcp80', 'ping_tcp22', 'device_type', 'layer'):
            self.assertIn(icon_key, _ICONS)
            ico = TopologyActions._icon(main_win, icon_key)
            self.assertIsNotNone(ico)
            self.assertFalse(ico.isNull(), f'Icon for {icon_key} must not be null')

        # 2. Inspect menu structure
        dev = Device(id='test_dev', ip='192.168.10.1', hostname='TestHost')
        captured_menus = []

        def mock_exec_capture(menu_obj, pos=None):
            captured_menus.append(menu_obj)
            return None

        with patch.object(QMenu, 'exec', mock_exec_capture):
            TopologyActions.show_node_menu(main_win, dev, None)

        self.assertEqual(len(captured_menus), 1)
        menu = captured_menus[0]

        # Device Type submenu has icon
        dev_type_act = next(a for a in menu.actions() if 'Device Type' in a.text())
        self.assertIsNotNone(dev_type_act.menu())
        self.assertFalse(dev_type_act.icon().isNull())

        # Layer submenu has icon
        layer_act = next(a for a in menu.actions() if 'Layer' in a.text())
        self.assertIsNotNone(layer_act.menu())
        self.assertFalse(layer_act.icon().isNull())

        # Ping submenu has icon and 3 sub-actions with icons
        ping_act = next(a for a in menu.actions() if a.text() == 'Ping')
        ping_menu = ping_act.menu()
        self.assertIsNotNone(ping_menu)
        self.assertFalse(ping_act.icon().isNull())

        ping_sub_actions = ping_menu.actions()
        ping_sub_labels = [a.text() for a in ping_sub_actions]
        self.assertEqual(ping_sub_labels, ['Ping (ICMP)', 'Ping (TCP 80)', 'Ping (TCP 22)'])
        for sub_act in ping_sub_actions:
            self.assertFalse(sub_act.icon().isNull(), f'Sub-action {sub_act.text()} must have an icon')

        # 3. Test selection dispatch
        from PyQt6.QtGui import QAction

        # ICMP dispatch
        def exec_icmp(menu_self, pos=None):
            return next(a for a in menu_self.findChildren(QAction) if 'ICMP' in a.text())

        with patch.object(QMenu, 'exec', exec_icmp):
            with patch.object(TopologyActions, '_invoke_ping') as mock_invoke:
                TopologyActions.show_node_menu(main_win, dev, None)
                mock_invoke.assert_called_once_with(main_win, dev, method='icmp')

        # TCP 80 dispatch
        def exec_tcp80(menu_self, pos=None):
            return next(a for a in menu_self.findChildren(QAction) if 'TCP 80' in a.text())

        with patch.object(QMenu, 'exec', exec_tcp80):
            with patch.object(TopologyActions, '_invoke_ping') as mock_invoke:
                TopologyActions.show_node_menu(main_win, dev, None)
                mock_invoke.assert_called_once_with(main_win, dev, method='tcp', port=80)

        # TCP 22 dispatch
        def exec_tcp22(menu_self, pos=None):
            return next(a for a in menu_self.findChildren(QAction) if 'TCP 22' in a.text())

        with patch.object(QMenu, 'exec', exec_tcp22):
            with patch.object(TopologyActions, '_invoke_ping') as mock_invoke:
                TopologyActions.show_node_menu(main_win, dev, None)
                mock_invoke.assert_called_once_with(main_win, dev, method='tcp', port=22)


if __name__ == '__main__':
    unittest.main()


