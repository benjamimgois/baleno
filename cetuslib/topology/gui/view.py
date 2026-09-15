"""Interactive topology renderer — QGraphicsView scene in the style of
MikroTik The Dude / ZabFox.

Exposes :class:`TopologyView` and a convenience :func:`load_graph` that
populates the scene from a :class:`TopologyGraph`.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsScene,
    QGraphicsView,
)

from cetuslib.topology.models import Device, DeviceRole, PortLink, TopologyGraph
from cetuslib.topology.engine import TopologyEngine
from cetuslib.topology.persistence import (
    apply_layout, load_layout, save_layout, default_layout_path,
)

__all__ = ['TopologyView', 'TopologyScene', 'NodeItem', 'EdgeItem', 'load_graph']


# ── palette ───────────────────────────────────────────────────────────────
BG = QColor(13, 17, 23)          # #0D1117
GRID = QColor(22, 27, 34)        # subtle grid line
NODE_BG = QColor(22, 27, 34)     # #161B22
NODE_BORDER = QColor(48, 54, 61)  # #30363D
TEXT = QColor(201, 209, 217)     # #C9D1D9
TEXT_DIM = QColor(139, 148, 158)  # #8B949E
UP = QColor(63, 185, 80)         # #3FB950
DOWN = QColor(248, 81, 73)       # #F85149
UNKNOWN = QColor(139, 148, 158)
ACCENT = QColor(88, 166, 255)    # #58A6FF
EDGE = QColor(139, 148, 158)

ROLE_COLOR = {
    DeviceRole.CORE: QColor(88, 166, 255),
    DeviceRole.ROUTER: QColor(210, 153, 34),
    DeviceRole.SWITCH: QColor(88, 166, 255),
    DeviceRole.ACCESS: QColor(121, 192, 255),
    DeviceRole.SERVER: QColor(163, 113, 247),
    DeviceRole.AP: QColor(63, 185, 80),
    DeviceRole.HOST: QColor(201, 209, 217),
    DeviceRole.UNKNOWN: QColor(139, 148, 158),
}

# Hop-level colours: level 1 (seed network) = green, level 2 (LLDP neighbours)
# = gray, deeper levels = a dimmer slate so the hierarchy stays readable.
LEVEL_COLOR = {
    1: QColor(46, 160, 67),      # green
    2: QColor(139, 148, 158),    # gray
}


def level_color(level: int) -> QColor:
    return LEVEL_COLOR.get(level, QColor(110, 118, 129))


def _status_color(device: Device) -> QColor:
    if device.status == 'up':
        return UP
    if device.status == 'down':
        return DOWN
    return UNKNOWN


def draw_device_icon(painter: QPainter, center: QPointF, role: DeviceRole, color: QColor) -> None:
    """Draw a simple vector glyph for a device role inside its icon circle."""
    painter.save()
    painter.setPen(QPen(color, 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    r = 12.0
    if role in (DeviceRole.SWITCH, DeviceRole.CORE, DeviceRole.ACCESS):
        painter.drawRect(QRectF(center.x() - r, center.y() - r / 1.6, r * 2, r * 1.25))
        for i in range(4):
            y = center.y() - r / 2 + i * (r / 2.6)
            painter.drawLine(QPointF(center.x() - r, y), QPointF(center.x() - r + 3, y))
            painter.drawLine(QPointF(center.x() + r - 3, y), QPointF(center.x() + r, y))
    elif role == DeviceRole.ROUTER:
        painter.drawEllipse(QRectF(center.x() - r, center.y() - r, r * 2, r * 2))
        for ang in (45, 135, 225, 315):
            rad = math.radians(ang)
            x, y = math.cos(rad), math.sin(rad)
            painter.drawLine(
                QPointF(center.x() + x * r, center.y() + y * r),
                QPointF(center.x() + x * (r + 5), center.y() + y * (r + 5)))
    elif role == DeviceRole.SERVER:
        for i in range(3):
            y = center.y() - r + i * (r / 1.6) + 2
            painter.drawRect(QRectF(center.x() - r, y, r * 2, r / 2.4))
    elif role == DeviceRole.AP:
        painter.setBrush(color)
        painter.drawEllipse(QRectF(center.x() - 2, center.y() - 2, 4, 4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for i, rad in enumerate((5, 9, 13)):
            painter.drawArc(QRectF(center.x() - rad, center.y() - rad - 6, rad * 2, rad * 2), 200 * 16, 140 * 16)
    elif role == DeviceRole.HOST:
        painter.drawRect(QRectF(center.x() - r, center.y() - r + 4, r * 2, r * 1.2))
        painter.drawLine(QPointF(center.x() - 4, center.y() - r + 4),
                         QPointF(center.x() + 4, center.y() + r + 2))
        painter.drawLine(QPointF(center.x() - 7, center.y() + r + 2),
                         QPointF(center.x() + 7, center.y() + r + 2))
    else:
        f = QFont('Monospace', 12, QFont.Weight.Bold)
        painter.setFont(f)
        painter.drawText(QRectF(center.x() - r, center.y() - r, r * 2, r * 2),
                         Qt.AlignmentFlag.AlignCenter, '?')
    painter.restore()


class NodeItem(QGraphicsObject):
    """A device node. Movable, selectable; emits signals on move / double-click."""

    WIDTH = 170.0
    HEIGHT = 96.0
    moved = pyqtSignal(object)
    double_clicked = pyqtSignal(object)

    def __init__(self, device: Device):
        super().__init__()
        self.device = device
        self.edges: list[EdgeItem] = []
        # Level 2+ devices are less relevant: render smaller icons/fonts.
        self.scale = 1.0 if device.layer <= 1 else 0.72
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setToolTip(self._tooltip())
        self.setZValue(10)

    def _tooltip(self) -> str:
        d = self.device
        return (f"{d.label}\n{d.ip}\n{d.role.value} · {d.vendor} {d.model}\n"
                f"status: {d.status} · {d.latency_ms} ms")

    def add_edge(self, edge: EdgeItem) -> None:
        self.edges.append(edge)

    def boundingRect(self) -> QRectF:
        s = self.scale
        return QRectF(-self.WIDTH / 2 * s, -self.HEIGHT / 2 * s,
                      self.WIDTH * s, self.HEIGHT * s)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
            self.moved.emit(self.device)
        return super().itemChange(change, value)

    def mouseDoubleClickEvent(self, event) -> None:
        self.double_clicked.emit(self.device)
        super().mouseDoubleClickEvent(event)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.scale, self.scale)
        rect = QRectF(-self.WIDTH / 2, -self.HEIGHT / 2, self.WIDTH, self.HEIGHT)
        status = _status_color(self.device)
        border = status if self.isSelected() is False else ACCENT

        painter.setBrush(NODE_BG)
        pen = QPen(ACCENT if self.isSelected() else NODE_BORDER, 2 if self.isSelected() else 1.5)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

        # left accent bar coloured by hop level (green = seed, gray = neighbour)
        lvl_color = level_color(self.device.layer)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(lvl_color)
        painter.drawRoundedRect(QRectF(rect.left(), rect.top() + 10, 4, rect.height() - 20), 2, 2)

        # level badge (bottom-right)
        painter.setPen(lvl_color)
        painter.setFont(QFont('Sans', 7, QFont.Weight.Bold))
        painter.drawText(QRectF(rect.right() - 30, rect.bottom() - 15, 26, 12),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f'L{self.device.layer or 1}')

        # icon circle
        role_color = ROLE_COLOR.get(self.device.role, UNKNOWN)
        icon_center = QPointF(rect.left() + 32, 0)
        painter.setPen(QPen(QColor(30, 35, 42), 1))
        painter.setBrush(QColor(30, 35, 42))
        painter.drawEllipse(icon_center, 22, 22)
        draw_device_icon(painter, icon_center, self.device.role, role_color)

        x0 = rect.left() + 62
        fm = QFontMetricsF(QFont('Sans', 10, QFont.Weight.Bold))
        label = self.device.label
        if len(label) > 18:
            label = label[:17] + '…'
        painter.setPen(TEXT)
        painter.setFont(QFont('Sans', 10, QFont.Weight.Bold))
        painter.drawText(QPointF(x0, rect.top() + 26), label)

        painter.setFont(QFont('Monospace', 8))
        painter.setPen(TEXT_DIM)
        painter.drawText(QPointF(x0, rect.top() + 42), self.device.ip or self.device.id)

        painter.setFont(QFont('Sans', 8))
        painter.setPen(role_color)
        painter.drawText(QPointF(x0, rect.top() + 58), self.device.role.value.upper())

        # status dot + latency badge (top-right)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(status)
        painter.drawEllipse(QPointF(rect.right() - 10, rect.top() + 10), 4, 4)
        painter.setPen(status)
        painter.setFont(QFont('Monospace', 7))
        painter.drawText(QRectF(rect.right() - 64, rect.top() + 3, 50, 14),
                         Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         f"{self.device.latency_ms:.0f}ms")
        painter.restore()


class EdgeItem(QGraphicsPathItem):
    """A link between two nodes, labelled with both endpoint ports."""

    def __init__(self, link: PortLink, source: NodeItem, target: NodeItem, offset: int = 0):
        super().__init__()
        self.link = link
        self.source = source
        self.target = target
        self.offset = offset
        self.setZValue(0)
        self.setPen(QPen(EDGE if not link.lag else ACCENT, 1.5))
        source.add_edge(self)
        target.add_edge(self)
        self.update_path()

    def update_path(self) -> None:
        s = self.source.pos()
        t = self.target.pos()
        path = QPainterPath(s)
        if self.offset:
            mid = (s + t) / 2
            dx, dy = t.x() - s.x(), t.y() - s.y()
            length = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / length, dx / length
            ctrl = QPointF(mid.x() + nx * self.offset * 14, mid.y() + ny * self.offset * 14)
            path.quadTo(ctrl, t)
        else:
            path.lineTo(t)
        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        super().paint(painter, option, widget)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        s = self.source.pos()
        t = self.target.pos()
        mid = (s + t) / 2
        label = f"{self.link.source_port} ⟷ {self.link.target_port}"
        painter.setPen(TEXT_DIM)
        painter.setFont(QFont('Monospace', 7))
        bg = QColor(BG)
        fm = QFontMetricsF(painter.font())
        tw = fm.horizontalAdvance(label)
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(mid.x() - tw / 2 - 4, mid.y() - 8, tw + 8, 14), 3, 3)
        painter.setPen(TEXT_DIM)
        painter.drawText(QPointF(mid.x() - tw / 2, mid.y() + 3), label)


class TopologyScene(QGraphicsScene):
    """Scene holding node/edge items and their device graph."""

    node_double_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []
        self.visible_levels: Optional[set] = None
        self.setBackgroundBrush(BG)
        self.setSceneRect(-20000, -20000, 40000, 40000)

    def set_graph(self, graph: TopologyGraph, layout_mode: str = 'hierarchical',
                  positions: dict[str, tuple[float, float]] | None = None) -> None:
        self.clear()
        self.node_items = {}
        self.edge_items = []

        engine = TopologyEngine()
        if layout_mode == 'force':
            pos = engine.layout_force(graph)
        else:
            pos = engine.layout_hierarchical(graph)
        if positions:
            pos = apply_layout(graph, positions, pos)

        # nodes
        for device_id, device in graph.devices.items():
            node = NodeItem(device)
            x, y = pos.get(device_id, (0.0, 0.0))
            node.setPos(x, y)
            node.double_clicked.connect(self.node_double_clicked)
            self.addItem(node)
            self.node_items[device_id] = node

        # edges (offset parallel links in a LAG so they don't overlap)
        seen: dict[frozenset, int] = {}
        for link in graph.links:
            key = frozenset((link.source_id, link.target_id))
            offset = seen.get(key, 0)
            seen[key] = offset + 1 if link.lag else 0
            src = self.node_items.get(link.source_id)
            dst = self.node_items.get(link.target_id)
            if src and dst:
                edge = EdgeItem(link, src, dst, offset=offset if link.lag else 0)
                self.edge_items.append(edge)
                self.addItem(edge)

    def set_visible_levels(self, levels: Optional[set]) -> None:
        """Show only nodes/edges whose devices belong to ``levels``.

        ``None`` shows everything; an empty set hides everything.  An edge is
        visible only when both endpoints are visible.
        """
        self.visible_levels = levels
        if levels is None:
            for item in self.node_items.values():
                item.setVisible(True)
            for edge in self.edge_items:
                edge.setVisible(True)
            return

        for device_id, node in self.node_items.items():
            node.setVisible(node.device.layer in levels)
        for edge in self.edge_items:
            s = edge.source.device.layer in levels
            t = edge.target.device.layer in levels
            edge.setVisible(s and t)


class Minimap(QGraphicsView):
    """Small overview view showing the whole scene and the visible area."""

    def __init__(self, main_view: TopologyView):
        super().__init__(main_view)
        self.main_view = main_view
        self.setScene(main_view.scene())
        self.setFixedSize(200, 150)
        self.setInteractive(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setStyleSheet('background: #0D1117; border: 1px solid #30363d;')
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._refresh)
        self._timer.start(100)

    def _refresh(self) -> None:
        if self.scene() and self.scene().itemsBoundingRect().isValid():
            self.fitInView(self.scene().itemsBoundingRect(), Qt.AspectRatioMode.KeepAspectRatio)
        self.viewport().update()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawForeground(painter, rect)
        if not self.scene():
            return
        visible = self.main_view.mapToScene(self.main_view.viewport().rect()).boundingRect()
        painter.setPen(QPen(ACCENT, 1.5))
        painter.setBrush(QColor(88, 166, 255, 30))
        painter.drawRect(self._scene_to_view(visible))

    def _scene_to_view(self, scene_rect: QRectF) -> QRectF:
        tl = self.mapFromScene(scene_rect.topLeft())
        br = self.mapFromScene(scene_rect.bottomRight())
        return QRectF(float(tl.x()), float(tl.y()),
                      float(br.x() - tl.x()), float(br.y() - tl.y()))


class TopologyView(QGraphicsView):
    """Main topology canvas: wheel-zoom, pan, minimap overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = TopologyScene()
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        self._zoom = 1.0
        self.minimap = Minimap(self)
        self.layout_path = ''
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save_layout)

    def set_layout_path(self, path: str) -> None:
        """Enable/change automatic persistence of manual node positions."""
        self.layout_path = path

    def current_positions(self) -> dict[str, tuple[float, float]]:
        return {did: (it.pos().x(), it.pos().y())
                for did, it in self._scene.node_items.items()}

    def save_layout(self) -> None:
        """Write current node coordinates to ``layout_path`` (if set)."""
        if not self.layout_path:
            return
        graph = TopologyGraph()
        for device_id, item in self._scene.node_items.items():
            graph.add_device(item.device)
        save_layout(graph, self.current_positions(), self.layout_path)

    def _schedule_save(self, *args) -> None:
        if self.layout_path:
            self._save_timer.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_minimap()

    def _place_minimap(self) -> None:
        self.minimap.move(self.width() - self.minimap.width() - 10,
                          self.height() - self.minimap.height() - 10)
        self.minimap.raise_()

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom *= factor
        self._zoom = max(0.1, min(self._zoom, 8.0))
        self.scale(factor, factor)

    def load(self, graph: TopologyGraph, layout_mode: str = 'hierarchical') -> None:
        saved = load_layout(self.layout_path) if self.layout_path else {}
        self._scene.set_graph(graph, layout_mode, saved)
        for item in self._scene.node_items.values():
            item.moved.connect(self._schedule_save)
        self.fit_in_view()

    def fit_in_view(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isValid():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = self.transform().m11()

    def set_visible_levels(self, levels: Optional[set]) -> None:
        """Filter the canvas to the given hop levels (None = show all)."""
        self._scene.set_visible_levels(levels)
        self._fit_visible()

    def _fit_visible(self) -> None:
        """Fit the view to the currently visible node items."""
        rect = QRectF()
        first = True
        for item in self._scene.node_items.values():
            if item.isVisible():
                r = item.sceneBoundingRect()
                rect = r if first else rect.united(r)
                first = False
        if first:
            return
        self.fitInView(rect.adjusted(-80, -80, 80, 80),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def switch_layout(self, layout_mode: str) -> None:
        """Re-layout keeping the current graph (positions are recomputed)."""
        graph = TopologyGraph()
        for device_id, item in self._scene.node_items.items():
            graph.add_device(item.device)
        # rebuild links from existing edge items
        engine = TopologyEngine()
        pos = (engine.layout_force(graph) if layout_mode == 'force'
               else engine.layout_hierarchical(graph))
        for device_id, item in self._scene.node_items.items():
            item.setPos(*pos.get(device_id, (0.0, 0.0)))
        self.fit_in_view()


def load_graph(graph: TopologyGraph, layout_mode: str = 'hierarchical') -> TopologyView:
    """Create a standalone :class:`TopologyView` populated with ``graph``."""
    view = TopologyView()
    view.load(graph, layout_mode)
    view.resize(1000, 700)
    return view
