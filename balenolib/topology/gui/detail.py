"""Device detail modal/drawer shown on node double-click."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHeaderView,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from balenolib.topology.models import Device, DeviceRole

__all__ = ['DeviceDetailDialog', 'GroupDevicesDialog', 'LinkCreationDialog', 'LinkEditDialog']

_DARK_DIALOG_STYLE = """
QDialog {
    background-color: #161B22;
    color: #C9D1D9;
}
QLabel {
    color: #C9D1D9;
}
QTabWidget::pane {
    border: 1px solid #30363D;
    background-color: #161B22;
    border-radius: 6px;
    top: -1px;
}
QTabBar::tab {
    background-color: #0D1117;
    color: #8B949E;
    border: 1px solid #30363D;
    border-bottom: none;
    padding: 7px 16px;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
    margin-right: 2px;
    font-size: 9pt;
}
QTabBar::tab:selected {
    background-color: #161B22;
    color: #58A6FF;
    border-bottom: 2px solid #58A6FF;
    font-weight: bold;
}
QTabBar::tab:hover:!selected {
    background-color: #21262D;
    color: #C9D1D9;
}
QGroupBox {
    border: 1px solid #30363D;
    border-radius: 6px;
    margin-top: 16px;
    padding-top: 14px;
    padding-bottom: 8px;
    padding-left: 8px;
    padding-right: 8px;
    background-color: #0D1117;
    color: #C9D1D9;
}
QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 6px;
    color: #58A6FF;
    font-weight: bold;
    background-color: #161B22;
}
QLineEdit, QSpinBox, QComboBox {
    background-color: #0D1117;
    border: 1px solid #30363D;
    border-radius: 4px;
    color: #C9D1D9;
    padding: 4px 8px;
    min-height: 22px;
}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
    border: 1px solid #58A6FF;
}
QComboBox::drop-down {
    border: none;
    width: 20px;
}
QComboBox QAbstractItemView {
    background-color: #161B22;
    color: #C9D1D9;
    selection-background-color: #4169E1;
    border: 1px solid #30363D;
}
QTableWidget, QListWidget {
    background-color: #0D1117;
    color: #C9D1D9;
    border: 1px solid #30363D;
    gridline-color: #21262D;
    border-radius: 4px;
    selection-background-color: #1F2A3D;
    selection-color: #58A6FF;
}
QHeaderView::section {
    background-color: #161B22;
    color: #8B949E;
    border: none;
    border-bottom: 1px solid #30363D;
    border-right: 1px solid #21262D;
    padding: 6px 8px;
    font-weight: bold;
}
QScrollBar:vertical {
    background: #0D1117;
    width: 10px;
    margin: 0;
}
QScrollBar::handle:vertical {
    background: #30363D;
    min-height: 20px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover {
    background: #484F58;
}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}
QScrollBar:horizontal {
    background: #0D1117;
    height: 10px;
    margin: 0;
}
QScrollBar::handle:horizontal {
    background: #30363D;
    min-width: 20px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover {
    background: #484F58;
}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}
QPushButton {
    background-color: #21262D;
    color: #C9D1D9;
    border: 1px solid #30363D;
    border-radius: 4px;
    padding: 6px 16px;
    font-size: 9pt;
}
QPushButton:hover {
    background-color: #30363D;
    color: #FFFFFF;
    border-color: #58A6FF;
}
QDialogButtonBox QPushButton {
    background-color: #4169E1;
    color: #FFFFFF;
    font-weight: bold;
    border: 1px solid #3156C8;
    border-radius: 4px;
    padding: 6px 18px;
    min-width: 60px;
}
QDialogButtonBox QPushButton:hover {
    background-color: #3156C8;
}
"""


class DeviceDetailDialog(QDialog):
    """Detail view with an editable Identity tab.

    Editable identity fields (hostname, ip, role, vendor, model, status, layer)
    mutate the underlying :class:`Device` on "Apply" and emit :attr:`device_changed`
    so the caller can persist the map and repaint the node.
    """

    device_changed = pyqtSignal(object)

    def __init__(self, device: Device, parent=None, graph=None):
        super().__init__(parent)
        self.device = device
        if graph is None and parent is not None:
            graph = getattr(parent, '_graph', None)
            if graph is None:
                view = getattr(parent, 'view', None)
                if view and hasattr(view, '_scene'):
                    graph = getattr(view._scene, 'graph', None)
        self.graph = graph
        self.setWindowTitle(f"{device.label} — Device Details")
        self.resize(750, 540)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(_DARK_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        header = QLabel(f"<h2>{device.label}</h2>"
                        f"<span style='color:#8b949e'>{device.ip} · "
                        f"{device.role.value.upper()} · {device.status.upper()}</span>")
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        tabs = QTabWidget()
        tabs.addTab(self._identity_tab(), "Identity")
        tabs.addTab(self._interfaces_tab(), "Interfaces")
        tabs.addTab(self._neighbors_tab(), "LLDP Neighbours")
        layout.addWidget(tabs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _identity_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        d = self.device

        self.hostname_edit = QLineEdit(d.hostname)
        form.addRow("Hostname", self.hostname_edit)

        self.ip_edit = QLineEdit(d.ip)
        form.addRow("IP", self.ip_edit)

        self.role_combo = QComboBox()
        for role in DeviceRole:
            self.role_combo.addItem(role.value.upper(), role)
        idx = self.role_combo.findData(d.role)
        if idx >= 0:
            self.role_combo.setCurrentIndex(idx)
        form.addRow("Role", self.role_combo)

        self.vendor_edit = QLineEdit(d.vendor)
        form.addRow("Vendor", self.vendor_edit)

        self.model_edit = QLineEdit(d.model)
        form.addRow("Model", self.model_edit)

        self.status_combo = QComboBox()
        self.status_combo.addItems(['up', 'down', 'unknown'])
        idx = self.status_combo.findText(d.status)
        if idx >= 0:
            self.status_combo.setCurrentIndex(idx)
        form.addRow("Status", self.status_combo)

        self.layer_spin = QSpinBox()
        self.layer_spin.setRange(0, 20)
        self.layer_spin.setValue(d.layer)
        form.addRow("Layer", self.layer_spin)

        form.addRow("Chassis ID", QLabel(d.chassis_id or '—'))
        form.addRow("Uptime", QLabel(d.uptime or '—'))
        form.addRow("Latency", QLabel(f"{d.latency_ms:.1f} ms" if d.latency_ms else '—'))

        apply_btn = QPushButton("Apply")
        apply_btn.setStyleSheet("""
            QPushButton {
                background-color: #4169E1;
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #3156C8;
                border-radius: 4px;
                padding: 6px 16px;
            }
            QPushButton:hover {
                background-color: #3156C8;
            }
        """)
        apply_btn.clicked.connect(self._apply_identity)
        form.addRow(apply_btn)

        desc_group = QGroupBox("System Description")
        desc_layout = QVBoxLayout(desc_group)
        desc = QLabel(d.sys_descr or '—')
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #8B949E; background: transparent; padding: 4px;")
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        desc_layout.addWidget(desc)
        form.addRow(desc_group)
        return page

    def _apply_identity(self) -> None:
        d = self.device
        d.hostname = self.hostname_edit.text().strip()
        d.ip = self.ip_edit.text().strip()
        d.role = self.role_combo.currentData()
        d.vendor = self.vendor_edit.text().strip()
        d.model = self.model_edit.text().strip()
        d.status = self.status_combo.currentText()
        d.layer = self.layer_spin.value()
        self.setWindowTitle(f"{d.label} — Device Details")
        self.device_changed.emit(d)

    def _interfaces_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(['Index', 'Name', 'Description', 'Status'])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Graph resolution for link fallback
        graph = self.graph
        if graph is None:
            graph = getattr(self.parent(), '_graph', None)
            if graph is None:
                view = getattr(self.parent(), 'view', None)
                if view and hasattr(view, '_scene'):
                    graph = getattr(view._scene, 'graph', None)

        interfaces = sorted(self.device.interfaces.values(), key=lambda i: i.index)
        table.setRowCount(len(interfaces))
        for row, iface in enumerate(interfaces):
            is_up = (iface.oper_status or '').lower() == 'up'

            it_idx = QTableWidgetItem(str(iface.index))
            it_idx.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

            it_name = QTableWidgetItem(iface.name or '—')

            # Description (alias preferred, then descr, then LLDP/link fallback)
            desc_val = (iface.alias or '').strip()
            if not desc_val and iface.descr and iface.descr.strip() != iface.name:
                desc_val = iface.descr.strip()

            # Check LLDP neighbors on this port
            if not desc_val and self.device.lldp_neighbors:
                for n in self.device.lldp_neighbors:
                    if n.local_port_name == iface.name or n.local_port_num == iface.index:
                        remote = n.remote_sys_name or n.remote_chassis_id or 'remote'
                        port = n.remote_port_id or n.remote_port_desc or ''
                        desc_val = f"→ {remote} ({port})" if port else f"→ {remote}"
                        break

            # Check graph links on this port
            if not desc_val and graph is not None:
                for link in getattr(graph, 'links', []):
                    if link.source_id == self.device.id and (link.source_port == iface.name or link.source_ifindex == iface.index):
                        tgt = graph.devices.get(link.target_id)
                        tgt_lbl = tgt.label if tgt else link.target_id
                        desc_val = f"→ {tgt_lbl} ({link.target_port})"
                        break
                    elif link.target_id == self.device.id and link.target_port == iface.name:
                        src = graph.devices.get(link.source_id)
                        src_lbl = src.label if src else link.source_id
                        desc_val = f"← {src_lbl} ({link.source_port})"
                        break

            if not desc_val:
                desc_val = (iface.descr or '').strip()

            it_desc = QTableWidgetItem(desc_val or '—')
            if iface.descr and iface.alias and iface.descr != iface.alias:
                it_desc.setToolTip(f"Alias: {iface.alias}\nDescr: {iface.descr}")

            status_str = iface.oper_status or 'unknown'
            it_status = QTableWidgetItem(status_str)
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            f = it_status.font()
            f.setBold(True)
            it_status.setFont(f)

            status_lower = (iface.oper_status or '').strip().lower()
            if status_lower == 'up':
                status_fg = QColor('#3FB950')
                row_bg = QColor(46, 160, 67, 35)
            elif status_lower == 'down':
                status_fg = QColor('#F85149')
                row_bg = QColor(248, 81, 73, 35)
            else:
                status_fg = QColor('#D29922')
                row_bg = None

            it_status.setForeground(status_fg)
            if row_bg is not None:
                for it in (it_idx, it_name, it_desc, it_status):
                    it.setBackground(row_bg)

            table.setItem(row, 0, it_idx)
            table.setItem(row, 1, it_name)
            table.setItem(row, 2, it_desc)
            table.setItem(row, 3, it_status)

        table.resizeColumnsToContents()
        for col in range(4):
            header.resizeSection(col, max(header.sectionSize(col) + 16, 60))
        if header.sectionSize(2) < 220:
            header.resizeSection(2, 240)

        layout.addWidget(table)
        return page

    def _neighbors_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ['Local Port', 'Remote System', 'Remote Port', 'Chassis ID', 'Mgmt IP'])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        # Collect neighbors from self.device.lldp_neighbors
        neighbors: list[dict[str, str]] = []
        seen: set[tuple[str, str, str]] = set()

        for n in self.device.lldp_neighbors:
            loc_p = n.local_port_name or (str(n.local_port_num) if n.local_port_num else '')
            rem_s = n.remote_sys_name or n.remote_chassis_id or ''
            rem_p = n.remote_port_id or n.remote_port_desc or ''
            key = (loc_p, rem_s, rem_p)
            if key in seen:
                continue
            seen.add(key)
            neighbors.append({
                'local_port': loc_p or '—',
                'remote_sys': rem_s or '—',
                'remote_port': rem_p or '—',
                'chassis_id': n.remote_chassis_id or '—',
                'mgmt_ip': n.remote_mgmt_addr or '—',
            })

        # Fallback / complement from graph links
        graph = self.graph
        if graph is None:
            graph = getattr(self.parent(), '_graph', None)
            if graph is None:
                view = getattr(self.parent(), 'view', None)
                if view and hasattr(view, '_scene'):
                    graph = getattr(view._scene, 'graph', None)

        if graph is not None:
            for link in getattr(graph, 'links', []):
                if link.source_id == self.device.id:
                    tgt = graph.devices.get(link.target_id)
                    loc_p = link.source_port or (str(link.source_ifindex) if link.source_ifindex else '')
                    rem_s = tgt.hostname if tgt and tgt.hostname else (tgt.label if tgt else link.target_id)
                    rem_p = link.target_port or ''
                    chassis = tgt.chassis_id if tgt and tgt.chassis_id else link.target_id
                    mgmt = tgt.ip if tgt and tgt.ip else ''
                    key = (loc_p, rem_s, rem_p)
                    if key not in seen:
                        seen.add(key)
                        neighbors.append({
                            'local_port': loc_p or '—',
                            'remote_sys': rem_s or '—',
                            'remote_port': rem_p or '—',
                            'chassis_id': chassis or '—',
                            'mgmt_ip': mgmt or '—',
                        })
                elif link.target_id == self.device.id:
                    src = graph.devices.get(link.source_id)
                    loc_p = link.target_port or ''
                    rem_s = src.hostname if src and src.hostname else (src.label if src else link.source_id)
                    rem_p = link.source_port or ''
                    chassis = src.chassis_id if src and src.chassis_id else link.source_id
                    mgmt = src.ip if src and src.ip else ''
                    key = (loc_p, rem_s, rem_p)
                    if key not in seen:
                        seen.add(key)
                        neighbors.append({
                            'local_port': loc_p or '—',
                            'remote_sys': rem_s or '—',
                            'remote_port': rem_p or '—',
                            'chassis_id': chassis or '—',
                            'mgmt_ip': mgmt or '—',
                        })

        if not neighbors:
            table.setRowCount(1)
            msg = QTableWidgetItem("No LLDP neighbours detected for this device")
            msg.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setForeground(QColor('#8B949E'))
            table.setItem(0, 0, msg)
            table.setSpan(0, 0, 1, 5)
        else:
            table.setRowCount(len(neighbors))
            for row, n in enumerate(neighbors):
                it_loc = QTableWidgetItem(n['local_port'])
                it_loc.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                it_sys = QTableWidgetItem(n['remote_sys'])
                it_sys.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                f = it_sys.font()
                f.setBold(True)
                it_sys.setFont(f)

                it_rem_port = QTableWidgetItem(n['remote_port'])
                it_rem_port.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                it_chassis = QTableWidgetItem(n['chassis_id'])
                it_chassis.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                it_ip = QTableWidgetItem(n['mgmt_ip'])
                it_ip.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                table.setItem(row, 0, it_loc)
                table.setItem(row, 1, it_sys)
                table.setItem(row, 2, it_rem_port)
                table.setItem(row, 3, it_chassis)
                table.setItem(row, 4, it_ip)

        table.resizeColumnsToContents()
        for col in range(5):
            header.resizeSection(col, max(header.sectionSize(col) + 20, 80))
        if header.sectionSize(1) < 180:
            header.resizeSection(1, 200)

        layout.addWidget(table)
        return page


class LinkCreationDialog(QDialog):
    """Configure a manual link: choose/type each endpoint's port and speed."""

    SPEED_OPTIONS = [('Auto', None), ('10 Mbps', 10.0), ('100 Mbps', 100.0),
                     ('1 Gbps', 1000.0), ('10 Gbps', 10000.0)]

    def __init__(self, source_label: str, source_ifaces, target_label: str,
                 target_ifaces, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Create Link')
        self.resize(520, 340)
        self.setStyleSheet(_DARK_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        header = QLabel('<h3>Connect two devices</h3>')
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        cols = QHBoxLayout()
        self._src_group, self._src_list, self._src_edit = self._side(source_label, source_ifaces)
        self._dst_group, self._dst_list, self._dst_edit = self._side(target_label, target_ifaces)
        cols.addWidget(self._src_group)
        cols.addWidget(self._dst_group)
        layout.addLayout(cols)

        speed_row = QHBoxLayout()
        speed_row.addWidget(QLabel('Speed:'))
        self.speed_combo = QComboBox()
        for label, mbps in self.SPEED_OPTIONS:
            self.speed_combo.addItem(label, mbps)
        speed_row.addWidget(self.speed_combo)
        speed_row.addStretch(1)
        layout.addLayout(speed_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _side(self, label: str, ifaces):
        """Build one endpoint column. Returns (container, list_or_None, edit_or_None)."""
        group = QGroupBox(label)
        v = QVBoxLayout(group)
        lst = None
        edit = None
        if ifaces:
            lst = QListWidget()
            for iface in ifaces:
                it = QListWidgetItem(iface.name)
                it.setData(Qt.ItemDataRole.UserRole, iface.name)
                if iface.descr:
                    it.setToolTip(iface.descr)
                lst.addItem(it)
            lst.setCurrentRow(0)
            v.addWidget(lst)
        else:
            edit = QLineEdit()
            edit.setPlaceholderText('port name (e.g. Gi0/1)')
            v.addWidget(edit)
        return group, lst, edit

    @staticmethod
    def _port(lst, edit) -> str:
        if lst is not None:
            it = lst.currentItem()
            return it.data(Qt.ItemDataRole.UserRole) if it else ''
        return edit.text().strip() if edit is not None else ''

    def source_port(self) -> str:
        return self._port(self._src_list, self._src_edit)

    def target_port(self) -> str:
        return self._port(self._dst_list, self._dst_edit)

    def speed(self):
        return self.speed_combo.currentData()


class GroupDevicesDialog(QDialog):
    """Read-only table listing the devices collapsed into a group node."""

    def __init__(self, members: list[Device], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{len(members)} devices')
        self.resize(680, 420)
        self.setSizeGripEnabled(True)
        self.setStyleSheet(_DARK_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        header = QLabel(f'<h3>{len(members)} devices</h3>'
                        '<span style="color:#8b949e">collapsed to keep the map readable</span>')
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(['Hostname', 'IP', 'Role', 'Status', 'Vendor/Model'])
        header = table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(members))
        for row, device in enumerate(sorted(members, key=lambda d: d.label.lower())):
            it_host = QTableWidgetItem(device.hostname or device.id)
            it_ip = QTableWidgetItem(device.ip)
            it_role = QTableWidgetItem(device.role.value)
            it_status = QTableWidgetItem(device.status)
            it_status.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            it_vendor = QTableWidgetItem(f'{device.vendor} {device.model}'.strip())

            status_lower = (device.status or '').strip().lower()
            if status_lower == 'up':
                status_fg = QColor('#3FB950')
                row_bg = QColor(46, 160, 67, 35)
            elif status_lower == 'down':
                status_fg = QColor('#F85149')
                row_bg = QColor(248, 81, 73, 35)
            else:
                status_fg = QColor('#D29922')
                row_bg = None

            it_status.setForeground(status_fg)
            f = it_status.font()
            f.setBold(True)
            it_status.setFont(f)

            if row_bg is not None:
                for it in (it_host, it_ip, it_role, it_status, it_vendor):
                    it.setBackground(row_bg)

            table.setItem(row, 0, it_host)
            table.setItem(row, 1, it_ip)
            table.setItem(row, 2, it_role)
            table.setItem(row, 3, it_status)
            table.setItem(row, 4, it_vendor)

        table.resizeColumnsToContents()
        for col in range(5):
            header.resizeSection(col, max(header.sectionSize(col) + 16, 80))

        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class LinkEditDialog(QDialog):
    """Edit the port names of a manually-created link."""

    def __init__(self, source_label: str, source_port: str,
                 target_label: str, target_port: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Edit Link')
        self.resize(380, 150)
        self.setStyleSheet(_DARK_DIALOG_STYLE)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.source_edit = QLineEdit(source_port)
        self.target_edit = QLineEdit(target_port)
        form.addRow(f'Port ({source_label})', self.source_edit)
        form.addRow(f'Port ({target_label})', self.target_edit)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def source_port(self) -> str:
        return self.source_edit.text().strip()

    def target_port(self) -> str:
        return self.target_edit.text().strip()

