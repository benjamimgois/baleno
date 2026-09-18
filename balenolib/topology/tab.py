"""Topology tab UI — Studio / CAD layout with compact topbar and GIMP-style layers.

Single-row topbar for discovery inputs, status, layout switcher, and map actions.
Retractable sidebar on the right hosting:
- GIMP-style hierarchical layer tree (expand/collapse, eye icons, context menu).
- Draggable device objects palette.
Floating canvas dock for zoom, fit, and link creation.
"""

from __future__ import annotations

import json
import os

from PyQt6.QtCore import (
    QMimeData, QPoint, QPointF, QRectF, Qt, QTimer,
    QPropertyAnimation, QEasingCurve,
)
from PyQt6.QtGui import QColor, QDrag, QFont, QPainter, QPixmap, QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QFrame,
    QPushButton, QLineEdit, QComboBox, QProgressBar, QMessageBox,
    QApplication, QMenu, QToolButton, QFileDialog, QScrollArea, QDialog,
    QColorDialog,
)

from balenolib.topology.collector import SnmpCredentials
from balenolib.topology.worker import TopologyDiscoveryWorker
from balenolib.topology.monitor import TrafficMonitor
from balenolib.topology.models import Device, DeviceRole, TopologyGraph
from balenolib.topology.gui.view import (
    TopologyView, DEVICE_MIME, role_renderer, GroupNodeItem, NodeItem,
)
from balenolib.topology.gui.layers import LayerTreeWidget, make_color_icon
from balenolib.topology.gui.accordion import AccordionWidget, CollapsibleSection
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
_BORDER = '#30363D'
_TEXT = '#C9D1D9'
_TEXT_MUTED = '#8B949E'

_TAB_STYLE = f"""
    QWidget#topologyRoot {{ background-color: {_BG}; }}
    QLabel {{ background: transparent; color: {_TEXT}; font-size: 9pt; border: none; }}
    QLineEdit {{
        background-color: {_BG_INPUT}; color: #E6EDF3;
        border: 1px solid {_BORDER}; border-radius: 6px;
        padding: 4px 8px; font-size: 9pt;
    }}
    QLineEdit:focus {{ border: 1px solid {_ROYAL}; }}
    QLineEdit:disabled {{ color: #6E7681; }}
    QComboBox {{
        background-color: {_BG_INPUT}; color: #E6EDF3;
        border: 1px solid {_BORDER}; border-radius: 6px;
        padding: 3px 8px; font-size: 9pt;
    }}
    QComboBox:focus {{ border: 1px solid {_ROYAL}; }}
    QComboBox QAbstractItemView {{
        background-color: {_BG_INPUT}; color: #E6EDF3;
        selection-background-color: {_ROYAL};
    }}
    QPushButton {{
        background-color: {_ROYAL}; color: #ffffff;
        border: none; border-radius: 6px;
        padding: 5px 14px; font-weight: bold; font-size: 9pt;
    }}
    QPushButton:hover {{ background-color: {_ROYAL_HOVER}; }}
    QPushButton:pressed {{ background-color: {_ROYAL_PRESS}; }}
    QPushButton:disabled {{ background-color: #2D333B; color: #6E7681; }}
    QToolButton {{
        background-color: {_BG_INPUT}; color: {_TEXT};
        border: 1px solid {_BORDER}; border-radius: 6px;
        padding: 4px 8px; font-size: 9pt;
    }}
    QToolButton:hover {{
        background-color: #21262D; border-color: {_ROYAL}; color: #FFFFFF;
    }}
    QToolButton:checked {{
        background-color: #24355A; border-color: {_ROYAL}; color: #58A6FF;
    }}
    QProgressBar {{
        background-color: {_BG_INPUT}; border: 1px solid {_BORDER}; border-radius: 5px;
        color: {_TEXT}; font-size: 8pt; text-align: center; height: 14px;
    }}
    QProgressBar::chunk {{ background-color: {_ROYAL}; border-radius: 4px; }}
    QFrame#topBar {{
        background-color: {_BG}; border-bottom: 1px solid {_BORDER};
    }}
    QFrame#topologySidebar {{
        background-color: {_BG}; border-right: 1px solid {_BORDER};
    }}
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
        self.setFixedSize(68, 54)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self.setToolTip(f'Drag a {label} onto the map')
        self._press_pos = None

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        bg = QColor(28, 33, 40) if (self.underMouse() or self.isDown()) else QColor(22, 27, 34)
        painter.fillRect(self.rect(), bg)
        if self._renderer is not None:
            r = 15.0
            self._renderer.render(
                painter, QRectF((self.width() - r * 2) / 2, 4, r * 2, r * 2))
        painter.setPen(QColor(201, 209, 217))
        painter.setFont(QFont('Sans', 7))
        painter.drawText(QRectF(0, self.height() - 14, self.width(), 12),
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
            pixmap = QPixmap(44, 44)
            pixmap.fill(Qt.GlobalColor.transparent)
            p = QPainter(pixmap)
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            self._renderer.render(p, QRectF(2, 2, 40, 40))
            p.end()
            drag.setPixmap(pixmap)
            drag.setHotSpot(QPoint(22, 22))
        drag.exec(Qt.DropAction.CopyAction)


class SnmpDialog(QDialog):
    """Clean dialog for configuring SNMP credentials and version."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self.setWindowTitle('SNMP Settings')
        self.setFixedWidth(340)
        self.setStyleSheet(_TAB_STYLE)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        form = QGridLayout()
        form.setSpacing(8)

        form.addWidget(QLabel('Version:'), 0, 0)
        self.version_combo = QComboBox()
        self.version_combo.addItem('v2c', '2c')
        self.version_combo.addItem('v1', '1')
        self.version_combo.addItem('v3', '3')
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        form.addWidget(self.version_combo, 0, 1)

        form.addWidget(QLabel('Community:'), 1, 0)
        comm_box = QHBoxLayout()
        comm_box.setSpacing(4)
        self.community_edit = QLineEdit('public')
        comm_box.addWidget(self.community_edit)
        self.community_hist_btn = QToolButton()
        self.community_hist_btn.setText('▾')
        self.community_hist_btn.setToolTip('Community history')
        self.community_hist_btn.clicked.connect(self._show_community_menu)
        comm_box.addWidget(self.community_hist_btn)
        form.addLayout(comm_box, 1, 1)

        layout.addLayout(form)

        # v3 container
        self.v3_box = QWidget()
        v3_layout = QGridLayout(self.v3_box)
        v3_layout.setContentsMargins(0, 0, 0, 0)
        v3_layout.setSpacing(8)

        v3_layout.addWidget(QLabel('User:'), 0, 0)
        self.username_edit = QLineEdit()
        v3_layout.addWidget(self.username_edit, 0, 1)

        v3_layout.addWidget(QLabel('Auth:'), 1, 0)
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(_AUTH_PROTOS)
        v3_layout.addWidget(self.auth_combo, 1, 1)

        v3_layout.addWidget(QLabel('Auth Pass:'), 2, 0)
        self.auth_pass_edit = QLineEdit()
        self.auth_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        v3_layout.addWidget(self.auth_pass_edit, 2, 1)

        v3_layout.addWidget(QLabel('Priv:'), 3, 0)
        self.priv_combo = QComboBox()
        self.priv_combo.addItems(_PRIV_PROTOS)
        v3_layout.addWidget(self.priv_combo, 3, 1)

        v3_layout.addWidget(QLabel('Priv Pass:'), 4, 0)
        self.priv_pass_edit = QLineEdit()
        self.priv_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        v3_layout.addWidget(self.priv_pass_edit, 4, 1)

        layout.addWidget(self.v3_box)

        btn_box = QHBoxLayout()
        btn_box.addStretch(1)
        close_btn = QPushButton('OK')
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        btn_box.addWidget(close_btn)
        layout.addLayout(btn_box)

        self._on_version_changed()

    def _on_version_changed(self) -> None:
        is_v3 = self.version_combo.currentData() == '3'
        self.community_edit.setEnabled(not is_v3)
        self.community_hist_btn.setEnabled(not is_v3)
        self.v3_box.setVisible(is_v3)
        self.adjustSize()

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


class TopologyTab(QWidget):
    """Studio / CAD layout: unified topbar + canvas + collapsible sidebar."""

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

        self.snmp_dialog = SnmpDialog(self._config, self)
        self.snmp_dialog.version_combo.currentIndexChanged.connect(self._on_snmp_version_changed)

        self._search_matches: list[str] = []
        self._search_match_idx = 0

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Build view first so topbar buttons can bind to it
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

        # Top control bar
        root.addWidget(self._build_top_bar())

        # Canvas + Sidebar content area
        content = QWidget()
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Left sidebar (Accordion: Objects 1st, Layers 2nd, Discovery 3rd)
        self.sidebar = self._build_sidebar()
        content_layout.addWidget(self.sidebar)

        # Canvas on the right
        content_layout.addWidget(self.view, 1)

        root.addWidget(content, 1)

        # Wire undo / redo stack
        self.view.undo_stack.canUndoChanged.connect(self.undo_btn.setEnabled)
        self.view.undo_stack.canRedoChanged.connect(self.redo_btn.setEnabled)
        self._undo_shortcut = QShortcut(QKeySequence.StandardKey.Undo, self)
        self._undo_shortcut.activated.connect(self._on_undo)
        self._redo_shortcut = QShortcut(QKeySequence.StandardKey.Redo, self)
        self._redo_shortcut.activated.connect(self._on_redo)
        self._redo_shortcut_y = QShortcut(QKeySequence('Ctrl+Y'), self)
        self._redo_shortcut_y.activated.connect(self._on_redo)

        # Smooth sidebar animation
        self._sidebar_anim = QPropertyAnimation(self.sidebar, b"maximumWidth")
        self._sidebar_anim.setDuration(220)
        self._sidebar_anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._sidebar_anim.finished.connect(self._on_sidebar_anim_finished)

        self._panel_shortcut = QShortcut(QKeySequence('Ctrl+B'), self)
        self._panel_shortcut.activated.connect(self.sidebar_toggle_btn.toggle)

        # Load saved map and restore state
        if self.view.load_saved_map():
            self._graph = self.view._scene.graph
            self.layer_tree.populate(self._graph, self._hidden_layers())
            self.view.set_visible_layers(self.layer_tree._visible_layers)

        self._load_remembered()
        if self._graph is not None:
            self._start_monitor(self._graph)

        QApplication.instance().aboutToQuit.connect(self.shutdown)

    @staticmethod
    def _vsep() -> QFrame:
        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.VLine)
        sep.setStyleSheet(f'color: {_BORDER}; margin: 2px 2px;')
        return sep

    # ── Top Bar ──────────────────────────────────────────────────────────

    def _build_top_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName('topBar')
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(6)

        # 1. Sidebar Toggle Button
        self.sidebar_toggle_btn = QToolButton()
        self.sidebar_toggle_btn.setText('☷ Panel')
        self.sidebar_toggle_btn.setCheckable(True)
        self.sidebar_toggle_btn.setChecked(True)
        self.sidebar_toggle_btn.setToolTip('Toggle sidebar panel (Ctrl+B)')
        self.sidebar_toggle_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle_btn.toggled.connect(self._toggle_sidebar)
        layout.addWidget(self.sidebar_toggle_btn)

        layout.addWidget(self._vsep())

        # 2. File actions: Save & PNG
        self.save_btn = QToolButton()
        self.save_btn.setText('💾 Save')
        self.save_btn.setToolTip('Save current layout and positions')
        self.save_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_btn.clicked.connect(self._save_map)
        layout.addWidget(self.save_btn)

        self.export_btn = QToolButton()
        self.export_btn.setText('📷 PNG')
        self.export_btn.setToolTip('Export topology map to PNG image')
        self.export_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.export_btn.clicked.connect(self._export_png)
        layout.addWidget(self.export_btn)

        layout.addWidget(self._vsep())

        # 3. Undo / Redo
        self.undo_btn = QToolButton()
        self.undo_btn.setText('↶ Undo')
        self.undo_btn.setToolTip('Undo last change (Ctrl+Z)')
        self.undo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.undo_btn.setEnabled(False)
        self.undo_btn.clicked.connect(self._on_undo)
        layout.addWidget(self.undo_btn)

        self.redo_btn = QToolButton()
        self.redo_btn.setText('↷ Redo')
        self.redo_btn.setToolTip('Redo change (Ctrl+Y / Ctrl+Shift+Z)')
        self.redo_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redo_btn.setEnabled(False)
        self.redo_btn.clicked.connect(self._on_redo)
        layout.addWidget(self.redo_btn)

        layout.addWidget(self._vsep())

        # 4. Link tool
        self.link_btn = QToolButton()
        self.link_btn.setText('⚡ Link')
        self.link_btn.setCheckable(True)
        self.link_btn.setToolTip('Create link between two devices (Esc to cancel)')
        self.link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.link_btn.toggled.connect(self._on_link_btn_toggled)
        layout.addWidget(self.link_btn)

        layout.addWidget(self._vsep())

        # 5. Zoom tools
        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText('－')
        self.zoom_out_btn.setToolTip('Zoom Out (-)')
        self.zoom_out_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_out_btn.clicked.connect(self.view.zoom_out)
        layout.addWidget(self.zoom_out_btn)

        self.zoom_reset_btn = QToolButton()
        self.zoom_reset_btn.setText('100%')
        self.zoom_reset_btn.setToolTip('Zoom 100% (Reset)')
        self.zoom_reset_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_reset_btn.clicked.connect(self.view.zoom_reset)
        layout.addWidget(self.zoom_reset_btn)

        self.zoom_in_btn = QToolButton()
        self.zoom_in_btn.setText('＋')
        self.zoom_in_btn.setToolTip('Zoom In (+)')
        self.zoom_in_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_in_btn.clicked.connect(self.view.zoom_in)
        layout.addWidget(self.zoom_in_btn)

        self.zoom_fit_btn = QToolButton()
        self.zoom_fit_btn.setText('⛶ Fit')
        self.zoom_fit_btn.setToolTip('Fit map in view (Zoom Fit)')
        self.zoom_fit_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.zoom_fit_btn.clicked.connect(self.view.fit_in_view)
        layout.addWidget(self.zoom_fit_btn)

        layout.addWidget(self._vsep())

        # 6. Interaction modes: Select vs Pan
        self.select_mode_btn = QToolButton()
        self.select_mode_btn.setText('↖ Select')
        self.select_mode_btn.setCheckable(True)
        self.select_mode_btn.setChecked(True)
        self.select_mode_btn.setToolTip('Selection Mode: drag a box to select multiple devices')
        self.select_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.select_mode_btn.clicked.connect(lambda: self._set_interaction_mode('select'))
        layout.addWidget(self.select_mode_btn)

        self.pan_mode_btn = QToolButton()
        self.pan_mode_btn.setText('✋ Pan')
        self.pan_mode_btn.setCheckable(True)
        self.pan_mode_btn.setChecked(False)
        self.pan_mode_btn.setToolTip('Pan Mode: drag canvas to move view (Middle-click also pans)')
        self.pan_mode_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.pan_mode_btn.clicked.connect(lambda: self._set_interaction_mode('pan'))
        layout.addWidget(self.pan_mode_btn)

        layout.addStretch(1)

        # 7. Fast search
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText('🔍 Search IP, host or vendor…')
        self.search_edit.setFixedWidth(220)
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.search_edit.returnPressed.connect(self._on_search_enter)
        layout.addWidget(self.search_edit)

        return bar

    # ── Sidebar ──────────────────────────────────────────────────────────

    def _build_sidebar(self) -> QFrame:
        sidebar = QFrame()
        sidebar.setObjectName('topologySidebar')
        sidebar.setMinimumWidth(0)
        sidebar.setMaximumWidth(275)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(4)

        self.accordion = AccordionWidget(sidebar)
        layout.addWidget(self.accordion, 1)

        # Section 1: Objects (expanded by default)
        palette_box = self._build_object_palette()
        self.section_objects = self.accordion.add_section('Objects', palette_box, expanded=True)

        # Section 2: Layers (expanded by default)
        layers_box = self._build_layers_section(sidebar)
        self.section_layers = self.accordion.add_section('Layers', layers_box, expanded=True)

        # Section 3: Discovery (collapsed by default)
        discovery_box = self._build_discovery_section()
        self.section_discovery = self.accordion.add_section('Discovery', discovery_box, expanded=False)

        return sidebar

    def _build_object_palette(self) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(2, 2, 2, 2)
        box_layout.setSpacing(4)

        hint = QLabel('Drag to map to add device')
        hint.setFont(QFont('Sans', 7))
        hint.setStyleSheet(f'color: {_TEXT_MUTED};')
        box_layout.addWidget(hint)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet('QScrollArea { background: transparent; }')
        scroll.setFixedHeight(190)

        grid_w = QWidget()
        grid = QGridLayout(grid_w)
        grid.setContentsMargins(0, 2, 0, 2)
        grid.setSpacing(4)

        for idx, (role, label) in enumerate(_PALETTE):
            r = idx // 3
            c = idx % 3
            grid.addWidget(DevicePaletteButton(role, label), r, c)

        scroll.setWidget(grid_w)
        box_layout.addWidget(scroll)
        return box

    def _build_layers_section(self, parent) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(2, 2, 2, 2)
        box_layout.setSpacing(4)

        self.layer_tree = LayerTreeWidget(parent)
        self.layer_tree.layers_visibility_changed.connect(self._on_layers_visibility_changed)
        self.layer_tree.fit_layer_requested.connect(self.view.fit_layer)
        self.layer_tree.remove_layer_requested.connect(self._on_remove_layer_requested)
        self.layer_tree.layer_color_changed.connect(self._on_layer_color_changed)
        self.layer_tree.create_layer_requested.connect(self._on_create_layer_requested)
        self.layer_tree.setMinimumHeight(350)
        box_layout.addWidget(self.layer_tree)
        return box

    def _build_discovery_section(self) -> QWidget:
        box = QWidget()
        box_layout = QVBoxLayout(box)
        box_layout.setContentsMargins(4, 4, 4, 4)
        box_layout.setSpacing(6)

        box_layout.addWidget(QLabel('Discovery Mode:'))
        self.mode_combo = QComboBox()
        self.mode_combo.addItem('Deep (ICMP + LLDP)', 'deep')
        self.mode_combo.addItem('Basic (ICMP Only)', 'basic')
        self.mode_combo.currentIndexChanged.connect(self._on_discovery_mode_changed)
        box_layout.addWidget(self.mode_combo)

        box_layout.addWidget(QLabel('Networks (CIDR or IP):'))
        self.networks_edit = QLineEdit()
        self.networks_edit.setPlaceholderText('10.0.0.0/24, 192.168.1.0/24')
        box_layout.addWidget(self.networks_edit)

        box_layout.addWidget(QLabel('Layer Name & Color:'))
        layer_row = QHBoxLayout()
        layer_row.setSpacing(4)
        self.layer_name_edit = QLineEdit()
        self.layer_name_edit.setPlaceholderText('Network-A')
        layer_row.addWidget(self.layer_name_edit, 1)

        self._selected_layer_color = '#3B82F6'
        self.layer_color_btn = QToolButton()
        self.layer_color_btn.setFixedSize(28, 28)
        self.layer_color_btn.setToolTip('Pick layer color')
        self.layer_color_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.layer_color_btn.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.layer_color_btn.setMenu(self._build_layer_color_menu())
        self._set_selected_layer_color('#3B82F6')
        layer_row.addWidget(self.layer_color_btn)
        box_layout.addLayout(layer_row)

        self.snmp_btn = QToolButton()
        self.snmp_btn.setText('⚙ SNMP: v2c ▾')
        self.snmp_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.snmp_btn.setToolTip('SNMP version and credentials')
        self.snmp_btn.clicked.connect(self._show_snmp_dialog)
        box_layout.addWidget(self.snmp_btn)

        self.discover_btn = QPushButton('Discover')
        self.discover_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.discover_btn.clicked.connect(self.start_discovery)
        box_layout.addWidget(self.discover_btn)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        box_layout.addWidget(self.progress)

        self.status_label = QLabel('Idle')
        self.status_label.setStyleSheet(f'color: {_TEXT_MUTED}; font-size: 8pt;')
        self.status_label.setWordWrap(True)
        box_layout.addWidget(self.status_label)

        return box

    def _on_discovery_mode_changed(self) -> None:
        mode = self.mode_combo.currentData()
        if mode == 'basic':
            self.snmp_btn.setEnabled(False)
            self.snmp_btn.setToolTip('SNMP is disabled in Basic (ICMP Only) mode')
        else:
            self.snmp_btn.setEnabled(True)
            self.snmp_btn.setToolTip('SNMP version and credentials')

    def _build_layer_color_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet(f"""
            QMenu {{
                background-color: {_BG};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                padding: 4px;
            }}
            QMenu::item {{
                padding: 6px 20px;
                border-radius: 4px;
            }}
            QMenu::item:selected {{
                background-color: {_ROYAL};
                color: #FFFFFF;
            }}
        """)
        palettes = [
            ('#3B82F6', 'Blue'),
            ('#10B981', 'Emerald'),
            ('#8B5CF6', 'Purple'),
            ('#F59E0B', 'Amber'),
            ('#EF4444', 'Crimson'),
            ('#06B6D4', 'Cyan'),
            ('#F97316', 'Orange'),
            ('#6B7280', 'Slate'),
        ]
        for hex_code, name in palettes:
            act = menu.addAction(name)
            act.setIcon(make_color_icon(hex_code, 14))
            act.triggered.connect(lambda checked=False, h=hex_code: self._set_selected_layer_color(h))
        menu.addSeparator()
        custom_act = menu.addAction('Custom Color…')
        custom_act.triggered.connect(self._choose_custom_layer_color)
        return menu

    def _set_selected_layer_color(self, hex_code: str) -> None:
        self._selected_layer_color = hex_code
        self.layer_color_btn.setIcon(make_color_icon(hex_code, 16))

    def _choose_custom_layer_color(self) -> None:
        initial = QColor(self._selected_layer_color or '#3B82F6')
        color = QColorDialog.getColor(initial, self, 'Select Layer Color')
        if color.isValid():
            self._set_selected_layer_color(color.name())

    def _on_layer_color_changed(self, name: str, hex_code: str) -> None:
        if self._graph is not None:
            if not hasattr(self._graph, 'layer_colors') or self._graph.layer_colors is None:
                self._graph.layer_colors = {}
            self._graph.layer_colors[name] = hex_code
        self.view.update_layer_color(name, hex_code)

    def _toggle_sidebar(self, visible: bool) -> None:
        self._sidebar_anim.stop()
        start_w = self.sidebar.width()
        if visible:
            self.sidebar.setVisible(True)
            self._sidebar_anim.setStartValue(start_w)
            self._sidebar_anim.setEndValue(275)
        else:
            self._sidebar_anim.setStartValue(start_w)
            self._sidebar_anim.setEndValue(0)
        self._sidebar_anim.start()

    def _on_sidebar_anim_finished(self) -> None:
        if not self.sidebar_toggle_btn.isChecked():
            self.sidebar.setVisible(False)

    def _on_undo(self) -> None:
        if self.view.undo_stack.canUndo():
            self.view.undo_stack.undo()

    def _on_redo(self) -> None:
        if self.view.undo_stack.canRedo():
            self.view.undo_stack.redo()

    def _on_link_btn_toggled(self, on: bool) -> None:
        self.view.set_link_mode(on)

    def _on_link_mode_changed(self, on: bool) -> None:
        self.link_btn.blockSignals(True)
        self.link_btn.setChecked(on)
        self.link_btn.blockSignals(False)

    def _on_search_text_changed(self, text: str) -> None:
        self._search_matches = self.view.highlight_matches(text)
        self._search_match_idx = 0

    def _on_search_enter(self) -> None:
        if not self._search_matches:
            self._search_matches = self.view.highlight_matches(self.search_edit.text())
            self._search_match_idx = 0
        if self._search_matches:
            target_id = self._search_matches[self._search_match_idx % len(self._search_matches)]
            self._search_match_idx += 1
            self.view.focus_device(target_id)

    # ── Actions & Interactions ───────────────────────────────────────────

    def _set_interaction_mode(self, mode: str) -> None:
        if mode == 'select':
            self.select_mode_btn.blockSignals(True)
            self.pan_mode_btn.blockSignals(True)
            self.select_mode_btn.setChecked(True)
            self.pan_mode_btn.setChecked(False)
            self.select_mode_btn.blockSignals(False)
            self.pan_mode_btn.blockSignals(False)
        else:
            self.select_mode_btn.blockSignals(True)
            self.pan_mode_btn.blockSignals(True)
            self.select_mode_btn.setChecked(False)
            self.pan_mode_btn.setChecked(True)
            self.select_mode_btn.blockSignals(False)
            self.pan_mode_btn.blockSignals(False)
        self.view.set_interaction_mode(mode)

    def _on_create_layer_requested(self, name: str, hex_code: str) -> None:
        if self._graph is None:
            self._graph = TopologyGraph()
        if not hasattr(self._graph, 'layer_colors') or self._graph.layer_colors is None:
            self._graph.layer_colors = {}
        self._graph.layer_colors[name] = hex_code
        self.layer_tree.populate(self._graph, self._hidden_layers())
        self.view.update_layer_color(name, hex_code)
        self.view.save_map()
        self.status_label.setText(f"Layer '{name}' created")

    def _current_layout(self) -> str:
        return 'hierarchical'

    def _save_map(self) -> None:
        self.view.save_map()
        path = self.view.layout_path or ''
        name = os.path.basename(path) if path else ''
        self.status_label.setText(f'✓ Saved{f" to {name}" if name else ""}')

    def _export_png(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, 'Export topology map', 'topology.png', 'PNG image (*.png)')
        if not path:
            return
        if self.view.export_png(path):
            self.status_label.setText(f'Exported {path}')
        else:
            QMessageBox.warning(self, 'Topology', 'Nothing to export (empty map).')

    # ── SNMP Popover / Dialog ────────────────────────────────────────────

    def _show_snmp_dialog(self) -> None:
        pos = self.snmp_btn.mapToGlobal(QPoint(0, self.snmp_btn.height() + 4))
        self.snmp_dialog.move(pos)
        self.snmp_dialog.exec()

    def _on_snmp_version_changed(self) -> None:
        v = self.snmp_dialog.version_combo.currentText()
        self.snmp_btn.setText(f'⚙ SNMP: {v} ▾')

    def _credentials(self) -> SnmpCredentials:
        return SnmpCredentials(
            version=self.snmp_dialog.version_combo.currentData(),
            community=self.snmp_dialog.community_edit.text().strip() or 'public',
            username=self.snmp_dialog.username_edit.text().strip(),
            auth_proto=self.snmp_dialog.auth_combo.currentText(),
            auth_pass=self.snmp_dialog.auth_pass_edit.text(),
            priv_proto=self.snmp_dialog.priv_combo.currentText(),
            priv_pass=self.snmp_dialog.priv_pass_edit.text(),
        )

    def _community_list(self) -> list[str]:
        ordered: list[str] = []
        cur = self.snmp_dialog.community_edit.text().strip()
        if cur:
            ordered.append(cur)
        for c in self._config.get_vuln_community_history():
            if c and c not in ordered:
                ordered.append(c)
        if not ordered:
            ordered.append('public')
        return ordered

    # ── Discovery Workflow ───────────────────────────────────────────────

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
        mode = self.mode_combo.currentData() if hasattr(self, 'mode_combo') else 'deep'
        layer_color = self._selected_layer_color if hasattr(self, '_selected_layer_color') else ''
        self._worker = TopologyDiscoveryWorker(
            networks, creds,
            communities=self._community_list(),
            config=self._config,
            layer_name=layer_name,
            mode=mode,
            layer_color=layer_color,
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
            layer_name = self.layer_name_edit.text().strip()
            if layer_name and hasattr(self, '_selected_layer_color') and self._selected_layer_color:
                if not hasattr(self._graph, 'layer_colors') or self._graph.layer_colors is None:
                    self._graph.layer_colors = {}
                self._graph.layer_colors[layer_name] = self._selected_layer_color
            self.view.load_merged(self._graph, new_ids, self._current_layout())
            self.layer_tree.populate(self._graph, self._hidden_layers())
            self.view.set_visible_layers(self.layer_tree._visible_layers)
            self.status_label.setText(
                f'{len(self._graph.devices)} nodes · {len(self._graph.links)} links · '
                f'{len(self._graph.orphans)} orphans')
            self.discover_btn.setEnabled(True)
            self._start_monitor(self._graph)
            self.view.save_map()
            if hasattr(self, 'section_discovery'):
                self.section_discovery.collapse()
        except Exception as exc:
            import traceback
            traceback.print_exc()
            self.status_label.setText(f'Error merging discovery: {exc}')
            self.discover_btn.setEnabled(True)

    def _merge_graphs(self, target: TopologyGraph, incoming: TopologyGraph) -> None:
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
        if hasattr(incoming, 'layer_colors') and incoming.layer_colors:
            if not hasattr(target, 'layer_colors') or target.layer_colors is None:
                target.layer_colors = {}
            target.layer_colors.update(incoming.layer_colors)

    def _on_failed(self, message: str) -> None:
        self._worker = None
        self.status_label.setText(f'Error: {message}')
        self.discover_btn.setEnabled(True)

    # ── Layer Management ─────────────────────────────────────────────────

    def _hidden_layers(self) -> set[str]:
        try:
            return set(json.loads(self._config.get('topology_hidden_layers') or '[]'))
        except (ValueError, TypeError):
            return set()

    def _on_layers_visibility_changed(self, visible_layers: set[str]) -> None:
        all_layers = self.layer_tree._all_layers
        hidden = list(all_layers - visible_layers)
        self._config.set('topology_hidden_layers', json.dumps(hidden))
        self.view.set_visible_layers(visible_layers)

    def _on_remove_layer_requested(self, layers: set[str]) -> None:
        if self._graph is None:
            return
        to_remove = set()
        for did, dev in list(self._graph.devices.items()):
            if dev.layers and dev.layers <= layers:
                to_remove.add(did)
            else:
                dev.layers -= layers

        for did in to_remove:
            self._graph.devices.pop(did, None)

        self._graph.links = [
            l for l in self._graph.links
            if l.source_id not in to_remove and l.target_id not in to_remove
        ]

        self.view.load(self._graph, self._current_layout())
        self.layer_tree.populate(self._graph, self._hidden_layers())
        self.view.set_visible_layers(self.layer_tree._visible_layers)
        self.view.save_map()
        self.status_label.setText(f'Removed {len(to_remove)} devices from layer')

    # ── Context Dialogs & Interactions ───────────────────────────────────

    def _on_node_double_clicked(self, device) -> None:
        dialog = DeviceDetailDialog(device, self)
        dialog.device_changed.connect(self.view.on_device_changed)
        dialog.show()

    def _on_group_clicked(self, group) -> None:
        GroupDevicesDialog(group.members(), self).show()

    def _on_node_context_menu(self, device, pos) -> None:
        if self._main is None:
            return
        target_devices = None
        if hasattr(self, 'view') and self.view and hasattr(self.view, '_scene') and self.view._scene:
            selected_nodes = [item for item in self.view._scene.selectedItems() if isinstance(item, NodeItem)]
            if any(item.device.id == device.id for item in selected_nodes):
                target_devices = [item.device for item in selected_nodes]
        TopologyActions.show_node_menu(self._main, device, pos, target_devices=target_devices)

    def _on_group_context_menu(self, group, pos) -> None:
        if self._main is None:
            return
        TopologyActions.show_group_menu(self._main, group, pos)

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

    # ── Persistence of UI Preferences ────────────────────────────────────

    def _remember(self) -> None:
        self._config.set('topology_networks', self.networks_edit.text())
        self._config.set('topology_snmp_version', self.snmp_dialog.version_combo.currentData())
        self._config.set('topology_community', self.snmp_dialog.community_edit.text())
        self._config.set('topology_username', self.snmp_dialog.username_edit.text())
        community = self.snmp_dialog.community_edit.text().strip()
        if community:
            self._config.add_vuln_community(community)

    def _load_remembered(self) -> None:
        nets = self._config.get('topology_networks')
        if nets:
            self.networks_edit.setText(nets)
        community = self._config.get('topology_community')
        if community:
            self.snmp_dialog.community_edit.setText(community)
        else:
            history = self._config.get_vuln_community_history()
            if history:
                self.snmp_dialog.community_edit.setText(history[0])
        username = self._config.get('topology_username')
        if username:
            self.snmp_dialog.username_edit.setText(username)
        version = self._config.get('topology_snmp_version')
        if version:
            idx = self.snmp_dialog.version_combo.findData(version)
            if idx >= 0:
                self.snmp_dialog.version_combo.setCurrentIndex(idx)
        self._on_snmp_version_changed()

    def shutdown(self) -> None:
        if self._worker is not None:
            try:
                if self._worker.isRunning():
                    self._worker.stop()
                    self._worker.wait(15000)
            except RuntimeError:
                self._worker = None
        self._stop_monitor()

    # ── Live Performance Monitor ─────────────────────────────────────────

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
        for sig in (mon.updated, mon.status_updated, mon.speed_updated):
            try:
                sig.disconnect()
            except TypeError:
                pass
        mon.stop()
        if not mon.wait(3000):
            mon.finished.connect(mon.deleteLater)
        else:
            mon.deleteLater()
