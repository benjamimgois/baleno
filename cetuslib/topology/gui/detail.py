"""Device detail modal/drawer shown on node double-click."""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHeaderView,
    QLabel, QLineEdit, QPushButton, QSpinBox, QTableWidget, QTableWidgetItem,
    QTabWidget, QVBoxLayout, QWidget,
)

from cetuslib.topology.models import Device, DeviceRole

__all__ = ['DeviceDetailDialog', 'GroupDevicesDialog']


class DeviceDetailDialog(QDialog):
    """Detail view with an editable Identity tab.

    Editable identity fields (hostname, ip, role, vendor, model, status, layer)
    mutate the underlying :class:`Device` on "Apply" and emit :attr:`device_changed`
    so the caller can persist the map and repaint the node.
    """

    device_changed = pyqtSignal(object)

    def __init__(self, device: Device, parent=None):
        super().__init__(parent)
        self.device = device
        self.setWindowTitle(f"{device.label} — Device Details")
        self.resize(560, 480)

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
        apply_btn.clicked.connect(self._apply_identity)
        form.addRow(apply_btn)

        desc_group = QGroupBox("System Description")
        desc_layout = QVBoxLayout(desc_group)
        desc = QLabel(d.sys_descr or '—')
        desc.setWordWrap(True)
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
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        interfaces = sorted(self.device.interfaces.values(), key=lambda i: i.index)
        table.setRowCount(len(interfaces))
        for row, iface in enumerate(interfaces):
            table.setItem(row, 0, QTableWidgetItem(str(iface.index)))
            table.setItem(row, 1, QTableWidgetItem(iface.name))
            table.setItem(row, 2, QTableWidgetItem(iface.descr or iface.alias))
            table.setItem(row, 3, QTableWidgetItem(iface.oper_status))
        layout.addWidget(table)
        return page

    def _neighbors_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(
            ['Local Port', 'Remote System', 'Remote Port', 'Chassis ID', 'Mgmt IP'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(self.device.lldp_neighbors))
        for row, n in enumerate(self.device.lldp_neighbors):
            table.setItem(row, 0, QTableWidgetItem(n.local_port_name))
            table.setItem(row, 1, QTableWidgetItem(n.remote_sys_name))
            table.setItem(row, 2, QTableWidgetItem(n.remote_port_id or n.remote_port_desc))
            table.setItem(row, 3, QTableWidgetItem(n.remote_chassis_id))
            table.setItem(row, 4, QTableWidgetItem(n.remote_mgmt_addr))
        layout.addWidget(table)
        return page


class GroupDevicesDialog(QDialog):
    """Read-only table listing the devices collapsed into a group node."""

    def __init__(self, members: list[Device], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f'{len(members)} devices')
        self.resize(560, 420)

        layout = QVBoxLayout(self)
        header = QLabel(f'<h3>{len(members)} devices</h3>'
                        '<span style="color:#8b949e">collapsed to keep the map readable</span>')
        header.setTextFormat(Qt.TextFormat.RichText)
        layout.addWidget(header)

        table = QTableWidget(0, 5)
        table.setHorizontalHeaderLabels(['Hostname', 'IP', 'Role', 'Status', 'Vendor/Model'])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setRowCount(len(members))
        for row, device in enumerate(sorted(members, key=lambda d: d.label.lower())):
            table.setItem(row, 0, QTableWidgetItem(device.hostname or device.id))
            table.setItem(row, 1, QTableWidgetItem(device.ip))
            table.setItem(row, 2, QTableWidgetItem(device.role.value))
            table.setItem(row, 3, QTableWidgetItem(device.status))
            table.setItem(row, 4, QTableWidgetItem(f'{device.vendor} {device.model}'.strip()))
        layout.addWidget(table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
