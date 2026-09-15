"""Device detail modal/drawer shown on node double-click."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QHeaderView, QLabel,
    QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from cetuslib.topology.models import Device

__all__ = ['DeviceDetailDialog', 'GroupDevicesDialog']


class DeviceDetailDialog(QDialog):
    """Read-only detail view: identity, interfaces, LLDP neighbours."""

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
        form.addRow("Vendor", QLabel(d.vendor or '—'))
        form.addRow("Model", QLabel(d.model or '—'))
        form.addRow("Chassis ID", QLabel(d.chassis_id or '—'))
        form.addRow("Uptime", QLabel(d.uptime or '—'))
        form.addRow("Latency", QLabel(f"{d.latency_ms:.1f} ms" if d.latency_ms else '—'))

        desc_group = QGroupBox("System Description")
        desc_layout = QVBoxLayout(desc_group)
        desc = QLabel(d.sys_descr or '—')
        desc.setWordWrap(True)
        desc.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        desc_layout.addWidget(desc)
        form.addRow(desc_group)
        return page

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
