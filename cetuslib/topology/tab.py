"""Topology tab UI — control panel + interactive topology canvas.

Wraps the Network Topology Mapper (``cetuslib.topology``) into a tab that
matches the other Cetus tabs: a light control panel on top (discovery +
SNMP credentials) and the dark ``TopologyView`` canvas filling the rest.

The discovery runs inside :class:`TopologyDiscoveryWorker` (QThread) so the
GUI thread never blocks; results are fed back through Qt signals.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QComboBox, QProgressBar, QMessageBox,
    QApplication, QMenu, QToolButton,
)

from cetuslib.topology.collector import SnmpCredentials
from cetuslib.topology.worker import TopologyDiscoveryWorker
from cetuslib.topology.gui.view import TopologyView
from cetuslib.topology.gui.detail import DeviceDetailDialog
from cetuslib.topology.persistence import default_layout_path

__all__ = ['TopologyTab']


_TAB_STYLE = """
    QGroupBox {
        font-weight: bold; font-size: 9pt;
        border: 1px solid #c8c8c8; border-radius: 8px;
        margin-top: 6px; padding-top: 4px;
        background-color: #f9f9f9;
    }
    QGroupBox::title {
        subcontrol-origin: margin; left: 10px;
        color: #26A69A; background-color: #f9f9f9;
    }
    QLabel {
        background-color: transparent;
        border: none;
        color: #555555;
        font-size: 9pt;
    }
    QLineEdit {
        background-color: #f5f5f5; color: #333333;
        border: 1px solid #d0d0d0; border-radius: 6px;
        padding: 2px 8px; font-size: 9pt;
    }
    QLineEdit:focus { border: 2px solid #26A69A; }
    QComboBox {
        background-color: #f5f5f5; color: #333333;
        border: 1px solid #d0d0d0; border-radius: 6px;
        padding: 2px 6px; font-size: 9pt;
    }
    QComboBox:focus { border: 2px solid #26A69A; }
    QPushButton {
        background-color: #26A69A; color: #ffffff;
        border: none; border-radius: 8px;
        padding: 8px 16px; font-weight: bold; font-size: 10pt;
    }
    QPushButton:hover { background-color: #1f8f85; }
    QPushButton:pressed { background-color: #1a7a71; }
    QPushButton:disabled { background-color: #b0cfc9; color: #f0f0f0; }
    QProgressBar {
        border: 1px solid #d0d0d0; border-radius: 6px;
        background-color: #f5f5f5; text-align: center;
        font-size: 8pt; color: #333333; height: 14px;
    }
    QProgressBar::chunk { background-color: #26A69A; border-radius: 5px; }
"""

_AUTH_PROTOS = ['None', 'MD5', 'SHA', 'SHA224', 'SHA256', 'SHA384', 'SHA512']
_PRIV_PROTOS = ['None', 'DES', '3DES', 'AES', 'AES192', 'AES256']


class TopologyTab(QWidget):
    """Discovery + SNMP controls over the interactive topology canvas."""

    def __init__(self, config_manager, parent=None):
        super().__init__(parent)
        self._config = config_manager
        self._worker = None
        self._graph = None
        self.setStyleSheet(_TAB_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)

        self.view = TopologyView()
        self.view.set_layout_path(default_layout_path())
        self.view._scene.node_double_clicked.connect(self._on_node_double_clicked)

        layout.addWidget(self._build_discovery_group())
        layout.addWidget(self._build_snmp_group())
        layout.addWidget(self.view, 1)

        self._load_remembered()

        QApplication.instance().aboutToQuit.connect(self.shutdown)

    # ── UI construction ──────────────────────────────────────────────────

    def _build_discovery_group(self) -> QGroupBox:
        group = QGroupBox('Discovery')
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel('Networks:'), 0, 0)
        self.networks_edit = QLineEdit()
        self.networks_edit.setPlaceholderText('10.0.0.0/24, 192.168.1.0/24')
        grid.addWidget(self.networks_edit, 0, 1)

        self.discover_btn = QPushButton('Discover')
        self.discover_btn.clicked.connect(self.start_discovery)
        grid.addWidget(self.discover_btn, 0, 2)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        grid.addWidget(self.progress, 1, 0, 1, 2)

        self.status_label = QLabel('Idle')
        grid.addWidget(self.status_label, 1, 2)

        layout_row = QHBoxLayout()
        layout_row.setSpacing(8)
        layout_row.addWidget(QLabel('Layout:'))
        self.layout_combo = QComboBox()
        self.layout_combo.addItem('Hierarchical (tree)', 'hierarchical')
        self.layout_combo.addItem('Force-directed', 'force')
        self.layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        layout_row.addWidget(self.layout_combo)
        layout_row.addStretch(1)
        fit_btn = QPushButton('Fit')
        fit_btn.clicked.connect(self.view.fit_in_view)
        layout_row.addWidget(fit_btn)
        save_btn = QPushButton('Save Layout')
        save_btn.clicked.connect(self.view.save_layout)
        layout_row.addWidget(save_btn)
        grid.addLayout(layout_row, 2, 0, 1, 3)

        return group

    def _build_snmp_group(self) -> QGroupBox:
        group = QGroupBox('SNMP (LLDP)')
        grid = QGridLayout(group)
        grid.setContentsMargins(8, 8, 8, 8)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(6)

        grid.addWidget(QLabel('Version:'), 0, 0)
        self.version_combo = QComboBox()
        self.version_combo.addItem('v2c', '2c')
        self.version_combo.addItem('v1', '1')
        self.version_combo.addItem('v3', '3')
        self.version_combo.currentIndexChanged.connect(self._on_version_changed)
        grid.addWidget(self.version_combo, 0, 1)

        grid.addWidget(QLabel('Community:'), 0, 2)
        community_box = QWidget()
        community_layout = QHBoxLayout()
        community_layout.setContentsMargins(0, 0, 0, 0)
        community_layout.setSpacing(4)
        self.community_edit = QLineEdit('public')
        self.community_hist_btn = QToolButton()
        self.community_hist_btn.setText('▾')
        self.community_hist_btn.setToolTip('Community history (inherited from the SNMP tab)')
        self.community_hist_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.community_hist_btn.clicked.connect(self._show_community_menu)
        community_layout.addWidget(self.community_edit, 1)
        community_layout.addWidget(self.community_hist_btn)
        community_box.setLayout(community_layout)
        grid.addWidget(community_box, 0, 3)

        grid.addWidget(QLabel('User:'), 0, 4)
        self.username_edit = QLineEdit()
        grid.addWidget(self.username_edit, 0, 5)

        grid.addWidget(QLabel('Auth:'), 1, 0)
        self.auth_combo = QComboBox()
        self.auth_combo.addItems(_AUTH_PROTOS)
        grid.addWidget(self.auth_combo, 1, 1)

        grid.addWidget(QLabel('Auth pass:'), 1, 2)
        self.auth_pass_edit = QLineEdit()
        self.auth_pass_edit.setEchoMode(QLineEdit.EchoMode.Password)
        grid.addWidget(self.auth_pass_edit, 1, 3)

        grid.addWidget(QLabel('Priv:'), 1, 4)
        self.priv_combo = QComboBox()
        self.priv_combo.addItems(_PRIV_PROTOS)
        grid.addWidget(self.priv_combo, 1, 5)

        self._on_version_changed()
        return group

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
        self._worker.finished.connect(self._on_finished)
        self._worker.failed.connect(self._on_failed)
        self._worker.finished.connect(self._worker.deleteLater)
        self.discover_btn.setEnabled(False)
        self.progress.setValue(0)
        self.status_label.setText('Scanning…')
        self._worker.start()

    def _on_progress(self, percent: int, message: str) -> None:
        self.progress.setValue(percent)
        self.status_label.setText(message)

    def _on_finished(self, graph) -> None:
        self._graph = graph
        self.view.load(graph, self.layout_combo.currentData())
        self.status_label.setText(
            f'{len(graph.devices)} nodes · {len(graph.links)} links · '
            f'{len(graph.orphans)} orphans')
        self.discover_btn.setEnabled(True)

    def _on_failed(self, message: str) -> None:
        self.status_label.setText(f'Error: {message}')
        self.discover_btn.setEnabled(True)

    # ── interactions ─────────────────────────────────────────────────────

    def _on_layout_changed(self) -> None:
        if self._graph is not None:
            self.view.switch_layout(self.layout_combo.currentData())

    def _on_node_double_clicked(self, device) -> None:
        DeviceDetailDialog(device, self).show()

    def _show_community_menu(self) -> None:
        """Show the SNMP community history shared with the SNMP tab."""
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
        """Ordered communities to try: current field first, then SNMP history."""
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
        """Stop a running discovery (called from the app shutdown hook)."""
        if self._worker is not None and self._worker.isRunning():
            self._worker.stop()
            self._worker.wait(15000)
