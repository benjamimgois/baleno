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
from PyQt6.QtGui import QColor, QDrag, QFont, QPainter, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QComboBox, QProgressBar, QMessageBox,
    QApplication, QMenu, QToolButton, QCheckBox, QButtonGroup,
    QStackedWidget, QFileDialog, QScrollArea,
)

from cetuslib.topology.collector import SnmpCredentials
from cetuslib.topology.worker import TopologyDiscoveryWorker
from cetuslib.topology.monitor import TrafficMonitor
from cetuslib.topology.models import Device, DeviceRole
from cetuslib.topology.gui.view import (
    TopologyView, DEVICE_MIME, role_renderer,
)
from cetuslib.topology.gui.detail import DeviceDetailDialog, GroupDevicesDialog
from cetuslib.topology.persistence import default_map_path
from cetuslib.topology.actions import TopologyActions

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

        root.addWidget(self._build_ribbon_tabs())
        self.ribbon_stack = QStackedWidget()
        self.ribbon_stack.addWidget(self._build_discovery_page())
        self.ribbon_stack.addWidget(self._build_devices_page())
        self.ribbon_stack.addWidget(self._build_settings_page())
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
        for index, label in enumerate(('Discovery', 'Objects', 'Settings')):
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
        row0.addWidget(self.networks_edit, 1)
        self.discover_btn = QPushButton('Discover')
        self.discover_btn.clicked.connect(self.start_discovery)
        row0.addWidget(self.discover_btn)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setFixedWidth(160)
        row0.addWidget(self.progress)
        self.status_label = QLabel('Idle')
        self.status_label.setMinimumWidth(120)
        row0.addWidget(self.status_label)
        layout.addLayout(row0)

        row1 = QHBoxLayout()
        row1.setSpacing(8)
        row1.addWidget(QLabel('Layout:'))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem('Hierarchical (tree)', 'hierarchical')
        self.layout_combo.addItem('Force-directed', 'force')
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        row1.addWidget(self.layout_combo)
        fit_btn = QPushButton('Fit')
        fit_btn.clicked.connect(self.view.fit_in_view)
        row1.addWidget(fit_btn)
        row1.addSpacing(16)
        row1.addWidget(QLabel('Levels:'))
        self.levels_layout = QHBoxLayout()
        self.levels_layout.setContentsMargins(0, 0, 0, 0)
        self.levels_layout.setSpacing(6)
        row1.addLayout(self.levels_layout)
        row1.addStretch(1)
        layout.addLayout(row1)
        self.level_checkboxes: list[QCheckBox] = []

        row2 = QHBoxLayout()
        row2.setSpacing(8)
        row2.addWidget(QLabel('SNMP:'))
        self.version_combo = QComboBox()
        self.version_combo.addItem('v2c', '2c')
        self.version_combo.addItem('v1', '1')
        self.version_combo.addItem('v3', '3')
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        row2.addWidget(self.version_combo)
        row2.addWidget(QLabel('Community:'))
        self.community_edit = QLineEdit('public')
        self.community_hist_btn = QToolButton()
        self.community_hist_btn.setText('▾')
        self.community_hist_btn.setToolTip('Community history (inherited from the SNMP tab)')
        self.community_hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.community_hist_btn.clicked.connect(self._show_community_menu)
        row2.addWidget(self.community_edit, 1)
        row2.addWidget(self.community_hist_btn)
        row2.addWidget(QLabel('User:'))
        self.username_edit = QLineEdit()
        row2.addWidget(self.username_edit)
        row2.addWidget(QLabel('Auth:'))
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(_AUTH_PROTOS)
        row2.addWidget(self.auth_combo)
        self.auth_pass_edit = QLineEdit()
        self.auth_pass_edit.setPlaceholderText('auth pass')
        self.auth_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        row2.addWidget(self.auth_pass_edit)
        row2.addWidget(QLabel('Priv:'))
        self.priv_combo = QComboBox()
        self.priv_combo.addItems(_PRIV_PROTOS)
        row2.addWidget(self.priv_combo)
        row2.addStretch(1)
        layout.addLayout(row2)

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
        if self._worker is not None and self._worker.isRunning():
            return

        self._remember()
        creds = self._credentials()
        self._worker = TopologyDiscoveryWorker(
            networks, creds,
            communities=self._community_list(),
            config=self._config,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.device_found.connect(self._on_device_found)
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self.view.clear_scene()
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
        self._graph = graph
        self.view.load(graph, self.layout_combo.currentData())
        self._rebuild_level_filters(graph)
        self.status_label.setText(
            f'{len(graph.devices)} nodes · {len(graph.links)} links · '
            f'{len(graph.orphans)} orphans')
        self.discover_btn.setEnabled(True)
        self._start_monitor(graph)
        self.view.save_map()

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f'Error: {message}')
        self.discover_btn.setEnabled(True)

    # ── interactions ─────────────────────────────────────────────────────

    def _on_layout_changed(self) -> None:
        if self._graph is not None:
            self.view.switch_layout(self.layout_combo.currentData())

    def _rebuild_level_filters(self, graph) -> None:
        while self.levels_layout.count():
            item = self.levels_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self.level_checkboxes = []

        hidden = self._hidden_levels()
        max_level = max((d.layer for d in graph.devices.values()), default=0)
        for lvl in range(1, max_level + 1):
            cb = QCheckBox(f'L{lvl}')
            cb.setChecked(lvl not in hidden)
            cb.setToolTip(f'Show level {lvl} devices')
            cb.toggled.connect(self._apply_level_filter)
            self.levels_layout.addWidget(cb)
            self.level_checkboxes.append(cb)
        self.levels_layout.addStretch(1)
        self._apply_level_filter()

    def _hidden_levels(self) -> set[int]:
        try:
            return set(json.loads(self._config.get('topology_hidden_levels') or '[]'))
        except (ValueError, TypeError):
            return set()

    def _apply_level_filter(self) -> None:
        active = {i + 1 for i, cb in enumerate(self.level_checkboxes)
                  if cb.isChecked()}
        hidden = [i + 1 for i, cb in enumerate(self.level_checkboxes)
                  if not cb.isChecked()]
        self._config.set('topology_hidden_levels', json.dumps(hidden))
        self.view.set_visible_levels(active)

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
        for w in (self.username_edit, self.auth_combo, self.auth_pass_edit,
                  self.priv_combo):
            w.setEnabled(is_v3)

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
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(15000)
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
        if self._monitor is not None:
            self._monitor.stop()
            self._monitor.wait(3000)
            self._monitor = None
