"""Interactive topology renderer — QGraphicsView scene in the style of
MikroTik The Dude / ZabFox.

Exposes :class:`TopologyView` and a convenience :func:`load_graph` that
populates the scene from a :class:`TopologyGraph`.
"""

from __future__ import annotations

import math
import os
import re
import sys
from typing import Optional

from PyQt6.QtCore import QLineF, QPointF, QRectF, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import (
    QColor, QFont, QFontMetricsF, QIcon, QImage, QPainter, QPainterPath, QPainterPathStroker,
    QPen, QPixmap, QPolygonF,
)
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsObject, QGraphicsPathItem, QGraphicsScene,
    QGraphicsView, QLabel, QMenu, QDialog, QFrame, QMessageBox, QToolButton, QVBoxLayout,
)

from balenolib.topology.models import (
    Device, DeviceRole, Interface, PortLink, TopologyGraph,
)
from balenolib.utils import _get_mac_vendor
from balenolib.topology.engine import TopologyEngine, normalize_port, LAYOUTS
from balenolib.topology.persistence import (
    apply_layout, load_layout, load_group_layout, save_layout, default_layout_path,
    save_map, load_map, default_map_path,
)
from balenolib.topology.undo import (
    TopologyUndoStack, MoveNodeCommand, AddDeviceCommand,
    RemoveDeviceCommand, AddLinkCommand,
)

__all__ = ['TopologyView', 'TopologyScene', 'NodeItem', 'EdgeItem',
           'GroupNodeItem', 'GroupLinkItem', 'load_graph', 'role_renderer',
           'make_role_icon']

# MIME type used to drag a device role from the palette onto the canvas.
DEVICE_MIME = 'application/x-baleno-topology-device'


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

# ── link styling ──────────────────────────────────────────────────────────
# Style reflects interface oper_status (up = dashed/animated, down = solid
# red); colour reflects the link's operating speed.
ACTIVE_COLOR = UP                # 10 Gbps+ (green)
DOWN_COLOR = DOWN                # offline link (red): interface down
SPEED_1G_COLOR = ACCENT          # 1 Gbps – <10 Gbps (light blue)
SPEED_LOW_COLOR = QColor(230, 126, 34)   # <1 Gbps incl. 100 Mbps (orange)
SPEED_UNKNOWN_COLOR = EDGE       # unknown speed (gray)
DASH_PATTERN = [6, 4]            # marching-ants dash pattern for active links
DASH_PERIOD = sum(DASH_PATTERN)


def speed_color(mbps: float) -> QColor:
    """Map an interface speed (Mbps) to its link colour."""
    if mbps >= 10000:
        return ACTIVE_COLOR
    if mbps >= 1000:
        return SPEED_1G_COLOR
    if mbps > 0:
        return SPEED_LOW_COLOR
    return SPEED_UNKNOWN_COLOR


_MAC_RE = re.compile(r'^([0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}$')


def _is_mac(value: str) -> bool:
    return bool(value and _MAC_RE.match(value.strip()))

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
    DeviceRole.CLOUD2: QColor(88, 166, 255),
    DeviceRole.CLOUD3: QColor(88, 166, 255),
    DeviceRole.CLOUD4: QColor(88, 166, 255),
    DeviceRole.INTERNET: QColor(88, 166, 255),
    DeviceRole.HOST: QColor(201, 209, 217),
    DeviceRole.PHONE: QColor(201, 209, 217),
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
    DeviceRole.CLOUD: 'cloud.svg',
    DeviceRole.CLOUD2: 'cloud2.svg',
    DeviceRole.CLOUD3: 'cloud3.svg',
    DeviceRole.CLOUD4: 'cloud4.svg',
    DeviceRole.INTERNET: 'internet.svg',
    DeviceRole.HOST: 'pc.svg',
    DeviceRole.PHONE: 'phone.svg',
    DeviceRole.UNKNOWN: 'unknown.svg',
}

_NETWORK_ICON_DIRS = [
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))), 'assets', 'icons',
        'network-icons'),
    os.path.join(getattr(sys, '_MEIPASS', ''), 'assets', 'icons', 'network-icons'),
    '/app/share/io.github.benjamimgois.baleno/icons/network-icons',
    '/usr/share/baleno/icons/network-icons',
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


def make_role_icon(role: DeviceRole, size: int = 16) -> QIcon:
    """Render a device role vector SVG into a QIcon."""
    renderer = role_renderer(role)
    if renderer is None:
        return QIcon()
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pix)
    renderer.render(painter, QRectF(0.0, 0.0, float(size), float(size)))
    painter.end()
    return QIcon(pix)


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


def draw_layout_icon(painter: QPainter, mode: str, rect: QRectF) -> None:
    """Draw a small self-contained glyph for a layout mode inside ``rect``.

    Drawn programmatically (no SVG assets): nodes as dots, links as lines.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(139, 148, 158)
    painter.setPen(QPen(color, 1.2))
    painter.setBrush(color)
    r = max(1.5, min(rect.width(), rect.height()) / 22.0)
    w, h = rect.width(), rect.height()

    def node(nx: float, ny: float) -> None:
        painter.drawEllipse(QPointF(rect.left() + nx * w, rect.top() + ny * h), r, r)

    def edge(x1: float, y1: float, x2: float, y2: float) -> None:
        painter.drawLine(QPointF(rect.left() + x1 * w, rect.top() + y1 * h),
                         QPointF(rect.left() + x2 * w, rect.top() + y2 * h))

    if mode == 'tree':
        edge(0.5, 0.15, 0.25, 0.5)
        edge(0.5, 0.15, 0.75, 0.5)
        edge(0.25, 0.5, 0.12, 0.85)
        edge(0.25, 0.5, 0.38, 0.85)
        edge(0.75, 0.5, 0.62, 0.85)
        edge(0.75, 0.5, 0.88, 0.85)
        for p in ((0.5, 0.15), (0.25, 0.5), (0.75, 0.5),
                  (0.12, 0.85), (0.38, 0.85), (0.62, 0.85), (0.88, 0.85)):
            node(*p)
    elif mode == 'force':
        pts = [(0.5, 0.5), (0.18, 0.22), (0.82, 0.28), (0.3, 0.8), (0.76, 0.78)]
        for a, b in ((0, 1), (0, 2), (0, 3), (0, 4), (1, 3), (2, 4)):
            edge(*pts[a], *pts[b])
        for p in pts:
            node(*p)
    elif mode == 'concentric':
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for rad in (0.2, 0.4):
            painter.drawEllipse(QPointF(rect.center()),
                                rad * w / 2, rad * h / 2)
        painter.setBrush(color)
        node(0.5, 0.5)
        for ang in range(0, 360, 60):
            rad = math.radians(ang)
            node(0.5 + 0.2 * math.cos(rad), 0.5 + 0.2 * math.sin(rad))
        for ang in range(30, 360, 60):
            rad = math.radians(ang)
            node(0.5 + 0.4 * math.cos(rad), 0.5 + 0.4 * math.sin(rad))
    elif mode == 'bfs':
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for y in (0.22, 0.5, 0.78):
            edge(0.12, y, 0.88, y)
        painter.setBrush(color)
        for y, xs in ((0.22, (0.3, 0.7)), (0.5, (0.2, 0.4, 0.6, 0.8)),
                      (0.78, (0.3, 0.7))):
            for x in xs:
                node(x, y)
    painter.restore()


def draw_fit_icon(painter: QPainter, rect: QRectF) -> None:
    """Draw a magnifier-with-plus glyph (zoom to fit) inside ``rect``."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(139, 148, 158)
    painter.setPen(QPen(color, 1.6))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    cx = rect.left() + rect.width() * 0.42
    cy = rect.top() + rect.height() * 0.42
    r = min(rect.width(), rect.height()) * 0.26
    painter.drawEllipse(QPointF(cx, cy), r, r)
    painter.drawLine(QPointF(cx + r * 0.7, cy + r * 0.7),
                     QPointF(rect.left() + rect.width() * 0.68,
                             rect.top() + rect.height() * 0.68))
    painter.drawLine(QPointF(cx - r * 0.55, cy), QPointF(cx + r * 0.55, cy))
    painter.drawLine(QPointF(cx, cy - r * 0.55), QPointF(cx, cy + r * 0.55))
    painter.restore()


def draw_link_icon(painter: QPainter, rect: QRectF) -> None:
    """Draw a two-node link glyph inside ``rect``."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    color = QColor(139, 148, 158)
    painter.setPen(QPen(color, 1.6))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    y = rect.center().y()
    x1 = rect.left() + rect.width() * 0.25
    x2 = rect.left() + rect.width() * 0.75
    r = min(rect.width(), rect.height()) * 0.18
    painter.drawLine(QPointF(x1, y), QPointF(x2, y))
    painter.drawEllipse(QPointF(x1, y), r, r)
    painter.drawEllipse(QPointF(x2, y), r, r)
    painter.restore()


class NodeItem(QGraphicsObject):
    """A device node. Movable, selectable; emits signals on move / double-click."""

    WIDTH = 170.0
    HEIGHT = 112.0
    moved = pyqtSignal(object)
    double_clicked = pyqtSignal(object)
    remove_requested = pyqtSignal(object)
    context_menu_requested = pyqtSignal(object, object)

    def __init__(self, device: Device):
        super().__init__()
        self.device = device
        self.edges: list[EdgeItem] = []
        self._link_highlight = False
        self._search_highlight = False
        # Level 2+ devices are less relevant: render smaller icons/fonts.
        self.scale = 1.0 if device.layer <= 1 else 0.72
        self.setFlags(
            QGraphicsItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        self.setCacheMode(QGraphicsItem.CacheMode.DeviceCoordinateCache)
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

    def set_link_highlight(self, on: bool) -> None:
        self._link_highlight = bool(on)
        self.update()

    def set_search_highlight(self, on: bool) -> None:
        if self._search_highlight != bool(on):
            self._search_highlight = bool(on)
            self.update()

    def mousePressEvent(self, event) -> None:
        scene = self.scene()
        if scene is not None and getattr(scene, '_link_mode', False):
            scene.link_hit(self)
            event.accept()
            return
        super().mousePressEvent(event)

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

    def contextMenuEvent(self, event) -> None:
        if not self.isSelected():
            scene = self.scene()
            if scene is not None:
                scene.clearSelection()
            self.setSelected(True)
        self.context_menu_requested.emit(self.device, event.screenPos())

    def get_layer_color(self) -> Optional[str]:
        scene = self.scene()
        if scene is None or not hasattr(scene, 'get_layer_color'):
            return None
        if not self.device.layers:
            return None
        sorted_layers = sorted(self.device.layers, key=lambda l: (len(l), l))
        for layer in sorted_layers:
            c = scene.get_layer_color(layer)
            if c:
                return c
        return None

    def paint(self, painter: QPainter, option, widget=None) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.scale(self.scale, self.scale)
        rect = QRectF(-self.WIDTH / 2, -self.HEIGHT / 2, self.WIDTH, self.HEIGHT)
        status = _status_color(self.device)
        border = status if self.isSelected() is False else ACCENT

        painter.setBrush(NODE_BG)
        is_lldp = getattr(self.device, 'layer', 1) > 1
        node_border_width = 1.0 if is_lldp else 2.0
        pen = QPen(ACCENT if self.isSelected() else NODE_BORDER,
                   2.5 if self.isSelected() else node_border_width)
        painter.setPen(pen)
        painter.drawRoundedRect(rect, 10, 10)

        # strong yellow ring when this node is the pending link source
        if self._link_highlight:
            painter.setPen(QPen(QColor(255, 214, 0), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-5, -5, 5, 5), 14, 14)

        # strong cyan ring when this node is highlighted by search
        if self._search_highlight:
            painter.setPen(QPen(QColor(0, 210, 255), 3.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(-6, -6, 6, 6), 14, 14)

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
        layer_color = self.get_layer_color()
        if layer_color:
            painter.setPen(QPen(QColor(layer_color), 2.5))
        else:
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

        model = ' '.join(p for p in (self.device.vendor, self.device.model)
                         if p and p.strip()).strip()
        if not model and not self.device.ip and _is_mac(self.device.chassis_id):
            model = _get_mac_vendor(self.device.chassis_id)
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

    Styling follows interface oper_status only:
    * ``active``  — both interfaces up, dashed and animated (marching ants)
    * ``offline`` — any interface down, solid red

    A manual override (``PortLink.override_status`` / ``override_speed``) takes
    priority over the automatic detection.
    """

    HIT_WIDTH = 10.0
    SPREAD = 30.0           # perpendicular offset per parallel-link step
    LABEL_STEP = 18.0       # vertical label stack gap for parallel links

    def __init__(self, link: PortLink, source: NodeItem, target: NodeItem, offset: int = 0):
        super().__init__()
        self.link = link
        self.source = source
        self.target = target
        self.offset = offset
        self.setZValue(0)
        self.setPen(QPen(EDGE, 2.5))
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.state = 'active'
        self._dash_offset = 0.0
        source.add_edge(self)
        target.add_edge(self)
        self.update_path()
        self.refresh_state()

    THICKNESS_MAP = {
        1: 1.0,
        2: 2.0,
        3: 3.0,
        4: 4.5,
        5: 6.0,
    }

    def _pen_width(self) -> float:
        w = getattr(self.link, 'weight', 2) or 2
        return self.THICKNESS_MAP.get(w, 2.0)

    def shape(self) -> QPainterPath:
        """Widen the hit area so the thin line is easy to right-click."""
        stroker = QPainterPathStroker()
        stroker.setWidth(max(self.HIT_WIDTH, self._pen_width() + 6.0))
        return stroker.createStroke(self.path())

    def contextMenuEvent(self, event) -> None:
        emit = getattr(self.scene(), 'edge_context_menu_requested', None)
        if emit is not None:
            emit.emit(self, event.screenPos())
        event.accept()

    def source_interface(self) -> Optional[Interface]:
        """Resolve the source-side interface for this link.

        Prefers matching by port name (lldpLocPortId vs ifName) because the
        LLDP local-port number stored in ``source_ifindex`` is not guaranteed
        to equal the ifIndex on every vendor.  Falls back to ifIndex only when
        the name does not resolve.
        """
        device = self.source.device
        port = (self.link.source_port or '').strip()
        if port:
            key = normalize_port(port)
            for iface in device.interfaces.values():
                if iface.name and normalize_port(iface.name) == key:
                    return iface
        if self.link.source_ifindex:
            return device.interfaces.get(self.link.source_ifindex)
        return None

    def target_interface(self) -> Optional[Interface]:
        """Resolve the target-side interface (by port name — no ifIndex stored)."""
        device = self.target.device
        port = (self.link.target_port or '').strip()
        if not port:
            return None
        key = normalize_port(port)
        for iface in device.interfaces.values():
            if iface.name and normalize_port(iface.name) == key:
                return iface
        return None

    @staticmethod
    def _iface_down(iface: Optional[Interface]) -> bool:
        return iface is not None and iface.oper_status == 'down'

    def link_speed(self) -> float:
        """Operating speed of the link.

        A manual ``override_speed`` wins; otherwise the slower of the two
        interfaces is used.
        """
        if self.link.override_speed is not None:
            return self.link.override_speed
        si = self.source_interface()
        ti = self.target_interface()
        speeds = [i.speed_mbps for i in (si, ti) if i is not None and i.speed_mbps > 0]
        return min(speeds) if speeds else 0.0

    def refresh_state(self) -> None:
        """Recompute the link state.

        A manual ``override_status`` wins; otherwise the two endpoints'
        oper_status decide (any down → offline, else active).  Traffic is
        intentionally ignored.
        """
        if self.link.override_status == 'down':
            self.state = 'down'
        elif self.link.override_status == 'up':
            self.state = 'active'
        elif self._iface_down(self.source_interface()) or self._iface_down(self.target_interface()):
            self.state = 'down'
        else:
            self.state = 'active'

    def _pen(self) -> QPen:
        w = self._pen_width()
        if self.state == 'down':
            return QPen(DOWN_COLOR, max(1.5, w))
        pen = QPen(speed_color(self.link_speed()), w)
        pen.setDashPattern(DASH_PATTERN)
        pen.setDashOffset(self._dash_offset)
        return pen

    def traffic_label(self) -> str:
        iface = self.source_interface()
        if iface is None or (iface.in_rate_bps <= 0 and iface.out_rate_bps <= 0):
            return ''
        return f'{_fmt_rate(iface.in_rate_bps)} ↓ · ↑ {_fmt_rate(iface.out_rate_bps)}'

    def _ctrl(self) -> QPointF:
        """Control point for the quadratic curve of an offset (parallel) link."""
        s = self.source.pos()
        t = self.target.pos()
        mid = (s + t) / 2
        if not self.offset:
            return mid
        dx, dy = t.x() - s.x(), t.y() - s.y()
        length = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / length, dx / length
        return QPointF(mid.x() + nx * self.offset * self.SPREAD,
                       mid.y() + ny * self.offset * self.SPREAD)

    def _label_pos(self) -> QPointF:
        """Label anchor, stacked vertically for parallel links so labels stay
        readable (positive offset → up, negative → down)."""
        mid = (self.source.pos() + self.target.pos()) / 2
        mid.setY(mid.y() - self.offset * self.LABEL_STEP)
        return mid

    def update_path(self) -> None:
        s = self.source.pos()
        t = self.target.pos()
        path = QPainterPath(s)
        if self.offset:
            path.quadTo(self._ctrl(), t)
        else:
            path.lineTo(t)
        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None) -> None:
        # Fast path for Minimap viewport: static solid line without text or animation overhead
        if widget is not None and getattr(widget, '_is_minimap_viewport', False):
            painter.setPen(QPen(speed_color(self.link_speed()), 1.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())
            return

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isSelected():
            painter.setPen(QPen(QColor(255, 255, 255, 150), self._pen_width() + 4.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(self.path())
        painter.setPen(self._pen())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawPath(self.path())

        # Level of Detail (LOD): skip port and traffic labels when zoomed far out
        lod = option.levelOfDetailFromTransform(painter.worldTransform()) if option else 1.0
        if lod < 0.5:
            return

        mid = self._label_pos()
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

        if self.link.overridden:
            lx = mid.x() - tw / 2 - 12
            ly = mid.y() - 3
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(ACCENT)
            painter.drawEllipse(QPointF(lx, ly), 6, 6)
            painter.setPen(QColor('#0D1117'))
            painter.setFont(QFont('Sans', 6, QFont.Weight.Bold))
            painter.drawText(QRectF(lx - 6, ly - 6, 12, 12),
                             Qt.AlignmentFlag.AlignCenter, 'M')


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
    context_menu_requested = pyqtSignal(object, object)   # (group, screen_pos)

    def __init__(self, parent_id: str, member_ids: list[str], graph: TopologyGraph,
                 parent_node: Optional[NodeItem] = None):
        super().__init__()
        self.parent_id = parent_id
        self.member_ids = list(member_ids)
        self.graph = graph
        self.parent_node = parent_node
        self.links: list[GroupLinkItem] = []
        self._link_highlight = False
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

        if self._link_highlight:
            painter.setPen(QPen(QColor(255, 214, 0), 4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(QPointF(0, 0), self.RADIUS + 5, self.RADIUS + 5)

        painter.setPen(color)
        painter.setFont(QFont('Sans', 10, QFont.Weight.Bold))
        painter.drawText(QRectF(-self.RADIUS, -8, self.RADIUS * 2, 18),
                         Qt.AlignmentFlag.AlignCenter,
                         str(len(self.member_ids)))
        painter.setFont(QFont('Sans', 6))
        painter.drawText(QRectF(-self.RADIUS, 6, self.RADIUS * 2, 12),
                         Qt.AlignmentFlag.AlignCenter, 'devices')

    def set_link_highlight(self, on: bool) -> None:
        self._link_highlight = bool(on)
        self.update()

    def mousePressEvent(self, event) -> None:
        scene = self.scene()
        if scene is not None and getattr(scene, '_link_mode', False):
            scene.link_hit(self)
            event.accept()
            return
        self.clicked.emit(self)
        super().mousePressEvent(event)

    def contextMenuEvent(self, event) -> None:
        self.context_menu_requested.emit(self, event.screenPos())


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
    node_removed = pyqtSignal(object)
    node_context_menu_requested = pyqtSignal(object, object)
    group_context_menu_requested = pyqtSignal(object, object)
    edge_context_menu_requested = pyqtSignal(object, object)
    link_requested = pyqtSignal(object, object)   # (source_item, target_item)
    link_mode_changed = pyqtSignal(bool)

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
        self._link_mode = False
        self._link_source: Optional[object] = None
        self._preview: Optional[QGraphicsPathItem] = None
        self._drag_start_positions: dict[str, QPointF] = {}
        self.setBackgroundBrush(BG)
        self.setSceneRect(-20000, -20000, 40000, 40000)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        """Fill the dark background and draw a faint grid to aid alignment."""
        super().drawBackground(painter, rect)
        _draw_grid(painter, rect)

    def get_layer_color(self, layer_name: str) -> Optional[str]:
        if not self.graph or not getattr(self.graph, 'layer_colors', None):
            return None
        colors = self.graph.layer_colors
        if layer_name in colors:
            return colors[layer_name]
        m = re.match(r'^(.*?)-(\d+)$', layer_name)
        if m and m.group(1) in colors:
            return colors[m.group(1)]
        return None

    def set_graph(self, graph: TopologyGraph, layout_mode: str = 'hierarchical',
                  positions: dict[str, tuple[float, float]] | None = None,
                  group_positions: dict[str, tuple[float, float]] | None = None) -> None:
        self.clear()
        self.node_items = {}
        self.edge_items = []
        self.group_items = {}
        self.group_links = []
        self.graph = graph
        self._link_mode = False
        self._link_source = None
        self._preview = None

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
            node.remove_requested.connect(self._on_remove_requested)
            node.context_menu_requested.connect(self.node_context_menu_requested)
            self.addItem(node)
            self.node_items[device_id] = node

        # group nodes (one per over-populated level-1 parent)
        for parent_id, member_ids in self.clusters.items():
            gnode = GroupNodeItem(parent_id, member_ids, graph,
                                  parent_node=self.node_items.get(parent_id))
            gnode.clicked.connect(self.group_clicked)
            gnode.context_menu_requested.connect(self.group_context_menu_requested)
            self.addItem(gnode)
            self.group_items[parent_id] = gnode

        # edges (skip any link touching a collapsed member)
        for link in graph.links:
            if link.source_id in grouped or link.target_id in grouped:
                continue
            src = self.node_items.get(link.source_id)
            dst = self.node_items.get(link.target_id)
            if src and dst:
                edge = EdgeItem(link, src, dst, offset=0)
                self.edge_items.append(edge)
                self.addItem(edge)
        self._assign_pair_offsets()

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
        method = LAYOUTS.get(layout_mode, 'layout_tree')
        node_pos, group_pos = getattr(engine, method)(self.graph, self.clusters)

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

    def set_visible_layers(self, visible_layers: Optional[set]) -> None:
        """Show only devices belonging to the given named layers.

        ``None`` shows everything.  A device with no layers (manual/legacy) is
        always visible; a device with layers is visible when at least one of its
        layers is in ``visible_layers``.  Edges follow their endpoints.
        """
        if visible_layers is None:
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
            layers = node.device.layers
            node.setVisible((not layers) or bool(layers & visible_layers))
        for edge in self.edge_items:
            edge.setVisible(edge.source.isVisible() and edge.target.isVisible())
        for gnode in self.group_items.values():
            gnode.setVisible(True)
        for glink in self.group_links:
            glink.setVisible(glink.source.isVisible())

    def _add_node(self, device: Device, pos: QPointF) -> NodeItem:
        if self.graph is None:
            self.graph = TopologyGraph()
        if device.id not in self.graph.devices:
            self.graph.devices[device.id] = device
        node = NodeItem(device)
        node.setPos(pos)
        node.double_clicked.connect(self.node_double_clicked)
        node.remove_requested.connect(self._on_remove_requested)
        node.context_menu_requested.connect(self.node_context_menu_requested)
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
        """Add a manually-placed device node (from the palette) at ``pos``.

        The device is registered in ``self.graph.devices`` so the persisted
        map carries manual objects too (design D2).
        """
        if self.graph is None:
            self.graph = TopologyGraph()
        self._manual_counter += 1
        device = Device(id=f'manual-{self._manual_counter}', role=role,
                        status='unknown', layer=1)
        self.graph.devices[device.id] = device
        self._add_node(device, pos)
        return device

    # ── manual link creation ─────────────────────────────────────────────

    def set_link_mode(self, on: bool) -> None:
        """Enter/exit manual link-creation mode."""
        self._link_mode = bool(on)
        if not on:
            self._clear_link_source()
        self.link_mode_changed.emit(self._link_mode)

    def _clear_link_source(self) -> None:
        if self._link_source is not None:
            self._link_source.set_link_highlight(False)
            self._link_source = None
        self._clear_preview()

    def _clear_preview(self) -> None:
        if self._preview is not None:
            self.removeItem(self._preview)
            self._preview = None

    def _update_preview(self, pos: QPointF) -> None:
        if self._link_source is None:
            self._clear_preview()
            return
        if self._preview is None:
            self._preview = QGraphicsPathItem()
            self._preview.setPen(QPen(QColor(255, 214, 0), 2, Qt.PenStyle.DashLine))
            self._preview.setZValue(20)
            self._preview.setAcceptedMouseButtons(Qt.MouseButton.NoButton)
            self.addItem(self._preview)
        path = QPainterPath(self._link_source.pos())
        path.lineTo(pos)
        self._preview.setPath(path)

    def link_hit(self, item) -> None:
        """Handle a click on a node/group while in link mode."""
        if not self._link_mode:
            return
        if self._link_source is None:
            self._link_source = item
            item.set_link_highlight(True)
        elif self._link_source is item:
            self.set_link_mode(False)   # clicking the same object cancels
        else:
            source = self._link_source
            self._link_source = None
            source.set_link_highlight(False)
            self._clear_preview()
            self.link_requested.emit(source, item)

    def mousePressEvent(self, event) -> None:
        """A click on empty canvas (not a node/group) while in link mode cancels."""
        if self._link_mode:
            hit = self.items(event.scenePos())
            if not any(isinstance(i, (NodeItem, GroupNodeItem)) for i in hit):
                self.set_link_mode(False)
                event.accept()
                return
        selected_nodes = [i for i in self.selectedItems() if isinstance(i, NodeItem)]
        if selected_nodes:
            self._drag_start_positions = {n.device.id: QPointF(n.pos()) for n in selected_nodes}
        else:
            hit_nodes = [i for i in self.items(event.scenePos()) if isinstance(i, NodeItem)]
            if hit_nodes:
                self._drag_start_positions = {hit_nodes[0].device.id: QPointF(hit_nodes[0].pos())}
            else:
                self._drag_start_positions = {}
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        if self._drag_start_positions:
            moves = []
            for did, old_pos in self._drag_start_positions.items():
                node = self.node_items.get(did)
                if node is not None and (node.pos() - old_pos).manhattanLength() > 1.0:
                    moves.append((did, old_pos, QPointF(node.pos())))
            if moves:
                views = self.views()
                if views and hasattr(views[0], 'undo_stack'):
                    stack = views[0].undo_stack
                    if len(moves) == 1:
                        did, old_pos, new_pos = moves[0]
                        stack.push(MoveNodeCommand(views[0], did, old_pos, new_pos))
                    else:
                        stack.beginMacro('Move Nodes')
                        for did, old_pos, new_pos in moves:
                            stack.push(MoveNodeCommand(views[0], did, old_pos, new_pos))
                        stack.endMacro()
            self._drag_start_positions = {}

    def mouseMoveEvent(self, event) -> None:
        if self._link_mode:
            self._update_preview(event.scenePos())
        super().mouseMoveEvent(event)

    def add_manual_link(self, source_id: str, source_port: str,
                        target_id: str, target_port: str,
                        speed: Optional[float] = None) -> Optional[str]:
        """Create a manual link between two devices.

        Returns ``None`` on success, or an error message to show the user.
        """
        if self.graph is None:
            self.graph = TopologyGraph()
        if source_id == target_id:
            return 'Cannot link a device to itself.'
        link = PortLink(source_id=source_id, source_port=source_port,
                        target_id=target_id, target_port=target_port,
                        source_ifindex=0, manual=True)
        if speed is not None:
            link.override_speed = speed
        for existing in self.graph.links:
            if existing.key() == link.key():
                return 'This link already exists.'
        src = self.node_items.get(source_id)
        dst = self.node_items.get(target_id)
        if src is None or dst is None:
            return 'Endpoint not found on the map.'
        self.graph.links.append(link)
        edge = EdgeItem(link, src, dst, offset=0)
        self.edge_items.append(edge)
        self.addItem(edge)
        self._assign_pair_offsets()
        return None

    def _assign_pair_offsets(self) -> None:
        """Recompute symmetric offsets for every set of parallel links."""
        groups: dict[frozenset, list[EdgeItem]] = {}
        for edge in self.edge_items:
            key = frozenset((edge.link.source_id, edge.link.target_id))
            groups.setdefault(key, []).append(edge)
        for pair in groups.values():
            for i, edge in enumerate(pair):
                edge.offset = 0 if i == 0 else ((i + 1) // 2) * (1 if i % 2 == 1 else -1)
                edge.update_path()

    def _on_remove_requested(self, device: Device) -> None:
        if self.remove_node(device.id):
            self.node_removed.emit(device.id)

    def _remove_edge_item(self, edge: EdgeItem) -> None:
        for node in (edge.source, edge.target):
            if edge in node.edges:
                node.edges.remove(edge)
        if edge in self.edge_items:
            self.edge_items.remove(edge)
        self.removeItem(edge)

    def remove_edge(self, edge: EdgeItem) -> None:
        """Remove an edge item and its PortLink from the graph."""
        if self.graph is not None:
            self.graph.links = [l for l in self.graph.links if l is not edge.link]
        self._remove_edge_item(edge)
        self._assign_pair_offsets()

    def remove_node(self, device_id: str) -> bool:
        """Remove a node item, its device and any touching links from the graph.

        Returns True if a node was actually removed.
        """
        node = self.node_items.pop(device_id, None)
        if node is None:
            return False
        for edge in list(node.edges):
            self._remove_edge_item(edge)
        # drop group link anchored on this node, and the group itself if the
        # removed node was its parent.
        for glink in list(self.group_links):
            if glink.source is node:
                self.group_links.remove(glink)
                self.removeItem(glink)
        gnode = self.group_items.pop(device_id, None)
        if gnode is not None:
            for glink in list(self.group_links):
                if glink.target is gnode:
                    self.group_links.remove(glink)
                    self.removeItem(glink)
            self.removeItem(gnode)
        self.clusters.pop(device_id, None)
        for members in self.clusters.values():
            if device_id in members:
                members.remove(device_id)
        self.removeItem(node)
        if self.graph is not None:
            self.graph.devices.pop(device_id, None)
            self.graph.links = [l for l in self.graph.links
                                if not l.touches(device_id)]
        return True

    def _derive_manual_counter(self) -> None:
        """Derive ``_manual_counter`` from the highest ``manual-N`` id present,
        so manually added devices do not collide after reload."""
        max_n = 0
        ids = self.graph.devices if self.graph is not None else {}
        for did in ids:
            if did.startswith('manual-'):
                try:
                    max_n = max(max_n, int(did[len('manual-'):]))
                except ValueError:
                    continue
        self._manual_counter = max_n

    def set_graph_from_persisted(
            self, graph: TopologyGraph,
            positions: dict[str, tuple[float, float]] | None = None,
            group_positions: dict[str, tuple[float, float]] | None = None) -> None:
        """Populate the scene from a persisted map, using saved coordinates as
        authoritative (no TopologyEngine auto-layout, no grouping)."""
        self.clear()
        self.node_items = {}
        self.edge_items = []
        self.group_items = {}
        self.group_links = []
        self.graph = graph
        self.clusters = {}
        self._link_mode = False
        self._link_source = None
        self._preview = None

        for device_id, device in graph.devices.items():
            node = NodeItem(device)
            node.double_clicked.connect(self.node_double_clicked)
            node.remove_requested.connect(self._on_remove_requested)
            node.context_menu_requested.connect(self.node_context_menu_requested)
            self.addItem(node)
            self.node_items[device_id] = node

        for link in graph.links:
            src = self.node_items.get(link.source_id)
            dst = self.node_items.get(link.target_id)
            if src and dst:
                edge = EdgeItem(link, src, dst, offset=0)
                self.edge_items.append(edge)
                self.addItem(edge)
        self._assign_pair_offsets()

        for device_id, node in self.node_items.items():
            xy = (positions or {}).get(device_id)
            if xy is not None:
                node.setPos(xy[0], xy[1])
        self._derive_manual_counter()


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
        self.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.NoViewportUpdate)
        if self.viewport() is not None:
            self.viewport()._is_minimap_viewport = True
        self.setStyleSheet('background: #0D1117; border: 1px solid #30363d;')

        # Update overview rectangle when main view is scrolled/panned
        main_view.horizontalScrollBar().valueChanged.connect(self._on_scroll)
        main_view.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def _on_scroll(self, *args) -> None:
        self.viewport().update()

    def refresh_bounds(self) -> None:
        """Fit scene bounds into overview and repaint."""
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


class NavDockButton(QToolButton):
    """Small square icon button for the floating canvas dock."""

    def __init__(self, mode: str, tooltip: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.setFixedSize(30, 30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        if mode == 'link':
            self.setCheckable(True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            bg = QColor(65, 105, 225)
        elif self.underMouse():
            bg = QColor(48, 54, 61)
        else:
            bg = Qt.GlobalColor.transparent
        painter.fillRect(self.rect(), bg)

        rect = QRectF(self.rect()).adjusted(4, 4, -4, -4)
        if self.mode == 'zoom_in':
            painter.setPen(QPen(QColor(201, 209, 217), 1.6))
            cx, cy = rect.center().x(), rect.center().y()
            painter.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
            painter.drawLine(QPointF(cx, cy - 5), QPointF(cx, cy + 5))
        elif self.mode == 'zoom_out':
            painter.setPen(QPen(QColor(201, 209, 217), 1.6))
            cx, cy = rect.center().x(), rect.center().y()
            painter.drawLine(QPointF(cx - 5, cy), QPointF(cx + 5, cy))
        elif self.mode == 'fit':
            draw_fit_icon(painter, rect)
        elif self.mode == 'link':
            draw_link_icon(painter, rect)
        painter.end()


class NavigationOverlay(QFrame):
    """Floating canvas navigation dock (+, -, Fit, Link)."""

    def __init__(self, view: TopologyView):
        super().__init__(view)
        self._view = view
        self.setObjectName('navOverlay')
        self.setStyleSheet("""
            QFrame#navOverlay {
                background-color: rgba(22, 27, 34, 0.88);
                border: 1px solid #30363D;
                border-radius: 6px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(2)

        self.btn_in = NavDockButton('zoom_in', 'Zoom In (+)', self)
        self.btn_in.clicked.connect(self._view.zoom_in)
        layout.addWidget(self.btn_in)

        self.btn_out = NavDockButton('zoom_out', 'Zoom Out (-)', self)
        self.btn_out.clicked.connect(self._view.zoom_out)
        layout.addWidget(self.btn_out)

        self.btn_fit = NavDockButton('fit', 'Fit Map in View', self)
        self.btn_fit.clicked.connect(self._view.fit_in_view)
        layout.addWidget(self.btn_fit)

        self.btn_link = NavDockButton('link', 'Create Link (Click two devices)', self)
        self.btn_link.toggled.connect(self._view.set_link_mode)
        layout.addWidget(self.btn_link)

        self._view._scene.link_mode_changed.connect(self._on_link_mode_changed)
        self.adjustSize()

    def _on_link_mode_changed(self, on: bool) -> None:
        self.btn_link.blockSignals(True)
        self.btn_link.setChecked(on)
        self.btn_link.blockSignals(False)


class TopologyView(QGraphicsView):
    """Main topology canvas: wheel-zoom, pan, minimap overlay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._scene = TopologyScene()
        self.setScene(self._scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._interaction_mode = 'select'
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setCursor(Qt.CursorShape.ArrowCursor)
        self._middle_pan_active = False
        self._middle_pan_pos = None
        self._interaction_active = False
        self._animation_enabled = True
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)

        # OpenGL hardware acceleration with transparent fallback to raster
        self._opengl_active = False
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtOpenGLWidgets import QOpenGLWidget
            from PyQt6.QtGui import QSurfaceFormat
            platform_name = QApplication.platformName() if QApplication.instance() else ''
            if platform_name != 'offscreen':
                fmt = QSurfaceFormat()
                fmt.setSamples(4)
                gl_widget = QOpenGLWidget()
                gl_widget.setFormat(fmt)
                self.setViewport(gl_widget)
                self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
                self._opengl_active = True
            else:
                self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
        except Exception:
            self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.BoundingRectViewportUpdate)
            self._opengl_active = False

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._zoom = 1.0
        self.minimap = Minimap(self)
        self.nav_dock = NavigationOverlay(self)
        self.nav_dock.setVisible(False)
        self.undo_stack = TopologyUndoStack(self)
        self._legend = QLabel(self)
        self._legend.setTextFormat(Qt.TextFormat.RichText)
        self._legend.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._legend.setText(
            '<span style="background-color:#0D1117; color:#C9D1D9; '
            'padding:5px 8px; border:1px solid #30363d; border-radius:4px;">'
            '<span style="color:#3FB950;">●</span> 10G+ &nbsp;&nbsp;'
            '<span style="color:#58A6FF;">●</span> 1G &nbsp;&nbsp;'
            '<span style="color:#E67E22;">●</span> 100M &nbsp;&nbsp;'
            '<span style="color:#8B949E;">●</span> ? &nbsp;&nbsp;'
            '<span style="color:#F85149;">━</span> down</span>')
        self._legend.adjustSize()
        self.layout_path = ''
        self.setAcceptDrops(True)
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(800)
        self._save_timer.timeout.connect(self.save_map)
        self._scene.node_removed.connect(self._schedule_save)
        self._scene.edge_context_menu_requested.connect(self._on_edge_context_menu)
        self._dash_phase = 0.0
        self._anim_timer = QTimer(self)
        self._anim_timer.setInterval(50)
        self._anim_timer.timeout.connect(self._tick_animation)
        self._anim_timer.start()

    def _tick_animation(self) -> None:
        """Advance the marching-ants phase and repaint only visible active edges."""
        if not self._animation_enabled or self._interaction_active or not self.isVisible():
            return

        self._dash_phase = (self._dash_phase + 1.0) % DASH_PERIOD
        viewport = self.viewport()
        if viewport is None:
            return
        visible_rect = self.mapToScene(viewport.rect()).boundingRect().adjusted(-80, -80, 80, 80)
        for edge in self._scene.edge_items:
            if edge.state == 'active' and edge.isVisible():
                if edge.sceneBoundingRect().intersects(visible_rect):
                    edge._dash_offset = self._dash_phase
                    edge.update()

    def set_animation_enabled(self, enabled: bool) -> None:
        """Enable or disable marching-ants link animations."""
        self._animation_enabled = enabled
        if enabled:
            if not self._anim_timer.isActive():
                self._anim_timer.start(50)
        else:
            if self._anim_timer.isActive():
                self._anim_timer.stop()
            for edge in self._scene.edge_items:
                if edge.state == 'active':
                    edge._dash_offset = 0.0
                    edge.update()

    def _on_edge_context_menu(self, edge: EdgeItem, pos) -> None:
        """Show the manual state/speed override menu for a link."""
        menu = QMenu(self)
        menu.setStyleSheet(
            'QMenu { background-color:#161B22; border:1px solid #30363D; color:#C9D1D9; }'
            'QMenu::item { padding:6px 22px 6px 14px; }'
            'QMenu::item:selected { background-color:#4169E1; color:#ffffff; }'
            'QMenu::separator { height:1px; background:#30363D; margin:4px 8px; }')

        state_menu = menu.addMenu('State')
        s_auto = state_menu.addAction('Auto')
        s_up = state_menu.addAction('Up')
        s_down = state_menu.addAction('Down')
        for act, val in ((s_auto, None), (s_up, 'up'), (s_down, 'down')):
            act.setCheckable(True)
            act.setChecked(edge.link.override_status == val)

        speed_menu = menu.addMenu('Speed')
        v_auto = speed_menu.addAction('Auto')
        v_auto.setCheckable(True)
        v_auto.setChecked(edge.link.override_speed is None)
        speed_opts = [('10 Mbps', 10.0), ('100 Mbps', 100.0),
                      ('1 Gbps', 1000.0), ('10 Gbps', 10000.0)]
        v_acts: list[tuple] = []
        for lbl, mbps in speed_opts:
            act = speed_menu.addAction(lbl)
            act.setCheckable(True)
            act.setChecked(edge.link.override_speed == mbps)
            v_acts.append((act, mbps))

        thick_menu = menu.addMenu('Espessura da linha')
        current_weight = getattr(edge.link, 'weight', 2) or 2
        thick_opts = [
            (1, '1 px — Muito fina'),
            (2, '2 px — Padrão'),
            (3, '3 px — Média'),
            (4, '4 px — Grossa'),
            (5, '6 px — Muito grossa'),
        ]
        t_acts: list[tuple] = []
        for lvl, lbl in thick_opts:
            act = thick_menu.addAction(lbl)
            act.setCheckable(True)
            act.setChecked(current_weight == lvl)
            t_acts.append((act, lvl))

        menu.addSeparator()
        edit_act = menu.addAction('Edit') if edge.link.manual else None
        delete_act = menu.addAction('Delete')

        chosen = menu.exec(pos)
        if chosen is None:
            return
        if edit_act is not None and chosen is edit_act:
            self._edit_manual_link(edge)
            return
        if chosen is delete_act:
            msg = f"Deseja realmente remover a conexão '{edge.link.source_port} ⟷ {edge.link.target_port}'?"
            if not self._confirm_deletion(msg):
                return
            self._scene.remove_edge(edge)
            self._schedule_save()
            return
        if chosen is s_auto:
            edge.link.override_status = None
        elif chosen is s_up:
            edge.link.override_status = 'up'
        elif chosen is s_down:
            edge.link.override_status = 'down'
        elif chosen is v_auto:
            edge.link.override_speed = None
        else:
            handled = False
            for act, mbps in v_acts:
                if chosen is act:
                    edge.link.override_speed = mbps
                    handled = True
                    break
            if not handled:
                for act, lvl in t_acts:
                    if chosen is act:
                        edge.link.weight = lvl
                        break
        edge.refresh_state()
        edge.update()
        self._schedule_save()

    def _edit_manual_link(self, edge: EdgeItem) -> None:
        """Edit the port names of a manually-created link."""
        from balenolib.topology.gui.detail import LinkEditDialog
        dialog = LinkEditDialog(
            edge.source.device.label, edge.link.source_port,
            edge.target.device.label, edge.link.target_port, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            edge.link.source_port = dialog.source_port()
            edge.link.target_port = dialog.target_port()
            edge.update()
            self._schedule_save()

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

    def save_map(self) -> None:
        """Write the whole map (graph + positions + groups) to ``layout_path``
        (if set), in the v3 ``topology_map.json`` format."""
        if not self.layout_path:
            return
        graph = self._scene.graph if self._scene.graph is not None else TopologyGraph()
        save_map(graph, self.current_positions(), self.layout_path,
                 group_positions=self.current_group_positions())

    def remove_node(self, device: Device) -> None:
        """Remove a device node from the canvas and schedule an auto-save."""
        if self._scene.remove_node(device.id):
            self._schedule_save()

    def on_device_changed(self, device: Device) -> None:
        """Handle an edited device: repaint its node and schedule a save."""
        node = self._scene.node_items.get(device.id)
        if node is not None:
            node.refresh_tooltip()
            node.update()
        self._schedule_save()

    def load_saved_map(self) -> bool:
        """Load the persisted topology map (if any) into the scene.

        Returns True when a non-empty map was restored.  Missing/corrupt files
        leave the tab empty (returns False) without raising.
        """
        path = self.layout_path or default_map_path()
        graph, positions, groups = load_map(path)
        if not graph.devices:
            return False
        self._scene.set_graph_from_persisted(graph, positions, groups)
        for item in self._scene.node_items.values():
            item.moved.connect(self._schedule_save)
        self.fit_in_view()
        return True

    def _schedule_save(self, *args) -> None:
        if hasattr(self, 'minimap'):
            self.minimap.refresh_bounds()
        if self.layout_path:
            self._save_timer.start()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._place_minimap()
        self._place_legend()
        self._place_nav_dock()
        if hasattr(self, 'minimap'):
            self.minimap.refresh_bounds()

    def _place_legend(self) -> None:
        self._legend.move(10, self.height() - self._legend.height() - 10)
        self._legend.raise_()

    def _place_minimap(self) -> None:
        self.minimap.move(self.width() - self.minimap.width() - 10,
                          self.height() - self.minimap.height() - 10)
        self.minimap.raise_()

    def _place_nav_dock(self) -> None:
        if hasattr(self, 'nav_dock'):
            self.nav_dock.move(14, 14)
            self.nav_dock.raise_()

    def wheelEvent(self, event) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom *= factor
        self._zoom = max(0.1, min(self._zoom, 8.0))
        self.scale(factor, factor)
        if hasattr(self, 'minimap'):
            self.minimap.viewport().update()

    def mousePressEvent(self, event) -> None:
        if event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.MiddleButton):
            self._interaction_active = True
        if event.button() == Qt.MouseButton.MiddleButton:
            self._middle_pan_active = True
            self._middle_pan_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._middle_pan_active and self._middle_pan_pos is not None:
            delta = event.pos() - self._middle_pan_pos
            self._middle_pan_pos = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._interaction_active = False
        if event.button() == Qt.MouseButton.MiddleButton and self._middle_pan_active:
            self._middle_pan_active = False
            self._middle_pan_pos = None
            if self._scene._link_mode:
                self.setCursor(Qt.CursorShape.CrossCursor)
            else:
                self._update_interaction_mode()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def leaveEvent(self, event) -> None:
        self._middle_pan_active = False
        self._interaction_active = False
        super().leaveEvent(event)

    def set_interaction_mode(self, mode: str) -> None:
        """Set active interaction mode: 'select' (rubber band drag) or 'pan' (hand drag)."""
        self._interaction_mode = mode
        if not self._scene._link_mode:
            self._update_interaction_mode()

    def _update_interaction_mode(self) -> None:
        if self._interaction_mode == 'pan':
            self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        else:
            self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def load(self, graph: TopologyGraph, layout_mode: str = 'hierarchical') -> None:
        saved = load_layout(self.layout_path) if self.layout_path else {}
        saved_groups = load_group_layout(self.layout_path) if self.layout_path else {}
        self._scene.set_graph(graph, layout_mode, saved, saved_groups)
        for item in self._scene.node_items.values():
            item.moved.connect(self._schedule_save)
        for gnode in self._scene.group_items.values():
            gnode.moved.connect(self._schedule_save)
        self.fit_in_view()

    def load_merged(self, graph: TopologyGraph, new_ids: set,
                    layout_mode: str = 'hierarchical') -> None:
        """Rebuild the scene after a discovery merge.

        Existing devices keep their current positions; newly discovered devices
        (``new_ids``) are laid out by the engine and shifted to the right of the
        existing bounding box.
        """
        old_positions = {did: pos for did, pos in self.current_positions().items()
                         if did not in new_ids}
        old_groups = self.current_group_positions()
        self._scene.set_graph(graph, layout_mode, old_positions, old_groups)
        self._offset_new_devices(new_ids, old_positions)
        for item in self._scene.node_items.values():
            item.moved.connect(self._schedule_save)
        for gnode in self._scene.group_items.values():
            gnode.moved.connect(self._schedule_save)
        self.fit_in_view()

    def _offset_new_devices(self, new_ids: set,
                            old_positions: dict[str, tuple[float, float]]) -> None:
        """Shift newly discovered nodes to the right of the existing bbox."""
        if not new_ids or not old_positions:
            return
        new_nodes = [self._scene.node_items[d] for d in new_ids
                     if d in self._scene.node_items]
        if not new_nodes:
            return
        old_right = max(p[0] for p in old_positions.values())
        new_left = min(n.pos().x() for n in new_nodes)
        dx = (old_right + 260.0) - new_left
        for n in new_nodes:
            n.setPos(n.pos().x() + dx, n.pos().y())

    def zoom_in(self) -> None:
        factor = 1.2
        if self._zoom * factor <= 8.0:
            self._zoom *= factor
            self.scale(factor, factor)
            if hasattr(self, 'minimap'):
                self.minimap.viewport().update()

    def zoom_out(self) -> None:
        factor = 1 / 1.2
        if self._zoom * factor >= 0.1:
            self._zoom *= factor
            self.scale(factor, factor)
            if hasattr(self, 'minimap'):
                self.minimap.viewport().update()

    def fit_in_view(self) -> None:
        rect = self._scene.itemsBoundingRect()
        if rect.isValid():
            self.fitInView(rect, Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = self.transform().m11()
            if hasattr(self, 'minimap'):
                self.minimap.refresh_bounds()

    def zoom_reset(self) -> None:
        """Reset view zoom to 100% (scale 1.0)."""
        current_zoom = self.transform().m11()
        if current_zoom != 0:
            factor = 1.0 / current_zoom
            self._zoom = 1.0
            self.scale(factor, factor)
            if hasattr(self, 'minimap'):
                self.minimap.viewport().update()

    def highlight_matches(self, query: str) -> list[str]:
        """Highlight nodes matching query (IP, label, vendor, model, etc.) and return IDs."""
        q = query.strip().lower()
        matched_ids: list[str] = []
        for did, node in self._scene.node_items.items():
            if not q:
                node.set_search_highlight(False)
                continue
            dev = node.device
            texts = [
                dev.ip or '',
                dev.label or '',
                dev.vendor or '',
                dev.model or '',
                dev.role.value or '',
                dev.chassis_id or '',
            ]
            for iface in dev.interfaces.values():
                if iface.name:
                    texts.append(iface.name)
                if iface.descr:
                    texts.append(iface.descr)
                if iface.mac:
                    texts.append(iface.mac)
            match = any(q in t.lower() for t in texts if t)
            node.set_search_highlight(match)
            if match:
                matched_ids.append(did)
        return matched_ids

    def focus_device(self, device_id: str) -> bool:
        """Center the view on the specified device with a comfortable zoom level."""
        node = self._scene.node_items.get(device_id)
        if node is None:
            return False
        self.centerOn(node)
        current_zoom = self.transform().m11()
        target_zoom = 1.0
        if current_zoom < 0.7 or current_zoom > 1.8:
            factor = target_zoom / current_zoom
            self._zoom = target_zoom
            self.scale(factor, factor)
        self._scene.clearSelection()
        node.setSelected(True)
        return True

    def fit_layer(self, layer_names: set[str] | str) -> None:
        """Fit view to nodes belonging to the specified layer(s)."""
        if isinstance(layer_names, str):
            layer_names = {layer_names}
        rect = QRectF()
        first = True
        for item in self._scene.node_items.values():
            if item.device.layers & layer_names:
                r = item.sceneBoundingRect()
                rect = r if first else rect.united(r)
                first = False
        if not first and rect.isValid():
            self.fitInView(rect.adjusted(-100, -100, 100, 100),
                           Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = self.transform().m11()

    def set_visible_levels(self, levels: Optional[set]) -> None:
        """Filter the canvas to the given hop levels (None = show all)."""
        self._scene.set_visible_levels(levels)
        self._fit_visible()

    def set_visible_layers(self, layers: Optional[set]) -> None:
        """Filter the canvas to the given named layers (None = show all)."""
        self._scene.set_visible_layers(layers)
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

    def set_link_mode(self, on: bool) -> None:
        """Toggle manual link-creation mode (cross cursor, no pan-drag)."""
        self._scene.set_link_mode(on)
        if on:
            self.setCursor(Qt.CursorShape.CrossCursor)
            self.setDragMode(QGraphicsView.DragMode.NoDrag)
        else:
            self._update_interaction_mode()

    def add_manual_link(self, source_id: str, source_port: str,
                        target_id: str, target_port: str,
                        speed: Optional[float] = None,
                        push_undo: bool = True) -> Optional[str]:
        """Create a manual link; returns an error message or None on success."""
        err = self._scene.add_manual_link(source_id, source_port,
                                          target_id, target_port, speed)
        if err is None:
            if push_undo:
                self.undo_stack.push(AddLinkCommand(
                    self, source_id, source_port, target_id, target_port, speed))
            self._schedule_save()
        return err

    def add_manual_device(self, role: DeviceRole, pos: QPointF) -> Device:
        """Add a manually-placed device (from the palette) and wire its save."""
        device = self._scene.add_manual_device(role, pos)
        self._scene.node_items[device.id].moved.connect(self._schedule_save)
        self.undo_stack.push(AddDeviceCommand(self, device, pos))
        self._schedule_save()
        return device

    def add_device_node(self, device: Device, pos: QPointF) -> None:
        """Add a discovered device node (progressive display); wires its save."""
        node = self._scene.add_device_node(device, pos)
        node.moved.connect(self._schedule_save)

    def clear_scene(self) -> None:
        """Remove all items and reset the scene (used before a new discovery)."""
        self.set_link_mode(False)
        self._scene.clear()
        self._scene.node_items = {}
        self._scene.edge_items = []
        self._scene.group_items = {}
        self._scene.group_links = []
        self._scene.graph = None
        self._scene.clusters = {}
        self._scene._manual_counter = 0

    def _confirm_deletion(self, text: str) -> bool:
        """Prompt the user with a dark-styled confirmation dialog before deleting."""
        box = QMessageBox(self)
        box.setWindowTitle('Confirmar Exclusão')
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Question)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        yes_btn = box.button(QMessageBox.StandardButton.Yes)
        if yes_btn:
            yes_btn.setText('Sim')
        no_btn = box.button(QMessageBox.StandardButton.No)
        if no_btn:
            no_btn.setText('Não')
        box.setStyleSheet("""
            QMessageBox {
                background-color: #161B22;
                color: #C9D1D9;
            }
            QLabel {
                color: #C9D1D9;
                font-size: 10pt;
            }
            QPushButton {
                background-color: #21262D;
                color: #C9D1D9;
                border: 1px solid #30363D;
                border-radius: 4px;
                padding: 6px 18px;
                min-width: 65px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #30363D;
                color: #ffffff;
            }
        """)
        return box.exec() == QMessageBox.StandardButton.Yes

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape and self._scene._link_mode:
            self.set_link_mode(False)
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            selected = self._scene.selectedItems()
            nodes_to_remove = [item for item in selected if isinstance(item, NodeItem)]
            edges_to_remove = [item for item in selected if isinstance(item, EdgeItem)]
            if not nodes_to_remove and not edges_to_remove:
                return

            parts = []
            if nodes_to_remove:
                if len(nodes_to_remove) == 1:
                    parts.append(f"o dispositivo '{nodes_to_remove[0].device.label}'")
                else:
                    parts.append(f"{len(nodes_to_remove)} dispositivos")
            if edges_to_remove:
                if len(edges_to_remove) == 1:
                    e = edges_to_remove[0]
                    parts.append(f"a conexão '{e.link.source_port} ⟷ {e.link.target_port}'")
                else:
                    parts.append(f"{len(edges_to_remove)} conexões")

            msg = f"Deseja realmente remover {' e '.join(parts)}?"
            if not self._confirm_deletion(msg):
                return

            self.undo_stack.beginMacro('Delete Items')
            for edge in edges_to_remove:
                self._scene.remove_edge(edge)
            for item in nodes_to_remove:
                dev = item.device
                pos = item.pos()
                connected_links = []
                if self._scene.graph is not None:
                    connected_links = [l for l in self._scene.graph.links
                                       if l.source_id == dev.id or l.target_id == dev.id]
                self._scene.remove_node(dev.id)
                self.undo_stack.push(RemoveDeviceCommand(self, dev, pos, connected_links))
            self.undo_stack.endMacro()
            self._schedule_save()
            return
        super().keyPressEvent(event)

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
            edge.refresh_state()

    def update_speeds(self, data: dict) -> None:
        """Apply live interface speeds (ifHighSpeed) and refresh edges.

        ``data`` is ``{device_id: {ifindex: float Mbps}}``.
        """
        for device_id, speeds in data.items():
            device = None
            node = self._scene.node_items.get(device_id)
            if node is not None:
                device = node.device
            elif self._scene.graph is not None:
                device = self._scene.graph.devices.get(device_id)
            if device is None:
                continue
            for idx, mbps in speeds.items():
                iface = device.interfaces.get(idx)
                if iface is not None:
                    iface.speed_mbps = mbps
        for edge in self._scene.edge_items:
            edge.update()

    def update_statuses(self, data: dict) -> None:
        """Apply live interface oper-status (ifOperStatus) and refresh edges.

        ``data`` is ``{device_id: {ifindex: 'up'|'down'|'unknown'}}``.
        """
        for device_id, statuses in data.items():
            device = None
            node = self._scene.node_items.get(device_id)
            if node is not None:
                device = node.device
            elif self._scene.graph is not None:
                device = self._scene.graph.devices.get(device_id)
            if device is None:
                continue
            for idx, status in statuses.items():
                iface = device.interfaces.get(idx)
                if iface is not None:
                    iface.oper_status = status
        for edge in self._scene.edge_items:
            edge.refresh_state()

    def update_layer_color(self, layer_name: str, color_hex: str) -> None:
        """Update layer color in graph and repaint all affected nodes."""
        if self._scene.graph is not None:
            if not hasattr(self._scene.graph, 'layer_colors') or self._scene.graph.layer_colors is None:
                self._scene.graph.layer_colors = {}
            self._scene.graph.layer_colors[layer_name] = color_hex
        for node in self._scene.node_items.values():
            node.update()
        self._schedule_save()

    def change_device_role(self, device_id: str, new_role: DeviceRole) -> None:
        """Update role of a device and redraw its node."""
        self.change_devices_role([device_id], new_role)

    def change_devices_role(self, device_ids: list[str], new_role: DeviceRole) -> None:
        """Update role of multiple devices and redraw their nodes."""
        changed = False
        for device_id in device_ids:
            device = None
            node = self._scene.node_items.get(device_id)
            if node is not None:
                device = node.device
            elif self._scene.graph is not None:
                device = self._scene.graph.devices.get(device_id)
            if device is not None:
                device.role = new_role
                if node is not None:
                    node.refresh_tooltip()
                    node.update()
                changed = True
        if changed:
            self._schedule_save()

    def change_device_layer(self, device_id: str, new_layer: str) -> None:
        """Move a device to a new layer, updating layers and redrawing node."""
        self.change_devices_layer([device_id], new_layer)

    def change_devices_layer(self, device_ids: list[str], new_layer: str) -> None:
        """Move multiple devices to a new layer, updating layers and redrawing nodes."""
        import re
        m = re.search(r'-(\d+)$', new_layer)
        layer_num = int(m.group(1)) if m else 1
        changed = False
        for device_id in device_ids:
            device = None
            node = self._scene.node_items.get(device_id)
            if node is not None:
                device = node.device
            elif self._scene.graph is not None:
                device = self._scene.graph.devices.get(device_id)
            if device is not None:
                device.layer = layer_num
                device.layers = {new_layer}
                if node is not None:
                    node.refresh_tooltip()
                    node.update()
                changed = True
        if changed:
            self._schedule_save()

    def remove_nodes(self, devices: list[Device]) -> None:
        """Remove multiple device nodes from the canvas and schedule an auto-save."""
        changed = False
        for dev in devices:
            if self._scene.remove_node(dev.id):
                changed = True
        if changed:
            self._schedule_save()



def load_graph(graph: TopologyGraph, layout_mode: str = 'hierarchical') -> TopologyView:
    """Create a standalone :class:`TopologyView` populated with ``graph``."""
    view = TopologyView()
    view.load(graph, layout_mode)
    view.resize(1000, 700)
    return view
