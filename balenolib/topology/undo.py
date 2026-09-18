"""Undo / Redo command history system for Baleno Topology view.

Uses PyQt6 QUndoStack and QUndoCommand to track spatial movements and graph
modifications (node moves, adding devices, adding/removing links).
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING
from PyQt6.QtCore import QPointF
from PyQt6.QtGui import QUndoCommand, QUndoStack

from balenolib.topology.models import Device, PortLink

if TYPE_CHECKING:
    from balenolib.topology.gui.view import TopologyView


class MoveNodeCommand(QUndoCommand):
    """Command for moving a device node from old_pos to new_pos."""

    def __init__(self, view: TopologyView, node_id: str,
                 old_pos: QPointF, new_pos: QPointF,
                 description: str = 'Move Node'):
        super().__init__(description)
        self.view = view
        self.node_id = node_id
        self.old_pos = QPointF(old_pos)
        self.new_pos = QPointF(new_pos)

    def redo(self) -> None:
        node = self.view._scene.node_items.get(self.node_id)
        if node is not None:
            node.setPos(self.new_pos)
            for edge in node.edges:
                edge.update_path()
            self.view._schedule_save()

    def undo(self) -> None:
        node = self.view._scene.node_items.get(self.node_id)
        if node is not None:
            node.setPos(self.old_pos)
            for edge in node.edges:
                edge.update_path()
            self.view._schedule_save()


class AddDeviceCommand(QUndoCommand):
    """Command for adding a manually placed device node."""

    def __init__(self, view: TopologyView, device: Device, pos: QPointF,
                 description: str = 'Add Device'):
        super().__init__(description)
        self.view = view
        self.device = device
        self.pos = QPointF(pos)

    def redo(self) -> None:
        if self.device.id in self.view._scene.node_items:
            return  # Already in scene
        node = self.view._scene.add_device_node(self.device, self.pos)
        node.moved.connect(self.view._schedule_save)
        self.view._schedule_save()

    def undo(self) -> None:
        if self.device.id in self.view._scene.node_items:
            self.view._scene.remove_node(self.device.id)
            self.view._schedule_save()


class RemoveDeviceCommand(QUndoCommand):
    """Command for removing a device node and its connected links."""

    def __init__(self, view: TopologyView, device: Device, pos: QPointF,
                 connected_links: list[PortLink],
                 description: str = 'Remove Device'):
        super().__init__(description)
        self.view = view
        self.device = device
        self.pos = QPointF(pos)
        self.connected_links = list(connected_links)

    def redo(self) -> None:
        if self.device.id in self.view._scene.node_items:
            self.view._scene.remove_node(self.device.id)
            self.view._schedule_save()

    def undo(self) -> None:
        if self.device.id not in self.view._scene.node_items:
            node = self.view._scene.add_device_node(self.device, self.pos)
            node.moved.connect(self.view._schedule_save)
            for l in self.connected_links:
                self.view.add_manual_link(
                    l.source_id, l.source_port, l.target_id, l.target_port, l.speed_mbps,
                    push_undo=False)
            self.view._schedule_save()


class AddLinkCommand(QUndoCommand):
    """Command for manually creating a link between two devices."""

    def __init__(self, view: TopologyView, source_id: str, source_port: str,
                 target_id: str, target_port: str, speed: Optional[float] = None,
                 description: str = 'Create Link'):
        super().__init__(description)
        self.view = view
        self.source_id = source_id
        self.source_port = source_port
        self.target_id = target_id
        self.target_port = target_port
        self.speed = speed

    def redo(self) -> None:
        if self.view._scene.graph is not None:
            if any(l.source_id == self.source_id and l.target_id == self.target_id
                   and l.source_port == self.source_port and l.target_port == self.target_port
                   for l in self.view._scene.graph.links):
                return
        self.view.add_manual_link(
            self.source_id, self.source_port,
            self.target_id, self.target_port, self.speed,
            push_undo=False)

    def undo(self) -> None:
        if self.view._scene.graph is not None:
            self.view._scene.graph.links = [
                l for l in self.view._scene.graph.links
                if not (l.source_id == self.source_id and l.target_id == self.target_id
                        and l.source_port == self.source_port and l.target_port == self.target_port)
            ]
        for edge in list(self.view._scene.edge_items):
            if (edge.link.source_id == self.source_id and edge.link.target_id == self.target_id
                    and edge.link.source_port == self.source_port and edge.link.target_port == self.target_port):
                self.view._scene.removeItem(edge)
                self.view._scene.edge_items.remove(edge)
                break
        self.view._schedule_save()


class TopologyUndoStack(QUndoStack):
    """Centralized undo/redo stack for topology canvas operations."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUndoLimit(50)
