#!/usr/bin/env python3
"""Unit tests for topology performance optimizations:
- Frustum/viewport culling of link animations
- Dynamic pause during mouse pan/drag interaction
- Minimap decoupling (timer removal, NoViewportUpdate, static links)
- DeviceCoordinateCache on NodeItem
- Level of Detail (LOD) on EdgeItem
- Link animation toggle button and config persistence
- OpenGL viewport fallback safety
"""

import unittest
from unittest.mock import MagicMock, patch

from PyQt6.QtCore import QPointF, QRectF, Qt
from PyQt6.QtGui import QFont, QPainter, QTransform
from PyQt6.QtWidgets import QApplication, QGraphicsItem, QGraphicsView, QStyleOptionGraphicsItem

# Ensure headless offscreen application instance exists
app = QApplication.instance() or QApplication(['test', '-platform', 'offscreen'])

from balenolib.config import ConfigManager
from balenolib.topology.models import Device, DeviceRole, Interface, PortLink, TopologyGraph
from balenolib.topology.gui.view import TopologyView, TopologyScene, NodeItem, EdgeItem, Minimap
from balenolib.topology.tab import TopologyTab


class TestTopologyPerformance(unittest.TestCase):

    def setUp(self):
        self.dev1 = Device(id='dev1', hostname='Switch-A', role=DeviceRole.SWITCH, status='up')
        self.dev2 = Device(id='dev2', hostname='Switch-B', role=DeviceRole.SWITCH, status='up')
        self.dev3 = Device(id='dev3', hostname='Core-C', role=DeviceRole.CORE, status='up')
        self.node1 = NodeItem(self.dev1)
        self.node2 = NodeItem(self.dev2)
        self.node3 = NodeItem(self.dev3)

    def test_node_item_device_coordinate_cache(self):
        """NodeItem must enable DeviceCoordinateCache to avoid vector redraws during camera pan."""
        self.assertEqual(self.node1.cacheMode(), QGraphicsItem.CacheMode.DeviceCoordinateCache)
        self.assertEqual(self.node2.cacheMode(), QGraphicsItem.CacheMode.DeviceCoordinateCache)

    def test_edge_item_lod_simplification(self):
        """EdgeItem.paint must skip text rendering when Level of Detail (LOD) is < 0.5."""
        link = PortLink(
            source_id='dev1', target_id='dev2',
            source_port='Gi0/1', target_port='Gi0/2'
        )
        edge = EdgeItem(link, self.node1, self.node2)

        # Mock option with LOD < 0.5
        mock_option_low = MagicMock(spec=QStyleOptionGraphicsItem)
        mock_option_low.levelOfDetailFromTransform.return_value = 0.3

        painter_low = MagicMock(spec=QPainter)
        painter_low.font.return_value = QFont('Monospace', 7)
        edge.paint(painter_low, mock_option_low)
        # In low LOD (< 0.5), drawText should not be called
        painter_low.drawText.assert_not_called()

        # Mock option with LOD >= 0.5
        mock_option_high = MagicMock(spec=QStyleOptionGraphicsItem)
        mock_option_high.levelOfDetailFromTransform.return_value = 1.0

        painter_high = MagicMock(spec=QPainter)
        painter_high.font.return_value = QFont('Monospace', 7)
        edge.paint(painter_high, mock_option_high)
        # In normal/high LOD, drawText should be called for port labels
        self.assertTrue(painter_high.drawText.called)

    def test_minimap_decoupling_and_static_render(self):
        """Minimap must not use continuous 100ms polling, must set NoViewportUpdate and render static lines."""
        view = TopologyView()
        minimap = view.minimap

        # Timer must not exist on minimap
        self.assertFalse(hasattr(minimap, '_timer'))
        # Must have NoViewportUpdate so scene dirty updates don't cause automatic minimap repaints
        self.assertEqual(minimap.viewportUpdateMode(), QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
        # Viewport must be marked as minimap viewport
        self.assertTrue(getattr(minimap.viewport(), '_is_minimap_viewport', False))

        # Test static line fast path in EdgeItem.paint for minimap
        link = PortLink(
            source_id='dev1', target_id='dev2',
            source_port='Gi0/1', target_port='Gi0/2'
        )
        edge = EdgeItem(link, self.node1, self.node2)
        mock_painter = MagicMock(spec=QPainter)
        mock_widget = MagicMock()
        mock_widget._is_minimap_viewport = True

        edge.paint(mock_painter, None, mock_widget)
        # Must draw path/line directly without labels or text
        mock_painter.drawPath.assert_called_once()
        mock_painter.drawText.assert_not_called()

    def test_viewport_culling_in_tick_animation(self):
        """_tick_animation must only update active edges that intersect visible scene bounds."""
        view = TopologyView()
        view.resize(800, 600)
        view.show()

        scene = view._scene
        # Place node1 and node2 inside view (near 100, 100)
        self.node1.setPos(100, 100)
        self.node2.setPos(200, 100)
        scene.addItem(self.node1)
        scene.addItem(self.node2)
        scene.node_items['dev1'] = self.node1
        scene.node_items['dev2'] = self.node2

        # Place node3 far outside visible view (e.g. 10000, 10000)
        self.node3.setPos(10000, 10000)
        node4 = NodeItem(Device(id='dev4', hostname='Core-D', role=DeviceRole.CORE, status='up'))
        node4.setPos(10100, 10000)
        scene.addItem(self.node3)
        scene.addItem(node4)
        scene.node_items['dev3'] = self.node3
        scene.node_items['dev4'] = node4

        # In-view edge
        link_in = PortLink(source_id='dev1', target_id='dev2', source_port='p1', target_port='p2')
        edge_in = EdgeItem(link_in, self.node1, self.node2)
        edge_in.state = 'active'
        scene.addItem(edge_in)
        scene.edge_items.append(edge_in)

        # Far out-of-view edge
        link_out = PortLink(source_id='dev3', target_id='dev4', source_port='p3', target_port='p4')
        edge_out = EdgeItem(link_out, self.node3, node4)
        edge_out.state = 'active'
        scene.addItem(edge_out)
        scene.edge_items.append(edge_out)

        # Record initial offsets
        initial_offset_in = edge_in._dash_offset
        initial_offset_out = edge_out._dash_offset

        # Mock edge updates to verify calls
        edge_in.update = MagicMock()
        edge_out.update = MagicMock()

        # Run one tick of animation
        view._interaction_active = False
        view._animation_enabled = True
        view._tick_animation()

        # In-view edge must be updated
        edge_in.update.assert_called_once()
        self.assertNotEqual(edge_in._dash_offset, initial_offset_in)

        # Out-of-view edge must be culled and NOT updated
        edge_out.update.assert_not_called()
        self.assertEqual(edge_out._dash_offset, initial_offset_out)

    def test_animation_pause_during_interaction(self):
        """Animation ticks must be ignored while interaction (pan or drag) is active."""
        view = TopologyView()
        view.resize(800, 600)
        view.show()

        scene = view._scene
        self.node1.setPos(100, 100)
        self.node2.setPos(200, 100)
        scene.addItem(self.node1)
        scene.addItem(self.node2)
        scene.node_items['dev1'] = self.node1
        scene.node_items['dev2'] = self.node2

        link = PortLink(source_id='dev1', target_id='dev2', source_port='p1', target_port='p2')
        edge = EdgeItem(link, self.node1, self.node2)
        edge.state = 'active'
        scene.addItem(edge)
        scene.edge_items.append(edge)

        edge.update = MagicMock()

        # Simulate active interaction (user dragging or panning)
        view._interaction_active = True
        view._tick_animation()

        # No edge update should happen during interaction
        edge.update.assert_not_called()

        # Interaction ended
        view._interaction_active = False
        view._tick_animation()
        edge.update.assert_called_once()

    def test_set_animation_enabled_toggle(self):
        """set_animation_enabled(False) stops timer and resets dash offset; True restarts timer."""
        view = TopologyView()
        link = PortLink(source_id='dev1', target_id='dev2', source_port='p1', target_port='p2')
        edge = EdgeItem(link, self.node1, self.node2)
        edge.state = 'active'
        edge._dash_offset = 5.0
        view._scene.edge_items.append(edge)

        # Disable animation
        view.set_animation_enabled(False)
        self.assertFalse(view._animation_enabled)
        self.assertFalse(view._anim_timer.isActive())
        self.assertEqual(edge._dash_offset, 0.0)

        # Re-enable animation
        view.set_animation_enabled(True)
        self.assertTrue(view._animation_enabled)
        self.assertTrue(view._anim_timer.isActive())

    def test_config_default_and_tab_toggle_button(self):
        """ConfigManager must have 'topology_animate_links' default, and TopologyTab button toggles it."""
        config_mgr = ConfigManager()
        self.assertIn('topology_animate_links', config_mgr.defaults)
        self.assertTrue(config_mgr.defaults['topology_animate_links'])

        mock_config = MagicMock()
        mock_config.get_vuln_community_history.return_value = []
        config_store = {
            'topology_animate_links': True,
            'vuln_community_history': '[]',
        }
        def mock_get(k, d=None):
            if k in config_store:
                return config_store[k]
            return d if d is not None else ''
        mock_config.get.side_effect = mock_get
        mock_config.set.side_effect = lambda k, v: config_store.__setitem__(k, v)

        tab = TopologyTab(config_manager=mock_config)
        self.assertTrue(tab.anim_toggle_btn.isChecked())
        self.assertIn('Animate', tab.anim_toggle_btn.text())
        self.assertTrue(tab.view._animation_enabled)

        # Toggle button to OFF
        tab.anim_toggle_btn.setChecked(False)
        self.assertFalse(tab.view._animation_enabled)
        self.assertFalse(mock_config.set.call_args[0][1] if mock_config.set.called else True)
        self.assertFalse(config_store['topology_animate_links'])
        self.assertEqual(tab.anim_toggle_btn.text(), '▶ Animate')

        # Toggle button to ON
        tab.anim_toggle_btn.setChecked(True)
        self.assertTrue(tab.view._animation_enabled)
        self.assertTrue(config_store['topology_animate_links'])
        self.assertEqual(tab.anim_toggle_btn.text(), '⏸ Animate')

    def test_opengl_viewport_fallback_safety(self):
        """TopologyView must gracefully handle offscreen/fallback raster mode without crashing."""
        view = TopologyView()
        self.assertIsNotNone(view.viewport())
        # Viewport update mode should be valid
        self.assertIn(view.viewportUpdateMode(), [
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate,
            QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate,
        ])


if __name__ == '__main__':
    unittest.main()
