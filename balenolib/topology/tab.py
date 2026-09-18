"""Topology tab UI — Ribbon-style control bar + interactive topology canvas.

Three ribbon tabs (Discovery / Objects / Settings) expose the controls
above a dark topology canvas.  The whole tab is dark with a royal-blue accent.

- Discovery: ICMP + SNMP/LLDP discovery controls, layout and level filters.
- Objects: a palette of draggable device icons to drop onto the map.
- Settings: export the current map to PNG, save the layout.
"""

from __future__ import annotations

import json
import os

from PyQt6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, QTimer
from PyQt6.QtGui import QColor, QDrag, QFont, QPainter, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QComboBox, QProgressBar, QMessageBox,
    QApplication, QMenu, QToolButton, QCheckBox, QButtonGroup,
    QStackedWidget, QFileDialog, QScrollArea, QDialog,
)

from balenolib.topology.collector import SnmpCredentials
from balenolib.topology.worker import TopologyDiscoveryWorker
from balenolib.topology.monitor import TrafficMonitor
from balenolib.topology.models import Device, DeviceRole, TopologyGraph
from balenolib.topology.gui.view import (
    TopologyView, DEVICE_MIME, role_renderer, draw_layout_icon, draw_fit_icon,
    draw_link_icon, GroupNodeItem,
)
from balenolib.topology.gui.detail import (
    DeviceDetailDialog, GroupDevicesDialog, LinkCreationDialog,
)
from balenolib.topology.persistence import default_map_path
from balenolib.topology.actions import TopologyActions

__all__ = ['TopologyTab']

_ROYAL = '#4169E1'
_ROYAL_HOVER = '#3156C8'
_ROYAL_PRESS = '#2949A8'
_BG = '#161B22'
_BG_INPUT = '#0D1117'
_BG_RIBBON = '#1C2128'
_BORDER = '#30363D'
_TEXT = '#C9D1D9'

_TAB_STYLE = f"""
    QWidget#topologyRoot {{ background-color: {_BG}; }}
    QLabel {{ background: transparent; color: {_TEXT}; font-size: 9pt; border: none; }}
    QLineEdit {{
        background-color: {_BG_INPUT}; color: #E6EDF3;
        border: 1px solid {_BORDER}; border-radius: 6px;
        padding: 3px 8px; font-size: 9pt;
    }}
    QLineEdit:focus {{ border: 1px solid {_ROYAL}; }}
    QLineEdit:disabled {{ color: #6E7681; }}
    QComboBox {{
        background-color: {_BG_INPUT}; color: #E6EDF3;
        border: 1px solid {_BORDER}; border-radius: 6px;
        padding: 2px 6px; font-size: 9pt;
    }}
    QComboBox:focus {{ border: 1px solid {_ROYAL}; }}
    QComboBox QAbstractItemView {{
        background-color: {_BG_INPUT}; color: #E6EDF3;
        selection-background-color: {_ROYAL};
    }}
    QPushButton {{
        background-color: {_ROYAL}; color: #ffffff;
        border: none; border-radius: 6px;
        padding: 6px 14px; font-weight: bold; font-size: 9pt;
    }}
    QPushButton:hover {{ background-color: {_ROYAL_HOVER}; }}
    QPushButton:pressed {{ background-color: {_ROYAL_PRESS}; }}
    QPushButton:disabled {{ background-color: #2D333B; color: #6E7681; }}
    QProgressBar {{
        background-color: {_BG_INPUT}; border: 1px solid {_BORDER}; border-radius: 5px;
        color: {_TEXT}; font-size: 8pt; text-align: center; height: 14px;
    }}
    QProgressBar::chunk {{ background-color: {_ROYAL}; border-radius: 4px; }}
    QCheckBox {{ background: transparent; color: {_TEXT}; font-size: 9pt; spacing: 4px; }}
    QCheckBox::indicator {{
        width: 14px; height: 14px;
        border: 1px solid #6E7681; border-radius: 3px; background-color: {_BG_INPUT};
    }}
    QCheckBox::indicator:checked {{ background-color: {_ROYAL}; border-color: {_ROYAL}; }}
    QPushButton#ribbonTab {{
        background: transparent; color: #8B949E;
        border: none; border-bottom: 2px solid transparent;
        border-radius: 0; padding: 7px 18px;
        font-size: 10pt; font-weight: bold;
    }}
    QPushButton#ribbonTab:hover {{ color: #E6EDF3; background-color: {_BG_RIBBON}; }}
    QPushButton#ribbonTab:checked {{
        color: #E6EDF3; border-bottom: 2px solid {_ROYAL}; background-color: {_BG_RIBBON};
    }}
    QFrame#ribbonBody {{ background-color: {_BG_RIBBON}; border-bottom: 1px solid {_BORDER}; }}
    QFrame#ribbonBar {{ background-color: {_BG}; border: none; }}
"""

_AUTH_PROTOS = ['None', 'MD5', 'SHA', 'SHA224', 'SHA256', 'SHA384', 'SHA512']
_PRIV_PROTOS = ['None', 'DES', '3DES', 'AES', 'AES192', 'AES256']

_PALETTE = [
    (DeviceRole.ROUTER, 'Router'),
    (DeviceRole.CORE, 'Switch L3'),
    (DeviceRole.SWITCH, 'Switch L2'),
    (DeviceRole.FIREWALL, 'Firewall'),
    (DeviceRole.SERVER, 'Server'),
    (DeviceRole.AP, 'Wi-Fi'),
    (DeviceRole.HOST, 'PC'),
    (DeviceRole.PHONE, 'Phone'),
    (DeviceRole.CAMERA, 'Camera'),
    (DeviceRole.CLOUD, 'Cloud'),
    (DeviceRole.CLOUD2, 'Cloud 2'),
    (DeviceRole.CLOUD3, 'Cloud 3'),
    (DeviceRole.CLOUD4, 'Cloud 4'),
    (DeviceRole.INTERNET, 'Internet'),
    (DeviceRole.UNKNOWN, 'Unknown'),
]


class LayoutButton(QToolButton):
    """An icon button for one layout mode; exclusive via QButtonGroup."""

    def __init__(self, mode: str, label: str, parent=None):
        super().__init__(parent)
        self.mode = mode
        self._label = label
        self.setCheckable(True)
        self.setFixedSize(62, 50)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(f'Layout: {label}')

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            bg = QColor(40, 60, 120)
        elif self.underMouse():
            bg = QColor(28, 33, 40)
        else:
            bg = QColor(22, 27, 34)
        painter.fillRect(self.rect(), bg)
        draw_layout_icon(painter, self.mode,
                         QRectF(8, 5, self.width() - 16, self.height() - 22))
        painter.setPen(QColor(88, 166, 255) if self.isChecked() else QColor(201, 209, 217))
        painter.setFont(QFont('Sans', 7))
        painter.drawText(QRectF(0, self.height() - 15, self.width(), 13),
                         Qt.AlignmentFlag.AlignCenter, self._label)
        painter.end()


class FitButton(QToolButton):
    """An icon button that fits the map to the current view."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('Zoom FIT — fit map to view')

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(28, 33, 40) if self.underMouse() else QColor(22, 27, 34)
        painter.fillRect(self.rect(), bg)
        draw_fit_icon(painter, QRectF(8, 4, self.width() - 16, self.height() - 18))
        painter.setPen(QColor(201, 209, 217))
        painter.setFont(QFont('Sans', 7))
        painter.drawText(QRectF(0, self.height() - 14, self.width(), 12),
                         Qt.AlignmentFlag.AlignCenter, 'Fit')
        painter.end()


class LinkButton(QToolButton):
    """Toggle button that enters/exits manual link-creation mode."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setFixedSize(72, 70)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip('Create link — click two devices')

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self.isChecked():
            bg = QColor(40, 60, 120)
        elif self.underMouse():
            bg = QColor(28, 33, 40)
        else:
            bg = QColor(22, 27, 34)
        painter.fillRect(self.rect(), bg)
        draw_link_icon(painter, QRectF(10, 8, self.width() - 20, self.height() - 22))
        painter.setPen(QColor(88, 166, 255) if self.isChecked() else QColor(201, 209, 217))
        painter.setFont(QFont('Sans', 7))
        painter.drawText(QRectF(0, self.height() - 17, self.width(), 14),
                         Qt.AlignmentFlag.AlignCenter, 'Link')
        painter.end()


class DevicePaletteButton(QToolButton):
    """A device-type button in the palette; draggable onto the map."""

    def __init__(self, role: DeviceRole, label: str, parent=None):
        super().__init__(parent)
        self.role = role
        self._label = label
        self._renderer = role_renderer(role)
        self.setFixedSize(72, 70)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f'Drag a {label} onto the map')
        self._press_pos = None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(28, 33, 40) if (self.underMouse() or self.isDown()) else QColor(22, 27, 34)
        painter.fillRect(self.rect(), bg)
        if self._renderer is not None:
            r = 20.0
            self._renderer.render(
                painter, QRectF((self.width() - r * 2) / 2, 6, r * 2, r * 2))
        painter.setPen(QColor(201, 209, 217))
        painter.setFont(QFont('Sans', 7))
        painter.drawText(QRectF(0, self.height() - 17, self.width(), 14),
                         Qt.AlignmentFlag.AlignCenter, self._label)
        painter.end()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._press_pos = event.position().toPoint()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if (self._press_pos is not None
                and event.buttons() & Qt.MouseButton.LeftButton
                and (event.position().toPoint() - self._press_pos).manhattanLength()
                >= QApplication.startDragDistance()):
            self._start_drag()
            self._press_pos = None
            return
        super().mouseMoveEvent(event)

    def _start_drag(self) -> None:
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(DEVICE_MIME, self.role.value.encode('utf-8'))
        drag.setMimeData(mime)
        if self._renderer is not None:
            pixmap = QPixmap(48, 48)
            pixmap.fill(Qt.GlobalColor.transparent)
            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._renderer.render(p, QRectF(2, 2, 44, 44))
            p.end()
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(24, 24))
        drag.exec(Qt.DropAction.CopyAction)


class TopologyTab(QWidget):
    """Ribbon-style controls over the interactive topology canvas."""

    def __init__(self, config_manager, parent=None, main_window=None):
        super().__init__(parent)
        self._config = config_manager
        self._main = main_window
        self._worker = None
        self._monitor = None
        self._graph = None
        self._live_devices: dict[str, Device] = {}
        self.setObjectName('topologyRoot')
        self.setStyleSheet(_TAB_STYLE)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.view = TopologyView()
        self.view.set_layout_path(default_map_path())
        self.view._scene.node_double_clicked.connect(self._on_node_double_clicked)
        self.view._scene.group_clicked.connect(self._on_group_clicked)
        self.view._scene.node_context_menu_requested.connect(self._on_node_context_menu)
        self.view._scene.group_context_menu_requested.connect(self._on_group_context_menu)
        self.view._scene.link_requested.connect(self._on_link_requested)
        self.view._scene.link_mode_changed.connect(self._on_link_mode_changed)
        self._link_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Escape), self)
        self._link_shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._link_shortcut.activated.connect(self._cancel_link_mode)

        root.addWidget(self._build_ribbon_tabs())
        self.ribbon_stack = QStackedWidget()
        self.ribbon_stack.addWidget(self._build_discovery_page())
        self.ribbon_stack.addWidget(self._build_devices_page())
        self.ribbon_stack.addWidget(self._build_settings_page())
        self.ribbon_stack.addWidget(self._build_layouts_page())
        body = QFrame()
        body.setObjectName('ribbonBody')
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(10, 8, 10, 8)
        body_layout.addWidget(self.ribbon_stack)
        root.addWidget(body)
        root.addWidget(self.view, 1)

        if self.view.load_saved_map():
            self._graph = self.view._scene.graph
            self._rebuild_level_filters(self._graph)
        self._load_remembered()
        if self._graph is not None:
            self._start_monitor(self._graph)
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    # ── ribbon tab bar ───────────────────────────────────────────────────

    def _build_ribbon_tabs(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName('ribbonBar')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(6, 4, 6, 0)
        layout.setSpacing(2)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.ribbon_btns: dict[int, QPushButton] = {}
        for index, label in enumerate(('Discovery', 'Objects', 'Settings', 'Layouts')):
            btn = QPushButton(label)
            btn.setObjectName('ribbonTab')
            btn.setCheckable(True)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda _=False, i=index: self._switch_ribbon(i))
            self.tab_group.addButton(btn, index)
            layout.addWidget(btn)
            self.ribbon_btns[index] = btn
        layout.addStretch(1)
        self.ribbon_btns[0].setChecked(True)
        return bar

    def _switch_ribbon(self, index: int) -> None:
        self.ribbon_stack.setCurrentIndex(index)
        self.ribbon_btns[index].setChecked(True)

    # ── Discovery page ───────────────────────────────────────────────────

    def _build_discovery_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row0 = QHBoxLayout()
        row0.setSpacing(8)
        row0.addWidget(QLabel('Networks:'))
        self.networks_edit = QLineEdit()
        self.networks_edit.setPlaceholderText('10.0.0.0/24, 192.168.1.0/24')
        self.networks_edit.setFixedWidth(240)
        row0.addWidget(self.networks_edit)
        row0.addWidget(QLabel('Layer:'))
        self.layer_name_edit = QLineEdit()
        self.layer_name_edit.setPlaceholderText('Rede-A')
        self.layer_name_edit.setFixedWidth(100)
        row0.addWidget(self.layer_name_edit)
        self.discover_btn = QPushButton('Discover')
        self.discover_btn.clicked.connect(self.start_discovery)
        row0.addWidget(self.discover_btn)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(160)
        row0.addWidget(self.progress)
        row0.addSpacing(16)
        row0.addWidget(QLabel('SNMP:'))
        self.version_combo = QComboBox()
        self.version_combo.addItem('v2c', '2c')
        self.version_combo.addItem('v1', '1')
        self.version_combo.addItem('v3', '3')
        self.version_combo.setFixedWidth(72)
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        row0.addWidget(self.version_combo)
        row0.addWidget(QLabel('Community:'))
        self.community_edit = QLineEdit('public')
        self.community_edit.setFixedWidth(100)
        self.community_hist_btn = QToolButton()
        self.community_hist_btn.setText('▾')
        self.community_hist_btn.setToolTip('Community history (inherited from the SNMP tab)')
        self.community_hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.community_hist_btn.clicked.connect(self._show_community_menu)
        row0.addWidget(self.community_edit)
        row0.addWidget(self.community_hist_btn)
        self.status_label = QLabel('Idle')
        self.status_label.setMinimumWidth(120)
        row0.addWidget(self.status_label)
        row0.addStretch(1)
        layout.addLayout(row0)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        self.fit_btn = FitButton()
        self.fit_btn.clicked.connect(self.view.fit_in_view)
        row1.addWidget(self.fit_btn)
        row1.addWidget(QLabel('Levels:'))
        self.levels_layout = QHBoxLayout()
        self.levels_layout.setContentsMargins(0, 0, 0, 0)
        self.levels_layout.setSpacing(6)
        row1.addLayout(self.levels_layout)
        row1.addStretch(1)
        layout.addLayout(row1)
        self.level_checkboxes: list[QCheckBox] = []

        # SNMPv3 auth fields — only shown when v3 is selected
        self.v3_row = QWidget()
        v3_layout = QHBoxLayout(self.v3_row)
        v3_layout.setContentsMargins(0, 0, 0, 0)
        v3_layout.setSpacing(8)
        v3_layout.addWidget(QLabel('User:'))
        self.username_edit = QLineEdit()
        v3_layout.addWidget(self.username_edit)
        v3_layout.addWidget(QLabel('Auth:'))
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(_AUTH_PROTOS)
        v3_layout.addWidget(self.auth_combo)
        self.auth_pass_edit = QLineEdit()
        self.auth_pass_edit.setPlaceholderText('auth pass')
        self.auth_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        v3_layout.addWidget(self.auth_pass_edit)
        v3_layout.addWidget(QLabel('Priv:'))
        self.priv_combo = QComboBox()
        self.priv_combo.addItems(_PRIV_PROTOS)
        v3_layout.addWidget(self.priv_combo)
        v3_layout.addStretch(1)
        layout.addWidget(self.v3_row)

        self._on_version_changed()
        return page

    # ── Devices page ─────────────────────────────────────────────────────

    def _build_devices_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        hint = QLabel('Drag a device onto the map to add it manually.')
        hint.setStyleSheet('color: #8B949E;')
        layout.addWidget(hint)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; }')
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(8)
        self.link_btn = LinkButton()
        self.link_btn.toggled.connect(self._on_link_toggled)
        row_layout.addWidget(self.link_btn)
        for role, label in _PALETTE:
            row_layout.addWidget(DevicePaletteButton(role, label))
        row_layout.addStretch(1)
        scroll.setWidget(row)
        layout.addWidget(scroll)
        return page

    # ── Settings page ────────────────────────────────────────────────────

    def _build_settings_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        row = QHBoxLayout()
        row.setSpacing(8)
        export_btn = QPushButton('Export PNG')
        export_btn.clicked.connect(self._export_png)
        row.addWidget(export_btn)
        save_btn = QPushButton('Save Map')
        save_btn.clicked.connect(self._save_map)
        row.addWidget(save_btn)
        self.save_feedback = QLabel('')
        self.save_feedback.setStyleSheet('color: #3FB950; font-weight: bold;')
        row.addWidget(self.save_feedback)
        row.addStretch(1)
        layout.addLayout(row)

        self._save_feedback_timer = QTimer(self)
        self._save_feedback_timer.setSingleShot(True)
        self._save_feedback_timer.setInterval(2500)
        self._save_feedback_timer.timeout.connect(self._clear_save_feedback)
        return page

    # ── Layouts page ─────────────────────────────────────────────────────

    def _build_layouts_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        row = QHBoxLayout()
        row.setSpacing(8)
        self.layout_buttons: list[LayoutButton] = []
        self.layout_group = QButtonGroup(self)
        self.layout_group.setExclusive(True)
        for mode, label in (('hierarchical', 'Tree'), ('force', 'Force'),
                            ('concentric', 'Radial'), ('bfs', 'BFS')):
            btn = LayoutButton(mode, label)
            self.layout_group.addButton(btn)
            self.layout_buttons.append(btn)
            row.addWidget(btn)
        row.addStretch(1)
        self.layout_buttons[0].setChecked(True)
        self.layout_group.buttonClicked.connect(self._on_layout_clicked)
        layout.addLayout(row)
        layout.addStretch(1)
        return page

    def _save_map(self) -> None:
        """Save the full map and show transient visual confirmation."""
        self.view.save_map()
        path = self.view.layout_path or ''
        name = os.path.basename(path) if path else ''
        self.save_feedback.setText(f'✓ Map saved{f" to {name}" if name else ""}')
        self._save_feedback_timer.start()

    def _clear_save_feedback(self) -> None:
        self.save_feedback.setText('')

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export topology map', 'topology.png', 'PNG image (*.png)')
        if not path:
            return
        if self.view.export_png(path):
            self.status_label.setText(f'Exported {path}')
        else:
            QMessageBox.warning(self, 'Topology', 'Nothing to export (empty map).')

    # ── discovery workflow ───────────────────────────────────────────────

    def _credentials(self) -> SnmpCredentials:
        return SnmpCredentials(
            version=self.version_combo.currentData(),
            community=self.community_edit.text().strip() or 'public',
            username=self.username_edit.text().strip(),
            auth_proto=self.auth_combo.currentText(),
            auth_pass=self.auth_pass_edit.text(),
            priv_proto=self.priv_combo.currentText(),
            priv_pass=self.auth_pass_edit.text(),
        )

    def start_discovery(self) -> None:
        networks = [n.strip() for n in self.networks_edit.text().split(',') if n.strip()]
        if not networks:
            QMessageBox.warning(self, 'Topology', 'Enter at least one network (CIDR or IP).')
            return
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    return
            except RuntimeError:
                self._worker = None

        self._remember()
        creds = self._credentials()
        layer_name = self.layer_name_edit.text().strip()
        self._worker = TopologyDiscoveryWorker(
            networks, creds,
            communities=self._community_list(),
            config=self._config,
            layer_name=layer_name,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.device_found.connect(self._on_device_found)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self._live_devices: dict[str, Device] = {}
        self.discover_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText('Scanning…')
        self._worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.status_label.setText(message)

    def _on_device_found(self, device) -> None:
        """Show a device on the map as soon as it is detected (progressive)."""
        idx = len(self._live_devices)
        x = (idx % 10) * 190 - 855
        y = (idx // 10) * 140 - 300
        self.view.add_device_node(device, QPointF(x, y))
        self._live_devices[device.id] = device

    def _on_finished(self, graph) -> None:
        self._worker = None
        try:
            self._stop_monitor()
            if self._graph is None:
                self._graph = graph
                new_ids = set(graph.devices.keys())
            else:
                new_ids = set(graph.devices.keys()) - set(self._graph.devices.keys())
                self._merge_graphs(self._graph, graph)
            self.view.load_merged(self._graph, new_ids, self._current_layout())
            self._rebuild_level_filters(self._graph)
            self.status_label.setText(
                f'{len(self._graph.devices)} nodes · {len(self._graph.links)} links · '
                f'{len(self._graph.orphans)} orphans')
            self.discover_btn.setEnabled(True)
            self._start_monitor(self._graph)
            self.view.save_map()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.status_label.setText(f'Error merging discovery: {exc}')
            self.discover_btn.setEnabled(True)

    def _merge_graphs(self, target: TopologyGraph, incoming: TopologyGraph) -> None:
        """Merge ``incoming`` into ``target`` in place, deduplicating devices by id."""
        for did, dev in incoming.devices.items():
            existing = target.devices.get(did)
            if existing is None:
                target.devices[did] = dev
            else:
                existing.layers |= dev.layers
                for idx, iface in dev.interfaces.items():
                    if idx not in existing.interfaces:
                        existing.interfaces[idx] = iface
        for link in incoming.links:
            if not any(link.key() == l.key() for l in target.links):
                target.links.append(link)

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.status_label.setText(f'Error: {message}')
        self.discover_btn.setEnabled(True)

    # ── interactions ─────────────────────────────────────────────────────

    def _current_layout(self) -> str:
        checked = self.layout_group.checkedButton()
        return checked.mode if checked is not None else 'hierarchical'

    def _on_layout_clicked(self, button) -> None:
        if self._graph is not None:
            self.view.switch_layout(button.mode)

    def _rebuild_level_filters(self, graph) -> None:
        while self.levels_layout.count():
            item = self.levels_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.level_checkboxes = []

        hidden = self._hidden_layers()
        layers = sorted({layer for d in graph.devices.values() for layer in d.layers})
        for layer in layers:
            cb = QCheckBox(layer)
            cb.setChecked(layer not in hidden)
            cb.setToolTip(f'Show/hide layer {layer}')
            cb.toggled.connect(self._apply_layer_filter)
            self.levels_layout.addWidget(cb)
            self.level_checkboxes.append(cb)
        self.levels_layout.addStretch(1)
        self._apply_layer_filter()

    def _hidden_layers(self) -> set[str]:
        try:
            return set(json.loads(self._config.get('topology_hidden_layers') or '[]'))
        except (ValueError, TypeError):
            return set()

    def _apply_layer_filter(self) -> None:
        visible = {cb.text() for cb in self.level_checkboxes if cb.isChecked()}
        hidden = [cb.text() for cb in self.level_checkboxes if not cb.isChecked()]
        self._config.set('topology_hidden_layers', json.dumps(hidden))
        self.view.set_visible_layers(visible)

    def _on_node_double_clicked(self, device) -> None:
        dialog = DeviceDetailDialog(device, self)
        dialog.device_changed.connect(self.view.on_device_changed)
        dialog.show()

    def _on_group_clicked(self, group) -> None:
        GroupDevicesDialog(group.members(), self).show()

    def _on_node_context_menu(self, device, pos) -> None:
        if self._main is None:
            return
        TopologyActions.show_node_menu(self._main, device, pos)

    def _on_group_context_menu(self, group, pos) -> None:
        if self._main is None:
            return
        TopologyActions.show_group_menu(self._main, group, pos)

    # ── manual link creation ─────────────────────────────────────────────

    def _on_link_toggled(self, checked: bool) -> None:
        self.view.set_link_mode(checked)

    def _on_link_mode_changed(self, on: bool) -> None:
        self.link_btn.blockSignals(True)
        self.link_btn.setChecked(on)
        self.link_btn.blockSignals(False)

    def _cancel_link_mode(self) -> None:
        if self.view._scene._link_mode:
            self.view.set_link_mode(False)

    @staticmethod
    def _endpoint_info(item):
        if isinstance(item, GroupNodeItem):
            dev = item.graph.devices.get(item.parent_id)
            label = dev.label if dev is not None else item.parent_id
            return item.parent_id, label, []
        ifaces = sorted(item.device.interfaces.values(), key=lambda i: i.index)
        return item.device.id, item.device.label, ifaces

    def _on_link_requested(self, source, target) -> None:
        src_id, src_label, src_ifaces = self._endpoint_info(source)
        dst_id, dst_label, dst_ifaces = self._endpoint_info(target)
        dialog = LinkCreationDialog(src_label, src_ifaces, dst_label, dst_ifaces, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            err = self.view.add_manual_link(
                src_id, dialog.source_port(), dst_id, dialog.target_port(),
                dialog.speed())
            if err:
                QMessageBox.warning(self, 'Link', err)
        self.view.set_link_mode(False)

    def _show_community_menu(self) -> None:
        history = self._config.get_vuln_community_history()
        menu = QMenu(self)
        if not history:
            act = menu.addAction('No history yet')
            act.setEnabled(False)
        else:
            for c in history:
                menu.addAction(c)
        btn = self.community_hist_btn
        chosen = menu.exec(btn.mapToGlobal(btn.rect().bottomLeft()))
        if chosen and chosen.isEnabled():
            self.community_edit.setText(chosen.text())

    def _community_list(self) -> list[str]:
        ordered: list[str] = []
        cur = self.community_edit.text().strip()
        if cur:
            ordered.append(cur)
        for c in self._config.get_vuln_community_history():
            if c and c not in ordered:
                ordered.append(c)
        if not ordered:
            ordered.append('public')
        return ordered

    def _on_version_changed(self) -> None:
        is_v3 = self.version_combo.currentData() == '3'
        self.community_edit.setEnabled(not is_v3)
        self.community_hist_btn.setEnabled(not is_v3)
        self.v3_row.setVisible(is_v3)

    # ── persistence of UI preferences ────────────────────────────────────

    def _remember(self) -> None:
        self._config.set('topology_networks', self.networks_edit.text())
        self._config.set('topology_snmp_version', self.version_combo.currentData())
        self._config.set('topology_community', self.community_edit.text())
        self._config.set('topology_username', self.username_edit.text())
        community = self.community_edit.text().strip()
        if community:
            self._config.add_vuln_community(community)

    def _load_remembered(self) -> None:
        nets = self._config.get('topology_networks')
        if nets:
            self.networks_edit.setText(nets)
        community = self._config.get('topology_community')
        if community:
            self.community_edit.setText(community)
        else:
            history = self._config.get_vuln_community_history()
            if history:
                self.community_edit.setText(history[0])
        username = self._config.get('topology_username')
        if username:
            self.username_edit.setText(username)
        version = self._config.get('topology_snmp_version')
        if version:
            idx = self.version_combo.findData(version)
            if idx >= 0:
                self.version_combo.setCurrentIndex(idx)

    def shutdown(self) -> None:
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    self._worker.stop()
                    self._worker.wait(15000)
            except RuntimeError:
                self._worker = None
        self._stop_monitor()

    # ── live performance monitor ─────────────────────────────────────────

    def _start_monitor(self, graph) -> None:
        self._stop_monitor()
        devices = [d for d in graph.devices.values()
                   if d.ip and d.status == 'up' and d.interfaces]
        if not devices:
            return
        self._monitor = TrafficMonitor(
            devices, self._credentials(),
            communities=self._community_list(),
            config=self._config,
        )
        self._monitor.updated.connect(self.view.update_traffic)
        self._monitor.status_updated.connect(self.view.update_statuses)
        self._monitor.speed_updated.connect(self.view.update_speeds)
        self._monitor.start()

    def _stop_monitor(self) -> None:
        if self._monitor is None:
            return
        mon = self._monitor
        self._monitor = None
        # Detach from the view so a still-running monitor can't touch the scene
        # while it is being merged/rebuild during the next discovery.
        for sig in (mon.updated, mon.status_updated, mon.speed_updated):
            try:
                sig.disconnect()
            except TypeError:
                pass
        mon.stop()
        if not mon.wait(3000):
            # Still running (mid-SNMP): schedule deletion on finish instead of
            # destroying a live QThread (which aborts the application).
            mon.finished.connect(mon.deleteLater)
        else:
            mon.deleteLater()
