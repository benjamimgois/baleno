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
           'default_layout_path', 'save_map', 'load_map', 'default_map_path']


def default_layout_path() -> str:
    """Return the default layout file inside the Cetus config directory."""
    xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.join(Path.home(), '.config')
    return os.path.join(xdg, 'cetus', 'topology_layout.json')


def default_map_path() -> str:
    """Return the default full-map file inside the Cetus config directory."""
    xdg = os.environ.get('XDG_CONFIG_HOME') or os.path.join(Path.home(), '.config')
    return os.path.join(xdg, 'cetus', 'topology_map.json')


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


def save_map(graph: TopologyGraph, positions: dict[str, tuple[float, float]],
             path: str,
             group_positions: Optional[dict[str, tuple[float, float]]] = None) -> None:
    """Persist the whole topology map (devices, links and coordinates) as JSON.

    Format version 3::

        {
            "version": 3,
            "devices":   { "<id>": { ...Device.to_dict()... } },
            "links":     [ { ...PortLink.to_dict()... } ],
            "positions": { "<id>": [x, y] },
            "groups":    { "<parent_id>": [x, y] }
        }
    """
    payload = {
        'version': 3,
        'devices': {did: dev.to_dict() for did, dev in graph.devices.items()},
        'links': [link.to_dict() for link in graph.links],
        'positions': {k: _round(v) for k, v in positions.items()
                      if k in graph.devices},
        'groups': {k: _round(v) for k, v in (group_positions or {}).items()
                   if k in graph.devices},
    }
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w') as f:
        json.dump(payload, f, indent=4)


def load_map(path: str) -> tuple[TopologyGraph, dict[str, tuple[float, float]],
                                 dict[str, tuple[float, float]]]:
    """Read a full topology map.

    Returns ``(graph, positions, group_positions)``.  On any error (missing or
    corrupt file) an empty graph and empty coordinate maps are returned, so the
    caller starts with an empty map without raising.  Positions whose device id
    is not part of the graph are discarded.
    """
    graph = TopologyGraph()
    positions: dict[str, tuple[float, float]] = {}
    groups: dict[str, tuple[float, float]] = {}
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return graph, positions, groups
        graph = TopologyGraph.from_dict(data)
        for key, source in (('positions', positions), ('groups', groups)):
            for did, xy in (data.get(key) or {}).items():
                if did not in graph.devices:
                    continue
                if isinstance(xy, (list, tuple)) and len(xy) == 2:
                    source[did] = (float(xy[0]), float(xy[1]))
    except (OSError, ValueError, TypeError):
        return TopologyGraph(), {}, {}
    return graph, positions, groups
