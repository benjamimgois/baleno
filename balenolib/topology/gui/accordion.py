"""Collapsible Accordion components for Baleno Topology sidebar.

Provides CollapsibleSection and AccordionWidget to organize tools and panels
(e.g., Objects, Layers, Discovery) into expandable / collapsible groups
similar to Draw.io / CAD studio layouts, with smooth easing animations.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal, QPropertyAnimation, QEasingCurve
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QToolButton, QScrollArea,
    QFrame, QSizePolicy,
)

__all__ = ['CollapsibleSection', 'AccordionWidget']

_BG = '#161B22'
_BG_HEADER = '#1C2128'
_BG_HEADER_HOVER = '#262C36'
_BORDER = '#30363D'
_TEXT = '#C9D1D9'
_TEXT_MUTED = '#8B949E'
_ROYAL = '#4169E1'

_SECTION_STYLE = f"""
    QToolButton#accordionHeader {{
        background-color: {_BG_HEADER};
        color: {_TEXT};
        border: 1px solid {_BORDER};
        border-radius: 6px;
        padding: 6px 8px;
        font-size: 8.5pt;
        font-weight: bold;
        text-align: left;
    }}
    QToolButton#accordionHeader:hover {{
        background-color: {_BG_HEADER_HOVER};
        border-color: {_ROYAL};
        color: #FFFFFF;
    }}
"""


class CollapsibleSection(QWidget):
    """An individual collapsible section with smooth animation and toggle header."""

    toggled = pyqtSignal(bool)

    def __init__(self, title: str, content: QWidget | None = None,
                 expanded: bool = True, parent: QWidget | None = None):
        super().__init__(parent)
        self._title = title
        self._expanded = expanded
        self._content_widget: QWidget | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Header button
        self.header_btn = QToolButton()
        self.header_btn.setObjectName('accordionHeader')
        self.header_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.header_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.header_btn.setStyleSheet(_SECTION_STYLE)
        self.header_btn.clicked.connect(self.toggle)
        layout.addWidget(self.header_btn)

        # Content container
        self.content_container = QWidget()
        self.content_container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.content_layout = QVBoxLayout(self.content_container)
        self.content_layout.setContentsMargins(2, 2, 2, 4)
        self.content_layout.setSpacing(4)
        layout.addWidget(self.content_container)

        # Animation for smooth height collapse / expand
        self._anim = QPropertyAnimation(self.content_container, b"maximumHeight")
        self._anim.setDuration(220)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutCubic)
        self._anim.finished.connect(self._on_anim_finished)

        if content is not None:
            self.set_content(content)

        # Initial state (instant, no animation)
        if not self._expanded:
            self.content_container.setMaximumHeight(0)
            self.content_container.setVisible(False)
        else:
            self.content_container.setMaximumHeight(16777215)
            self.content_container.setVisible(True)

        self._update_header_text()

    def set_content(self, widget: QWidget) -> None:
        """Assign or replace the child content widget."""
        if self._content_widget is not None:
            self.content_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)
        self._content_widget = widget
        self.content_layout.addWidget(widget)

    def is_expanded(self) -> bool:
        return self._expanded

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        if self._expanded == expanded and self._anim.state() != QPropertyAnimation.State.Running:
            return
        self._expanded = expanded
        self._update_header_text()
        self.toggled.emit(self._expanded)

        if not animate:
            self._anim.stop()
            if self._expanded:
                self.content_container.setVisible(True)
                self.content_container.setMaximumHeight(16777215)
            else:
                self.content_container.setMaximumHeight(0)
                self.content_container.setVisible(False)
            return

        self._anim.stop()
        start_h = self.content_container.height()
        if self._expanded:
            self.content_container.setVisible(True)
            self.content_container.setMaximumHeight(16777215)
            target_h = max(
                self.content_container.sizeHint().height(),
                self.content_layout.sizeHint().height(),
            )
            if self._content_widget is not None:
                target_h = max(
                    target_h,
                    self._content_widget.sizeHint().height() + 8,
                    self._content_widget.minimumSizeHint().height() + 8,
                    self._content_widget.minimumHeight() + 8,
                )
            if target_h <= 0:
                target_h = 200
            self.content_container.setMaximumHeight(start_h)
            self._anim.setStartValue(start_h)
            self._anim.setEndValue(target_h)
        else:
            self._anim.setStartValue(start_h)
            self._anim.setEndValue(0)

        self._anim.start()

    def toggle(self) -> None:
        self.set_expanded(not self._expanded)

    def expand(self) -> None:
        self.set_expanded(True)

    def collapse(self) -> None:
        self.set_expanded(False)

    def _update_header_text(self) -> None:
        indicator = '▾' if self._expanded else '▸'
        self.header_btn.setText(f' {indicator}  {self._title.upper()}')

    def _on_anim_finished(self) -> None:
        if self._expanded:
            self.content_container.setMaximumHeight(16777215)
        else:
            self.content_container.setVisible(False)


class AccordionWidget(QScrollArea):
    """Vertical stack of CollapsibleSection elements with scroll support."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet(f"""
            QScrollArea {{
                background-color: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {_BG};
                width: 6px;
                border: none;
                margin: 0;
            }}
            QScrollBar::handle:vertical {{
                background: {_BORDER};
                min-height: 20px;
                border-radius: 3px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: {_ROYAL};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
        """)

        self._container = QWidget()
        self._container.setObjectName('accordionContainer')
        self._container.setStyleSheet('QWidget#accordionContainer { background: transparent; }')
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(6)
        self._sections: list[CollapsibleSection] = []

        self._stretch_item = None
        self._add_stretch()

        self.setWidget(self._container)

    def _add_stretch(self) -> None:
        if self._stretch_item is None:
            self._layout.addStretch(1)
            self._stretch_item = self._layout.itemAt(self._layout.count() - 1)

    def add_section(self, title: str, widget: QWidget | None = None,
                    expanded: bool = True) -> CollapsibleSection:
        """Add a new collapsible section to the accordion."""
        section = CollapsibleSection(title, widget, expanded=expanded, parent=self._container)
        # Insert before the stretch
        idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(idx, section)
        self._sections.append(section)
        return section

    def sections(self) -> list[CollapsibleSection]:
        return list(self._sections)
