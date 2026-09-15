"""Layout persistence for the Network Topology Mapper.

Stores manually adjusted node coordinates as JSON (matching the rest of
Cetus, which persists settings via ``ConfigManager`` JSON).  SQLite is
intentionally not used here: a topology layout is a small, single-shot
mapping that JSON handles with zero extra dependency.

The file format is deliberately simple so it can be hand-edited and
version-controlled::

    {
        "version": 2,
        "positions": {
            "SW-CORE": [120.0, -84.0],
            "RTR-EDGE": [-310.5, 0.0]
        },
        "groups": {
            "SW-CORE": [120.0, 200.0]
        }
    }
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

from cetuslib.topology.models import TopologyGraph

__all__ = ['save_layout', 'load_layout', 'load_group_layout',
           'default_layout_path']


def default_layout_path() -> str:
    """Return the default layout file inside the Cetus config directory."""
    xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.join(Path.home(), '.config')
    return os.path.join(xdg, 'cetus', 'topology_layout.json')


def _round(xy: tuple[float, float]) -> list[float]:
    return [round(xy[0], 1), round(xy[1], 1)]


def save_layout(graph: TopologyGraph, positions: dict[str, tuple[float, float]],
                path: str,
                group_positions: Optional[dict[str, tuple[float, float]]] = None) -> None:
    """Persist node (and optional group) coordinates for ``graph`` as JSON."""
    payload = {
        'version': 2,
        'positions': {k: _round(v) for k, v in positions.items()
                      if k in graph.devices},
        'groups': {k: _round(v) for k, v in (group_positions or {}).items()
                   if k in graph.devices},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(payload, f, indent=4)


def _load_map(path: str, key: str) -> dict[str, tuple[float, float]]:
    try:
        with open(path) as f:
            data = json.load(f)
        out: dict[str, tuple[float, float]] = {}
        for k, xy in data.get(key, {}).items():
            if isinstance(xy, (list, tuple)) and len(xy) == 2:
                out[k] = (float(xy[0]), float(xy[1]))
        return out
    except (OSError, ValueError, TypeError):
        return {}


def load_layout(path: str) -> dict[str, tuple[float, float]]:
    """Read saved node coordinates from ``path`` (empty dict on any error)."""
    return _load_map(path, 'positions')


def load_group_layout(path: str) -> dict[str, tuple[float, float]]:
    """Read saved collapsed-group coordinates from ``path``."""
    return _load_map(path, 'groups')


def apply_layout(graph: TopologyGraph, positions: dict[str, tuple[float, float]],
                 fallback: dict[str, tuple[float, float]]) -> dict[str, tuple[float, float]]:
    """Merge saved ``positions`` over ``fallback`` (auto-layout) coordinates."""
    merged = dict(fallback)
    for key, xy in positions.items():
        if key in graph.devices:
            merged[key] = xy
    return merged
