"""Interactive topology renderer — QGraphicsView scene in the style of
MikroTik The Dude / ZabFox.

Exposes :class:`TopologyView` and a convenience :func:`load_graph` that
populates the scene from a :class:`TopologyGraph`.
"""

from __future__ import annotations

import math
import os
import sys
from typing import Optional

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QImage, QPainter, QPainterPath, QPen, QPolygonF,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsScene,
    QGraphicsView,
)

from cetuslib.topology.models import (
    Device, DeviceRole, Interface, PortLink, TopologyGraph,
)
from cetuslib.topology.engine import TopologyEngine, normalize_port
from cetuslib.topology.persistence import (
    apply_layout, load_layout, load_group_layout, save_layout, default_layout_path,
)

__all__ = ['TopologyView', 'TopologyScene', 'NodeItem', 'EdgeItem',
           'GroupNodeItem', 'GroupLinkItem', 'load_graph', 'role_renderer']

# MIME type used to drag a device role from the palette onto the canvas.
DEVICE_MIME = 'application/x-cetus-topology-device'


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
GRID_LINE = QColor(30, 36, 44)   # very faint grid, barely lighter than BG

ROLE_COLOR = {
    DeviceRole.CORE: QColor(88, 166, 255),
    DeviceRole.ROUTER: QColor(210, 153, 34),
    DeviceRole.SWITCH: QColor(88, 166, 255),
    DeviceRole.ACCESS: QColor(121, 192, 255),
    DeviceRole.FIREWALL: QColor(230, 126, 34),
    DeviceRole.SERVER: QColor(163, 113, 247),
    DeviceRole.AP: QColor(63, 185, 80),
    DeviceRole.CAMERA: QColor(210, 153, 34),
    DeviceRole.CLOUD: QColor(88, 166, 255),
    DeviceRole.HOST: QColor(201, 209, 217),
    DeviceRole.UNKNOWN: QColor(139, 148, 158),
}

# Realistic device icons (assets/icons/network-icons) keyed by role.
ROLE_ICON = {
    DeviceRole.CORE: 'switch_l3.svg',
    DeviceRole.ROUTER: 'router.svg',
    DeviceRole.SWITCH: 'switch_l2.svg',
    DeviceRole.ACCESS: 'switch_l2.svg',
    DeviceRole.FIREWALL: 'firewall.svg',
    DeviceRole.SERVER: 'server.svg',
    DeviceRole.AP: 'wifi.svg',
    DeviceRole.CAMERA: 'camera.svg',
    DeviceRole.CLOUD: 'internet.svg',
    DeviceRole.HOST: 'pc.svg',
    DeviceRole.UNKNOWN: 'unknown.svg',
}

_NETWORK_ICON_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), 'assets', 'icons',
        'network-icons'),
    os.path.join(getattr(sys, '_MEIPASS', ''), 'assets', 'icons', 'network-icons'),
    '/app/share/io.github.benjamimgois.cetus/icons/network-icons',
    '/usr/share/cetus/icons/network-icons',
]

_renderer_cache: dict[str, Optional[QSvgRenderer]] = {}


def _renderer_for_name(name: str) -> Optional[QSvgRenderer]:
    if name in _renderer_cache:
        return _renderer_cache[name]
    for base in _NETWORK_ICON_DIRS:
        path = os.path.join(base, name)
        if os.path.exists(path):
            renderer = QSvgRenderer(path)
            if renderer.isValid():
                _renderer_cache[name] = renderer
                return renderer
    _renderer_cache[name] = None
    return None


def role_renderer(role: DeviceRole) -> Optional[QSvgRenderer]:
    """Return a vector SVG renderer for a device role (None if unavailable)."""
    name = ROLE_ICON.get(role)
    return _renderer_for_name(name) if name else None


def device_renderer(device: Device) -> Optional[QSvgRenderer]:
    """Return a vector SVG renderer for a device's role (None if unavailable).

    QSvgRenderer keeps the artwork vector: it is rasterised at the exact paint
    size each frame, so the icon stays crisp at any zoom level (unlike a QIcon,
    which caches a fixed-resolution pixmap and pixelates when scaled).
    """
    return role_renderer(device.role)

# Hop-level colours: level 1 (seed network) = green, level 2 (LLDP neighbours)
# = gray, deeper levels = a dimmer slate so the hierarchy stays readable.
LEVEL_COLOR = {
    1: QColor(46, 160, 67),      # green
    2: QColor(139, 148, 158),    # gray
}


def level_color(level: int) -> QColor:
    return LEVEL_COLOR.get(level, QColor(110, 118, 129))


def _draw_grid(painter: QPainter, rect: QRectF, grid: float = 40.0) -> None:
    """Draw the faint alignment grid inside ``rect`` (scene coordinates)."""
    painter.setPen(QPen(GRID_LINE, 1))
    lines: list[QLineF] = []
    x = math.floor(rect.left() / grid) * grid
    while x < rect.right():
        lines.append(QLineF(x, rect.top(), x, rect.bottom()))
        x += grid
    y = math.floor(rect.top() / grid) * grid
    while y < rect.bottom():
        lines.append(QLineF(rect.left(), y, rect.right(), y))
        y += grid
    if lines:
        painter.drawLines(lines)


def _status_color(device: Device) -> QColor:
    if device.status == 'up':
        return UP
    if device.status == 'down':
        return DOWN
    return UNKNOWN


def _fmt_rate(bps: float) -> str:
    """Human-readable throughput: '0 Mbps', '123.4 Mbps', '1.25 Gbps'."""
    if bps <= 0:
        return '0 Mbps'
    if bps >= 1e9:
        return f'{bps / 1e9:.2f} Gbps'
    if bps >= 1e6:
        return f'{bps / 1e6:.1f} Mbps'
    return f'{bps / 1e3:.0f} kbps'


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
    HEIGHT = 112.0
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
        cpu = f'{d.cpu_usage:.0f}%' if d.cpu_usage >= 0 else '—'
        mem = f'{d.memory_usage:.0f}%' if d.memory_usage >= 0 else '—'
        return (f'{d.label}\n{d.ip}\n{d.role.value} · {d.vendor} {d.model}\n'
                f'status: {d.status} · {d.latency_ms} ms\n'
                f'CPU {cpu} · Mem {mem}\n'
                f'Traffic ↓ {_fmt_rate(d.in_rate_bps)} · ↑ {_fmt_rate(d.out_rate_bps)}')

    def refresh_tooltip(self) -> None:
        self.setToolTip(self._tooltip())

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
        renderer = device_renderer(self.device)
        if renderer is not None:
            r = 19.0
            renderer.render(painter, QRectF(icon_center.x() - r, icon_center.y() - r,
                                            r * 2, r * 2))
        else:
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

        model = (self.device.model or self.device.vendor or '').strip()
        if model:
            if len(model) > 24:
                model = model[:23] + '…'
            painter.setFont(QFont('Sans', 7))
            painter.setPen(TEXT_DIM)
            painter.drawText(QPointF(x0, rect.top() + 74), model)

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
    """A link between two nodes, labelled with both endpoint ports.

    Styling follows the endpoint levels: links between two level-1 devices are
    green and thicker (backbone), while any link touching a level-2+ device is
    gray and thinner.
    """

    def __init__(self, link: PortLink, source: NodeItem, target: NodeItem, offset: int = 0):
        super().__init__()
        self.link = link
        self.source = source
        self.target = target
        self.offset = offset
        self.setZValue(0)
        if source.device.layer <= 1 and target.device.layer <= 1:
            self.setPen(QPen(level_color(1), 2.5))
        else:
            self.setPen(QPen(EDGE, 1.0))
        source.add_edge(self)
        target.add_edge(self)
        self.update_path()

    def source_interface(self) -> Optional[Interface]:
        """Resolve the source-side interface for this link (by ifIndex/name)."""
        device = self.source.device
        if self.link.source_ifindex:
            iface = device.interfaces.get(self.link.source_ifindex)
            if iface is not None:
                return iface
        key = normalize_port(self.link.source_port)
        for iface in device.interfaces.values():
            if normalize_port(iface.name) == key:
                return iface
        return None

    def traffic_label(self) -> str:
        iface = self.source_interface()
        if iface is None or (iface.in_rate_bps <= 0 and iface.out_rate_bps <= 0):
            return ''
        return f'{_fmt_rate(iface.in_rate_bps)} ↓ · ↑ {_fmt_rate(iface.out_rate_bps)}'

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
        traffic = self.traffic_label()
        painter.setPen(TEXT_DIM)
        painter.setFont(QFont('Monospace', 7))
        bg = QColor(BG)
        fm = QFontMetricsF(painter.font())
        tw = fm.horizontalAdvance(label)
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        if traffic:
            t_fm = QFontMetricsF(QFont('Monospace', 7))
            box_w = max(tw, t_fm.horizontalAdvance(traffic)) + 8
            painter.drawRoundedRect(QRectF(mid.x() - box_w / 2, mid.y() - 16, box_w, 26), 3, 3)
            painter.setPen(TEXT_DIM)
            painter.drawText(QPointF(mid.x() - tw / 2, mid.y() - 2), label)
            painter.setPen(ACCENT)
            painter.drawText(QPointF(mid.x() - t_fm.horizontalAdvance(traffic) / 2, mid.y() + 10), traffic)
        else:
            painter.drawRoundedRect(QRectF(mid.x() - tw / 2 - 4, mid.y() - 8, tw + 8, 14), 3, 3)
            painter.setPen(TEXT_DIM)
            painter.drawText(QPointF(mid.x() - tw / 2, mid.y() + 3), label)


class GroupNodeItem(QGraphicsObject):
    """A circle collapsing several level-2 devices under one level-1 parent.

    Drawn as a distinct shape (dashed circle) so it never overlaps the
    individual icons it replaces.  Clicking it emits :attr:`clicked` so the
    UI can show a table of its member devices.
    """

    RADIUS = 22.0
    MIN_GAP = 80.0          # minimum vertical gap below the parent level-1 node
    clicked = pyqtSignal(object)   # emits the GroupNodeItem
    moved = pyqtSignal(object)     # emits the GroupNodeItem

    def __init__(self, parent_id: str, member_ids: list[str], graph: TopologyGraph,
                 parent_node: Optional[NodeItem] = None):
        super().__init__()
        self.parent_id = parent_id
        self.member_ids = list(member_ids)
        self.graph = graph
        self.parent_node = parent_node
        self.links: list[GroupLinkItem] = []
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setZValue(5)
        self.setToolTip(self._tooltip())

    def members(self) -> list[Device]:
        return [self.graph.devices[m] for m in self.member_ids
                if m in self.graph.devices]

    def _tooltip(self) -> str:
        return f'{len(self.member_ids)} devices (click to list, drag to move)'

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange \
                and self.parent_node is not None:
            p = QPointF(value)
            min_y = self.parent_node.pos().y() + self.MIN_GAP
            if p.y() < min_y:
                p.setY(min_y)
                return p
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for link in self.links:
                link.update_path()
            self.moved.emit(self)
        return super().itemChange(change, value)

    def boundingRect(self) -> QRectF:
        r = self.RADIUS + 12.0
        return QRectF(-r, -r, r * 2, r * 2)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = level_color(2)
        pen = QPen(ACCENT if self.isSelected() else color, 2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(22, 27, 34))
        painter.drawEllipse(QPointF(0, 0), self.RADIUS, self.RADIUS)

        painter.setPen(color)
        painter.setFont(QFont('Sans', 10, QFont.Weight.Bold))
        painter.drawText(QRectF(-self.RADIUS, -8, self.RADIUS * 2, 18),
                         Qt.AlignmentFlag.AlignCenter,
                         str(len(self.member_ids)))
        painter.setFont(QFont('Sans', 6))
        painter.drawText(QRectF(-self.RADIUS, 6, self.RADIUS * 2, 12),
                         Qt.AlignmentFlag.AlignCenter, 'devices')

    def mousePressEvent(self, event) -> None:
        self.clicked.emit(self)
        super().mousePressEvent(event)


class GroupLinkItem(QGraphicsPathItem):
    """A dashed line from a level-1 parent to a collapsed group node."""

    def __init__(self, source: NodeItem, target: GroupNodeItem):
        super().__init__()
        self.source = source
        self.target = target
        self.setZValue(0)
        self.setPen(QPen(EDGE, 1.0, Qt.PenStyle.DashLine))
        source.moved.connect(self.update_path)
        target.links.append(self)
        self.update_path()

    def update_path(self, *args) -> None:
        path = QPainterPath(self.source.pos())
        path.lineTo(self.target.pos())
        self.setPath(path)


class TopologyScene(QGraphicsScene):
    """Scene holding node/edge items and their device graph."""

    node_double_clicked = pyqtSignal(object)
    group_clicked = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.node_items: dict[str, NodeItem] = {}
        self.edge_items: list[EdgeItem] = []
        self.group_items: dict[str, GroupNodeItem] = {}
        self.group_links: list[GroupLinkItem] = []
        self.graph: Optional[TopologyGraph] = None
        self.clusters: dict[str, list[str]] = {}
        self.visible_levels: Optional[set] = None
        self._manual_counter = 0
        self.setBackgroundBrush(BG)
        self.setSceneRect(-20000, -20000, 40000, 40000)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Fill the dark background and draw a faint grid to aid alignment."""
        super().drawBackground(painter, rect)
        _draw_grid(painter, rect)

    def set_graph(self, graph: TopologyGraph, layout_mode: str = 'hierarchical',
                  positions: dict[str, tuple[float, float]] | None = None,
                  group_positions: dict[str, tuple[float, float]] | None = None) -> None:
        self.clear()
        self.node_items = {}
        self.edge_items = []
        self.group_items = {}
        self.group_links = []
        self.graph = graph

        engine = TopologyEngine()
        self.clusters = engine.group_children(graph)
        grouped: set[str] = set()
        for members in self.clusters.values():
            grouped.update(members)

        # nodes (skip grouped members — they collapse into a group circle)
        for device_id, device in graph.devices.items():
            if device_id in grouped:
                continue
            node = NodeItem(device)
            node.double_clicked.connect(self.node_double_clicked)
            self.addItem(node)
            self.node_items[device_id] = node

        # group nodes (one per over-populated level-1 parent)
        for parent_id, member_ids in self.clusters.items():
            gnode = GroupNodeItem(parent_id, member_ids, graph,
                                  parent_node=self.node_items.get(parent_id))
            gnode.clicked.connect(self.group_clicked)
            self.addItem(gnode)
            self.group_items[parent_id] = gnode

        # edges (skip any link touching a collapsed member)
        seen: dict[frozenset, int] = {}
        for link in graph.links:
            if link.source_id in grouped or link.target_id in grouped:
                continue
            key = frozenset((link.source_id, link.target_id))
            offset = seen.get(key, 0)
            seen[key] = offset + 1 if link.lag else 0
            src = self.node_items.get(link.source_id)
            dst = self.node_items.get(link.target_id)
            if src and dst:
                edge = EdgeItem(link, src, dst, offset=offset if link.lag else 0)
                self.edge_items.append(edge)
                self.addItem(edge)

        # dashed line from each level-1 parent to its collapsed group
        for parent_id, gnode in self.group_items.items():
            src = self.node_items.get(parent_id)
            if src is not None:
                glink = GroupLinkItem(src, gnode)
                self.group_links.append(glink)
                self.addItem(glink)

        self._apply_layout(layout_mode, positions, group_positions)

    def _apply_layout(self, layout_mode: str,
                      positions: dict[str, tuple[float, float]] | None = None,
                      group_positions: dict[str, tuple[float, float]] | None = None) -> None:
        if self.graph is None:
            return
        engine = TopologyEngine()
        if layout_mode == 'force':
            node_pos = engine.layout_force(self.graph)
            group_pos: dict[str, tuple[float, float]] = {}
            for parent_id, gnode in self.group_items.items():
                xs: list[float] = []
                ys: list[float] = []
                for m in gnode.member_ids:
                    p = node_pos.get(m)
                    if p:
                        xs.append(p[0])
                        ys.append(p[1])
                if xs:
                    group_pos[parent_id] = (sum(xs) / len(xs), sum(ys) / len(ys))
                else:
                    pp = node_pos.get(parent_id, (0.0, 0.0))
                    group_pos[parent_id] = (pp[0], pp[1] + TopologyEngine.SPACING * 1.4)
        else:
            node_pos, group_pos = engine.layout_tree(self.graph, self.clusters)

        if positions:
            node_pos = apply_layout(self.graph, positions, node_pos)
        if group_positions:
            for pid, xy in group_positions.items():
                if pid in self.graph.devices:
                    group_pos[pid] = xy

        for device_id, node in self.node_items.items():
            node.setPos(*node_pos.get(device_id, (0.0, 0.0)))
        for parent_id, gnode in self.group_items.items():
            gnode.setPos(*group_pos.get(parent_id, (0.0, 0.0)))

    def set_visible_levels(self, levels: Optional[set]) -> None:
        """Show only nodes/edges whose devices belong to ``levels``.

        ``None`` shows everything; an empty set hides everything.  An edge is
        visible only when both endpoints are visible.  A collapsed group is
        treated as a level-2 item.
        """
        self.visible_levels = levels
        if levels is None:
            for item in self.node_items.values():
                item.setVisible(True)
            for edge in self.edge_items:
                edge.setVisible(True)
            for gnode in self.group_items.values():
                gnode.setVisible(True)
            for glink in self.group_links:
                glink.setVisible(True)
            return

        for node in self.node_items.values():
            node.setVisible(node.device.layer in levels)
        for edge in self.edge_items:
            edge.setVisible(edge.source.device.layer in levels
                            and edge.target.device.layer in levels)
        for gnode in self.group_items.values():
            gnode.setVisible(2 in levels)
        for glink in self.group_links:
            glink.setVisible(glink.source.device.layer in levels and 2 in levels)

    def _add_node(self, device: Device, pos: QPointF) -> NodeItem:
        node = NodeItem(device)
        node.setPos(pos)
        node.double_clicked.connect(self.node_double_clicked)
        self.addItem(node)
        self.node_items[device.id] = node
        return node

    def add_device_node(self, device: Device, pos: QPointF) -> NodeItem:
        """Add a node for an existing (discovered) device; no-op if present."""
        existing = self.node_items.get(device.id)
        if existing is not None:
            return existing
        return self._add_node(device, pos)

    def add_manual_device(self, role: DeviceRole, pos: QPointF) -> Device:
        """Add a manually-placed device node (from the palette) at ``pos``."""
        self._manual_counter += 1
        device = Device(id=f'manual-{self._manual_counter}', role=role,
                        status='unknown', layer=1)
        self._add_node(device, pos)
        return device


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
        self.setAcceptDrops(True)
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

    def current_group_positions(self) -> dict[str, tuple[float, float]]:
        return {pid: (g.pos().x(), g.pos().y())
                for pid, g in self._scene.group_items.items()}

    def save_layout(self) -> None:
        """Write current node/group coordinates to ``layout_path`` (if set)."""
        if not self.layout_path:
            return
        graph = self._scene.graph if self._scene.graph is not None else TopologyGraph()
        save_layout(graph, self.current_positions(), self.layout_path,
                    group_positions=self.current_group_positions())

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
        saved_groups = load_group_layout(self.layout_path) if self.layout_path else {}
        self._scene.set_graph(graph, layout_mode, saved, saved_groups)
        for item in self._scene.node_items.values():
            item.moved.connect(self._schedule_save)
        for gnode in self._scene.group_items.values():
            gnode.moved.connect(self._schedule_save)
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
        """Fit the view to the currently visible node/group items."""
        rect = QRectF()
        first = True
        for item in self._scene.node_items.values():
            if item.isVisible():
                r = item.sceneBoundingRect()
                rect = r if first else rect.united(r)
                first = False
        for gnode in self._scene.group_items.values():
            if gnode.isVisible():
                r = gnode.sceneBoundingRect()
                rect = r if first else rect.united(r)
                first = False
        if first:
            return
        self.fitInView(rect.adjusted(-80, -80, 80, 80),
                       Qt.AspectRatioMode.KeepAspectRatio)
        self._zoom = self.transform().m11()

    def switch_layout(self, layout_mode: str) -> None:
        """Re-layout keeping the current graph (positions are recomputed)."""
        self._scene._apply_layout(layout_mode)
        self.fit_in_view()

    def add_manual_device(self, role: DeviceRole, pos: QPointF) -> Device:
        """Add a manually-placed device (from the palette) and wire its save."""
        device = self._scene.add_manual_device(role, pos)
        self._scene.node_items[device.id].moved.connect(self._schedule_save)
        return device

    def add_device_node(self, device: Device, pos: QPointF) -> None:
        """Add a discovered device node (progressive display); wires its save."""
        node = self._scene.add_device_node(device, pos)
        node.moved.connect(self._schedule_save)

    def clear_scene(self) -> None:
        """Remove all items and reset the scene (used before a new discovery)."""
        self._scene.clear()
        self._scene.node_items = {}
        self._scene.edge_items = []
        self._scene.group_items = {}
        self._scene.group_links = []
        self._scene.graph = None
        self._scene.clusters = {}

    # ── drag-and-drop (device palette → canvas) ──────────────────────────

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasFormat(DEVICE_MIME):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasFormat(DEVICE_MIME):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event) -> None:
        if event.mimeData().hasFormat(DEVICE_MIME):
            raw = bytes(event.mimeData().data(DEVICE_MIME))
            try:
                role = DeviceRole(raw.decode('utf-8'))
            except ValueError:
                role = DeviceRole.UNKNOWN
            pos = self.mapToScene(event.position().toPoint())
            self.add_manual_device(role, pos)
            event.acceptProposedAction()
        else:
            super().dropEvent(event)

    # ── PNG export ───────────────────────────────────────────────────────

    def export_png(self, path: str, scale: float = 2.0) -> bool:
        """Render the current map (background grid + items) to a PNG file."""
        scene = self._scene
        source = scene.itemsBoundingRect().adjusted(-60, -60, 60, 60)
        if not source.isValid() or source.isEmpty():
            return False
        w = max(1, int(source.width() * scale))
        h = max(1, int(source.height() * scale))
        image = QImage(w, h, QImage.Format.Format_ARGB32)
        image.fill(BG)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.save()
        painter.scale(scale, scale)
        painter.translate(-source.left(), -source.top())
        _draw_grid(painter, source)
        painter.restore()
        scene.render(painter, QRectF(image.rect()), source)
        painter.end()
        return image.save(path, 'PNG')

    def update_traffic(self, data: dict) -> None:
        """Apply live CPU/memory/traffic rates and refresh tooltips + edges."""
        for device_id, perf in data.items():
            node = self._scene.node_items.get(device_id)
            device = node.device if node is not None else None
            if device is None and self._scene.graph is not None:
                device = self._scene.graph.devices.get(device_id)
            if device is None:
                continue
            cpu = perf.get('cpu')
            mem = perf.get('memory')
            if cpu is not None:
                device.cpu_usage = round(float(cpu), 1)
            if mem is not None:
                device.memory_usage = float(mem)
            device.in_rate_bps = perf.get('in_bps', 0.0)
            device.out_rate_bps = perf.get('out_bps', 0.0)
            for idx, (in_bps, out_bps) in perf.get('if_rates', {}).items():
                iface = device.interfaces.get(idx)
                if iface is not None:
                    iface.in_rate_bps = in_bps
                    iface.out_rate_bps = out_bps
            if node is not None:
                node.refresh_tooltip()
        for edge in self._scene.edge_items:
            edge.update()


def load_graph(graph: TopologyGraph, layout_mode: str = 'hierarchical') -> TopologyView:
    """Create a standalone :class:`TopologyView` populated with ``graph``."""
    view = TopologyView()
    view.load(graph, layout_mode)
    view.resize(1000, 700)
    return view
