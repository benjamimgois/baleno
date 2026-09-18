"""GIMP-style layer management tree widget for the Baleno topology tab.

Provides hierarchical grouping of discovery layers (seeds and LLDP hops),
cascade visibility toggling via eye icons, node counters, and right-click
context actions (Solo, Fit Layer, Show/Hide Group, Remove).
"""

from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtCore import Qt, QPointF, QRectF, pyqtSignal, QSize
from PyQt6.QtGui import QColor, QFont, QIcon, QPainter, QPainterPath, QPen, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTreeWidget,
    QTreeWidgetItem, QMenu, QPushButton, QHeaderView, QMessageBox,
    QColorDialog, QInputDialog,
)

__all__ = ['LayerTreeWidget', 'make_eye_icon', 'make_color_icon']

_BG = '#161B22'
_BG_DARK = '#0D1117'
_BORDER = '#30363D'
_TEXT = '#C9D1D9'
_TEXT_MUTED = '#8B949E'
_ROYAL = '#4169E1'
_ROYAL_HOVER = '#3156C8'


def make_eye_icon(state: str = 'visible', size: int = 18) -> QIcon:
    """Draw a vector eye icon for layer visibility.

    :param state: 'visible' (bright open eye), 'hidden' (dim closed eye with slash),
                  or 'partial' (dim orange eye for mixed groups).
    """
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)

    w = float(size)
    h = float(size)
    cx, cy = w / 2.0, h / 2.0

    if state == 'visible':
        pen_color = QColor(88, 166, 255)     # Soft blue
        pupil_color = QColor(230, 237, 243)  # Bright white
    elif state == 'partial':
        pen_color = QColor(227, 179, 65)     # Amber / orange
        pupil_color = QColor(227, 179, 65)
    else:  # hidden
        pen_color = QColor(110, 118, 129)    # Muted gray
        pupil_color = QColor(110, 118, 129)

    # Eye almond shape using two quadratic bezier curves
    path = QPainterPath()
    path.moveTo(2.5, cy)
    path.quadTo(cx, cy - 5.0, w - 2.5, cy)
    path.quadTo(cx, cy + 5.0, 2.5, cy)

    p.setPen(QPen(pen_color, 1.4))
    p.setBrush(Qt.BrushStyle.NoBrush)
    p.drawPath(path)

    if state != 'hidden':
        # Iris & Pupil
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(pupil_color)
        p.drawEllipse(QPointF(cx, cy), 2.2, 2.2)
    else:
        # Diagonal slash across closed eye
        p.setPen(QPen(QColor(248, 81, 73), 1.5))  # Red slash
        p.drawLine(QPointF(3.0, h - 3.0), QPointF(w - 3.0, 3.0))

    p.end()
    return QIcon(pix)


def make_color_icon(color_hex: str, size: int = 14) -> QIcon:
    """Draw a small circular color swatch icon for a layer."""
    pix = QPixmap(size, size)
    pix.fill(Qt.GlobalColor.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color_hex))
    p.setPen(QPen(QColor(255, 255, 255, 70), 1.0))
    p.drawEllipse(QRectF(1.0, 1.0, float(size - 2), float(size - 2)))
    p.end()
    return QIcon(pix)


def parse_layer_prefix(layer: str) -> tuple[str, int]:
    """Extract discovery group prefix and hop depth from a layer name.

    'Rede-A' -> ('Rede-A', 1)
    'Rede-A-2' -> ('Rede-A', 2)
    'backbone-3' -> ('backbone', 3)
    """
    m = re.match(r'^(.*?)-(\d+)$', layer)
    if m:
        return m.group(1), int(m.group(2))
    return layer, 1


class LayerTreeWidget(QWidget):
    """GIMP-style layer tree with hierarchy, eye visibility, and context actions."""

    # Emitted when visible layers set changes: set[str] of active layer names
    layers_visibility_changed = pyqtSignal(set)
    # Emitted when user requests focusing on specific layer(s)
    fit_layer_requested = pyqtSignal(set)
    # Emitted when user asks to remove specific layer(s) from map
    remove_layer_requested = pyqtSignal(set)
    # Emitted when a layer or group color is updated: (layer_name, hex_color)
    layer_color_changed = pyqtSignal(str, str)
    # Emitted when user creates a manual layer: (layer_name, hex_color)
    create_layer_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._visible_layers: set[str] = set()
        self._all_layers: set[str] = set()
        self._layer_colors: dict[str, str] = {}
        self._layer_counts: dict[str, int] = {}
        self._group_children: dict[str, list[str]] = {}

        self._eye_visible = make_eye_icon('visible')
        self._eye_hidden = make_eye_icon('hidden')
        self._eye_partial = make_eye_icon('partial')

        self._init_ui()

    def sizeHint(self) -> QSize:
        return QSize(260, 350)

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        # Header Bar
        header = QHBoxLayout()
        title = QLabel('LAYERS')
        title.setFont(QFont('Sans', 8, QFont.Weight.Bold))
        title.setStyleSheet(f'color: {_TEXT_MUTED}; letter-spacing: 1px;')
        header.addWidget(title)
        header.addStretch(1)

        self.summary_label = QLabel('0 layers')
        self.summary_label.setFont(QFont('Sans', 8))
        self.summary_label.setStyleSheet(f'color: {_TEXT_MUTED};')
        header.addWidget(self.summary_label)

        self.btn_new_layer = QPushButton('+ New')
        self.btn_new_layer.setToolTip('Create a new layer')
        self.btn_new_layer.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_new_layer.setStyleSheet(f"""
            QPushButton {{
                background-color: {_BG};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 2px 7px;
                font-size: 8pt;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: #21262D;
                color: #FFFFFF;
                border-color: {_ROYAL};
            }}
        """)
        self.btn_new_layer.clicked.connect(self._prompt_create_layer)
        header.addWidget(self.btn_new_layer)
        layout.addLayout(header)

        # Tree Widget
        self.tree = QTreeWidget()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(['👁', 'Name', 'Nodes'])
        self.tree.setRootIsDecorated(True)
        self.tree.setAnimated(True)
        self.tree.setIndentation(14)
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._on_context_menu)
        self.tree.itemClicked.connect(self._on_item_clicked)

        # Header sizing
        h = self.tree.header()
        h.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(0, 28)
        h.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        h.setSectionResizeMode(2, QHeaderView.ResizeMode.Fixed)
        h.resizeSection(2, 48)

        self.tree.setStyleSheet(f"""
            QTreeWidget {{
                background-color: {_BG_DARK};
                border: 1px solid {_BORDER};
                border-radius: 6px;
                color: {_TEXT};
                font-size: 9pt;
            }}
            QTreeWidget::item {{
                padding: 4px 2px;
                border-radius: 4px;
            }}
            QTreeWidget::item:hover {{
                background-color: #1C2128;
            }}
            QTreeWidget::item:selected {{
                background-color: #1F2A3D;
                color: #58A6FF;
            }}
            QHeaderView::section {{
                background-color: {_BG};
                color: {_TEXT_MUTED};
                border: none;
                border-bottom: 1px solid {_BORDER};
                padding: 3px 6px;
                font-size: 8pt;
                font-weight: bold;
            }}
        """)
        layout.addWidget(self.tree, 1)

        # Quick Actions footer
        footer = QHBoxLayout()
        footer.setSpacing(6)

        btn_style = f"""
            QPushButton {{
                background-color: {_BG};
                color: {_TEXT};
                border: 1px solid {_BORDER};
                border-radius: 4px;
                padding: 3px 8px;
                font-size: 8pt;
            }}
            QPushButton:hover {{
                background-color: #21262D;
                color: #FFFFFF;
                border-color: {_ROYAL};
            }}
        """
        self.btn_all = QPushButton('Show All')
        self.btn_all.setStyleSheet(btn_style)
        self.btn_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all.clicked.connect(self.show_all)
        footer.addWidget(self.btn_all)

        self.btn_none = QPushButton('Hide All')
        self.btn_none.setStyleSheet(btn_style)
        self.btn_none.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_none.clicked.connect(self.hide_all)
        footer.addWidget(self.btn_none)

        self.btn_invert = QPushButton('Invert')
        self.btn_invert.setStyleSheet(btn_style)
        self.btn_invert.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_invert.clicked.connect(self.invert_selection)
        footer.addWidget(self.btn_invert)

        layout.addLayout(footer)

    # ── Population ────────────────────────────────────────────────────────

    def populate(self, graph, hidden_layers: Optional[set[str]] = None) -> None:
        """Rebuild the layer tree from the given TopologyGraph."""
        self.tree.clear()
        self._all_layers.clear()
        self._layer_counts.clear()
        self._group_children.clear()
        self._layer_colors = dict(getattr(graph, 'layer_colors', {}) or {})

        # Count occurrences of each layer
        if graph is not None and getattr(graph, 'devices', None):
            for dev in graph.devices.values():
                for layer in dev.layers:
                    self._all_layers.add(layer)
                    self._layer_counts[layer] = self._layer_counts.get(layer, 0) + 1

        # Also include manual layers defined in layer_colors
        for layer in self._layer_colors:
            self._all_layers.add(layer)
            if layer not in self._layer_counts:
                self._layer_counts[layer] = 0

        if not self._all_layers:
            self.summary_label.setText('0 layers')
            return

        hidden = hidden_layers or set()
        self._visible_layers = self._all_layers - hidden

        # Group layers by prefix
        groups: dict[str, list[str]] = {}
        for layer in sorted(self._all_layers):
            prefix, _ = parse_layer_prefix(layer)
            groups.setdefault(prefix, []).append(layer)

        self._group_children = groups
        self.summary_label.setText(f'{len(self._all_layers)} layers · {len(groups)} groups')

        # Build tree nodes
        for group_name, child_layers in sorted(groups.items()):
            sorted_children = sorted(
                child_layers,
                key=lambda l: parse_layer_prefix(l)[1]
            )

            total_nodes = sum(self._layer_counts.get(l, 0) for l in sorted_children)
            group_color = self.get_layer_color(group_name) or '#3B82F6'

            group_item = QTreeWidgetItem(self.tree)
            group_item.setData(0, Qt.ItemDataRole.UserRole, ('group', group_name))
            group_item.setIcon(1, make_color_icon(group_color))
            group_item.setText(1, f'{group_name}')
            group_item.setText(2, f'({total_nodes})')
            group_item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            group_item.setFont(1, QFont('Sans', 9, QFont.Weight.Bold))

            # Add child layers
            for child_layer in sorted_children:
                _, hop = parse_layer_prefix(child_layer)
                tag = ' (seeds)' if hop == 1 else f' (hop {hop})'
                child_color = self.get_layer_color(child_layer) or group_color
                child_item = QTreeWidgetItem(group_item)
                child_item.setData(0, Qt.ItemDataRole.UserRole, ('layer', child_layer))
                child_item.setIcon(1, make_color_icon(child_color))
                child_item.setText(1, f'{child_layer}{tag}')
                child_item.setText(2, f'({self._layer_counts.get(child_layer, 0)})')
                child_item.setTextAlignment(2, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                child_item.setForeground(1, QColor(_TEXT))
                child_item.setForeground(2, QColor(_TEXT_MUTED))

                # Set child visibility icon
                is_vis = child_layer in self._visible_layers
                child_item.setIcon(0, self._eye_visible if is_vis else self._eye_hidden)

            # Update parent group icon (all, none, or partial)
            self._update_group_icon(group_item, sorted_children)
            group_item.setExpanded(True)

    def get_layer_color(self, layer_name: str) -> Optional[str]:
        if layer_name in self._layer_colors:
            return self._layer_colors[layer_name]
        prefix, _ = parse_layer_prefix(layer_name)
        if prefix in self._layer_colors:
            return self._layer_colors[prefix]
        return None

    def set_layer_color(self, name: str, hex_code: str) -> None:
        self._layer_colors[name] = hex_code
        icon = make_color_icon(hex_code)
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            p_data = group_item.data(0, Qt.ItemDataRole.UserRole)
            if p_data and p_data[1] == name:
                group_item.setIcon(1, icon)
                for j in range(group_item.childCount()):
                    child = group_item.child(j)
                    c_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if c_data and c_data[1] not in self._layer_colors:
                        child.setIcon(1, icon)
            elif p_data:
                for j in range(group_item.childCount()):
                    child = group_item.child(j)
                    c_data = child.data(0, Qt.ItemDataRole.UserRole)
                    if c_data and c_data[1] == name:
                        child.setIcon(1, icon)

    def _prompt_layer_color(self, name: str, kind: str) -> None:
        initial = QColor(self.get_layer_color(name) or '#3B82F6')
        color = QColorDialog.getColor(initial, self, f'Select Color for {name}')
        if color.isValid():
            hex_code = color.name()
            self.set_layer_color(name, hex_code)
            self.layer_color_changed.emit(name, hex_code)

    def _prompt_create_layer(self) -> None:
        name, ok = QInputDialog.getText(self, 'Create New Layer', 'Layer name:')
        name = name.strip() if name else ''
        if not ok or not name:
            return
        if name in self._all_layers:
            QMessageBox.information(self, 'Layers', f"Layer '{name}' already exists.")
            return
        color = QColorDialog.getColor(QColor('#3B82F6'), self, f"Select Color for Layer '{name}'")
        color_hex = color.name() if color.isValid() else '#3B82F6'
        self.create_layer_requested.emit(name, color_hex)

    def _update_group_icon(self, group_item: QTreeWidgetItem, child_layers: list[str]) -> None:
        vis_count = sum(1 for l in child_layers if l in self._visible_layers)
        if vis_count == len(child_layers) and vis_count > 0:
            group_item.setIcon(0, self._eye_visible)
        elif vis_count == 0:
            group_item.setIcon(0, self._eye_hidden)
        else:
            group_item.setIcon(0, self._eye_partial)

    # ── Interaction & Visibility ─────────────────────────────────────────

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        """Clicking column 0 (the eye) toggles visibility."""
        if column != 0:
            return
        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, name = data

        if kind == 'group':
            children = self._group_children.get(name, [])
            any_vis = any(c in self._visible_layers for c in children)
            if any_vis:
                for c in children:
                    self._visible_layers.discard(c)
            else:
                for c in children:
                    self._visible_layers.add(c)
            for i in range(item.childCount()):
                child = item.child(i)
                c_data = child.data(0, Qt.ItemDataRole.UserRole)
                if c_data:
                    c_layer = c_data[1]
                    child.setIcon(0, self._eye_visible if c_layer in self._visible_layers else self._eye_hidden)
            self._update_group_icon(item, children)

        elif kind == 'layer':
            if name in self._visible_layers:
                self._visible_layers.discard(name)
                item.setIcon(0, self._eye_hidden)
            else:
                self._visible_layers.add(name)
                item.setIcon(0, self._eye_visible)
            parent = item.parent()
            if parent is not None:
                p_data = parent.data(0, Qt.ItemDataRole.UserRole)
                if p_data:
                    children = self._group_children.get(p_data[1], [])
                    self._update_group_icon(parent, children)

        self.layers_visibility_changed.emit(set(self._visible_layers))

    def show_all(self) -> None:
        self._visible_layers = set(self._all_layers)
        self._refresh_all_icons()
        self.layers_visibility_changed.emit(set(self._visible_layers))

    def hide_all(self) -> None:
        self._visible_layers.clear()
        self._refresh_all_icons()
        self.layers_visibility_changed.emit(set(self._visible_layers))

    def invert_selection(self) -> None:
        self._visible_layers = self._all_layers - self._visible_layers
        self._refresh_all_icons()
        self.layers_visibility_changed.emit(set(self._visible_layers))

    def isolate(self, target_layers: set[str]) -> None:
        """Solo mode: hide everything except target_layers."""
        self._visible_layers = set(target_layers) & self._all_layers
        self._refresh_all_icons()
        self.layers_visibility_changed.emit(set(self._visible_layers))

    def _refresh_all_icons(self) -> None:
        for i in range(self.tree.topLevelItemCount()):
            group_item = self.tree.topLevelItem(i)
            p_data = group_item.data(0, Qt.ItemDataRole.UserRole)
            if not p_data:
                continue
            children = self._group_children.get(p_data[1], [])
            for j in range(group_item.childCount()):
                child = group_item.child(j)
                c_data = child.data(0, Qt.ItemDataRole.UserRole)
                if c_data:
                    is_vis = c_data[1] in self._visible_layers
                    child.setIcon(0, self._eye_visible if is_vis else self._eye_hidden)
            self._update_group_icon(group_item, children)

    # ── Context Menu ─────────────────────────────────────────────────────

    def _on_context_menu(self, pos) -> None:
        item = self.tree.itemAt(pos)
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
            QMenu::separator {{
                height: 1px;
                background-color: {_BORDER};
                margin: 4px 8px;
            }}
        """)

        if item is None:
            act_new = menu.addAction('➕ New Layer…')
            act_new.triggered.connect(self._prompt_create_layer)
            menu.exec(self.tree.viewport().mapToGlobal(pos))
            return

        data = item.data(0, Qt.ItemDataRole.UserRole)
        if not data:
            return
        kind, name = data

        if kind == 'group':
            target_layers = set(self._group_children.get(name, []))
            menu_title = f'Group: {name}'
        else:
            target_layers = {name}
            menu_title = f'Layer: {name}'

        act_title = menu.addAction(menu_title)
        act_title.setEnabled(False)
        menu.addSeparator()

        act_solo = menu.addAction('🎯 Solo (Isolate this)')
        act_solo.triggered.connect(lambda: self.isolate(target_layers))

        act_fit = menu.addAction('⛶ Fit in View (Focus)')
        act_fit.triggered.connect(lambda: self.fit_layer_requested.emit(target_layers))

        menu.addSeparator()

        act_show = menu.addAction('👁 Show')
        act_show.triggered.connect(lambda: self._set_targets_visible(target_layers, True))

        act_hide = menu.addAction('🚫 Hide')
        act_hide.triggered.connect(lambda: self._set_targets_visible(target_layers, False))

        menu.addSeparator()

        act_color = menu.addAction('🎨 Set Layer Color…')
        act_color.triggered.connect(lambda: self._prompt_layer_color(name, kind))

        menu.addSeparator()

        act_new = menu.addAction('➕ New Layer…')
        act_new.triggered.connect(self._prompt_create_layer)

        menu.addSeparator()

        act_remove = menu.addAction('🗑 Remove from Map…')
        act_remove.triggered.connect(lambda: self._confirm_remove(target_layers, name))

        menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _set_targets_visible(self, layers: set[str], visible: bool) -> None:
        if visible:
            self._visible_layers |= layers
        else:
            self._visible_layers -= layers
        self._refresh_all_icons()
        self.layers_visibility_changed.emit(set(self._visible_layers))

    def _confirm_remove(self, layers: set[str], label: str) -> None:
        reply = QMessageBox.question(
            self,
            'Remove Layer',
            f"Are you sure you want to remove '{label}' from the map?\n"
            f"Devices exclusive to this layer will be deleted from the graph.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.remove_layer_requested.emit(layers)
