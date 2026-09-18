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
        self.assertEqual(tab.anim_toggle_btn.text(), '')
        self.assertFalse(tab.anim_toggle_btn.icon().isNull())
        self.assertIn('Pause', tab.anim_toggle_btn.toolTip())
        self.assertTrue(tab.view._animation_enabled)

        # Toggle button to OFF
        tab.anim_toggle_btn.setChecked(False)
        self.assertFalse(tab.view._animation_enabled)
        self.assertFalse(mock_config.set.call_args[0][1] if mock_config.set.called else True)
        self.assertFalse(config_store['topology_animate_links'])
        self.assertEqual(tab.anim_toggle_btn.text(), '')
        self.assertFalse(tab.anim_toggle_btn.icon().isNull())
        self.assertIn('Resume', tab.anim_toggle_btn.toolTip())

        # Toggle button to ON
        tab.anim_toggle_btn.setChecked(True)
        self.assertTrue(tab.view._animation_enabled)
        self.assertTrue(config_store['topology_animate_links'])
        self.assertEqual(tab.anim_toggle_btn.text(), '')
        self.assertFalse(tab.anim_toggle_btn.icon().isNull())
        self.assertIn('Pause', tab.anim_toggle_btn.toolTip())

    def test_toolbar_icon_only_buttons_and_detach_flow(self):
        """Verify Undo, Redo, Animate and Detach buttons have no text, valid icons, and detach/reattach works."""
        from PyQt6.QtWidgets import QStackedWidget
        from balenolib.topology.tab import DetachedTopologyWindow

        mock_config = MagicMock()
        mock_config.get.side_effect = lambda k, d='': True if k == 'topology_animate_links' else ('["public"]' if k == 'vuln_community_history' else d)
        mock_config.get_vuln_community_history.return_value = ['public']

        class MockMainWindow:
            def __init__(self):
                self.content_stack = QStackedWidget()
                self.config = mock_config
                self.switch_tab = MagicMock()

        main_win = MockMainWindow()
        tab = TopologyTab(config_manager=mock_config, main_window=main_win)
        main_win.content_stack.addWidget(tab)

        # 1. Undo / Redo are icon-only
        self.assertEqual(tab.undo_btn.text(), '')
        self.assertFalse(tab.undo_btn.icon().isNull())
        self.assertEqual(tab.redo_btn.text(), '')
        self.assertFalse(tab.redo_btn.icon().isNull())

        # 2. Detach button exists and is icon-only
        self.assertTrue(hasattr(tab, 'detach_btn'))
        self.assertEqual(tab.detach_btn.text(), '')
        self.assertFalse(tab.detach_btn.icon().isNull())

        # 3. Test detaching into DetachedTopologyWindow
        tab.detach_btn.click()
        self.assertIsNotNone(tab._detached_window)
        self.assertIsInstance(tab._detached_window, DetachedTopologyWindow)
        self.assertEqual(tab.window(), tab._detached_window)
        self.assertIsNotNone(tab._placeholder_widget)
        self.assertEqual(main_win.content_stack.currentWidget(), tab._placeholder_widget)

        # 4. Test reattaching via detach_btn
        tab.detach_btn.click()
        self.assertIsNone(tab._detached_window)
        self.assertIsNone(tab._placeholder_widget)
        self.assertGreaterEqual(main_win.content_stack.indexOf(tab), 0)

        # 5. Test detaching and reattaching via window closeEvent
        tab._detach_to_window()
        self.assertIsNotNone(tab._detached_window)
        tab._detached_window.close()
        self.assertIsNone(tab._detached_window)
        self.assertGreaterEqual(main_win.content_stack.indexOf(tab), 0)

    def test_opengl_viewport_fallback_safety(self):
        """TopologyView must gracefully handle offscreen/fallback raster mode without crashing."""
        view = TopologyView()
        self.assertIsNotNone(view.viewport())
        # Viewport update mode should be valid
        self.assertIn(view.viewportUpdateMode(), [
            QGraphicsView.ViewportUpdateMode.FullViewportUpdate,
            QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate,
        ])

    def test_default_viewport_raster_and_pen_round_cap(self):
        """Default viewport must be native raster QWidget, and EdgeItem pen must use RoundCap."""
        view = TopologyView()
        self.assertFalse(view._opengl_active)
        self.assertEqual(type(view.viewport()).__name__, 'QWidget')
        self.assertEqual(view.viewportUpdateMode(), QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)

        link = PortLink(source_id='dev1', target_id='dev2', source_port='Gi0/1', target_port='Gi0/2')
        edge = EdgeItem(link, self.node1, self.node2)
        # Active state RoundCap
        pen_active = edge._pen()
        self.assertEqual(pen_active.capStyle(), Qt.PenCapStyle.RoundCap)
        # Down state RoundCap
        edge.state = 'down'
        pen_down = edge._pen()
        self.assertEqual(pen_down.capStyle(), Qt.PenCapStyle.RoundCap)

    def test_fps_overlay_and_toast_notifications(self):
        """TopologyTab F11 and F12 shortcuts must toggle OpenGL mode and FPS overlay with Toast feedback."""
        mock_config = MagicMock()
        mock_config.get.side_effect = lambda k, d='': True if k == 'topology_animate_links' else ('["public"]' if k == 'vuln_community_history' else d)
        mock_config.get_vuln_community_history.return_value = ['public']

        tab = TopologyTab(config_manager=mock_config)
        tab.show()
        view = tab.view

        # Overlays exist and start hidden
        self.assertTrue(hasattr(view, '_fps_overlay'))
        self.assertTrue(hasattr(view, '_toast'))
        self.assertFalse(view._fps_overlay.isVisible())

        # Test F12 toggle on
        tab._f12_shortcut.activated.emit()
        self.assertTrue(view._fps_overlay.isVisible())
        self.assertIn('Contador de FPS: Ativado', view._toast.text())

        # Test paintEvent records frame
        view._fps_overlay.record_frame()
        self.assertGreater(len(view._fps_overlay._frame_times), 0)

        # Test F12 toggle off
        tab._f12_shortcut.activated.emit()
        self.assertFalse(view._fps_overlay.isVisible())
        self.assertIn('Contador de FPS: Desativado', view._toast.text())

        # Test F11 toggle OpenGL
        tab._f11_shortcut.activated.emit()
        # In offscreen platform (headless test environment), offscreen toast is displayed or toggled
        self.assertTrue(view._toast.isVisible())

        # Test show_toast directly
        view.show_toast('Teste Toast', '#58A6FF')
        self.assertTrue(view._toast.isVisible())
        self.assertIn('Teste Toast', view._toast.text())


if __name__ == '__main__':
    unittest.main()
