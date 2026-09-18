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


if __name__ == '__main__':
    unittest.main()
