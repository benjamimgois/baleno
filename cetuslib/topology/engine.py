"""Topology engine — resolves LLDP adjacencies into a graph, detects
anomalies (loops, LAGs, orphans) and computes node layouts.

Uses ``networkx`` when available (for layout and cycle detection); otherwise
falls back to a small self-contained implementation so the module never
hard-fails in a minimal environment.
"""

from __future__ import annotations

import ipaddress
import math
import random
from collections import defaultdict, deque
from typing import Iterable, Optional

from cetuslib.topology.models import (
    Device, DeviceRole, LldpNeighbor, PortLink, TopologyGraph,
)

__all__ = ['TopologyEngine', 'LAYOUTS']

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    nx = None
    HAS_NETWORKX = False


_PORT_ALIASES = {
    'gigabitethernet': 'gi',
    'fastethernet': 'fa',
    'tengigabitethernet': 'te',
    'twentyfivegige': '25ge',
    'fortygige': 'fo',
    'hundredgige': 'hu',
    'ethernet': 'eth',
    'port-channel': 'po',
    'bundle-ether': 'be',
    'ae': 'ae',
}


def normalize_port(name: str) -> str:
    """Normalise an interface name so 'GigabitEthernet0/1' == 'Gi0/1'."""
    n = (name or '').strip().lower()
    for full, short in _PORT_ALIASES.items():
        if n.startswith(full):
            n = short + n[len(full):]
            break
    return ''.join(ch for ch in n if ch.isalnum())


class TopologyEngine:
    """Build and lay out a :class:`TopologyGraph` from discovered devices."""

    SPACING = 180.0

    def __init__(self) -> None:
        self.graph = TopologyGraph()

    # ── graph construction ────────────────────────────────────────────────

    def build(self, devices: Iterable[Device],
              seed_networks: Optional[Iterable[str]] = None) -> TopologyGraph:
        devices = list(devices)
        g = TopologyGraph()
        for d in devices:
            g.add_device(d)

        index = self._build_index(devices)
        groups: dict[frozenset, list[PortLink]] = defaultdict(list)

        for d in devices:
            for n in d.lldp_neighbors:
                target = self._resolve_neighbor(n, index)
                if not target or target == d.id:
                    continue
                link = PortLink(
                    source_id=d.id,
                    source_port=n.local_port_name or str(n.local_port_num),
                    target_id=target,
                    target_port=n.remote_port_id or n.remote_port_desc or '',
                    source_ifindex=n.local_port_num,
                )
                groups[frozenset((d.id, target))].append(link)

        for pair, links in groups.items():
            physical: dict[frozenset, PortLink] = {}
            for link in links:
                key = frozenset((
                    (link.source_id, normalize_port(link.source_port)),
                    (link.target_id, normalize_port(link.target_port)),
                ))
                if key not in physical:
                    physical[key] = link
            merged = list(physical.values())
            lag = len(merged) > 1
            for link in merged:
                link.lag = lag
                g.links.append(link)
                if lag and merged not in g.lags:
                    g.lags.append(merged)

        linked: set[str] = set()
        for link in g.links:
            linked.update((link.source_id, link.target_id))
        g.orphans = [d.id for d in devices if d.id not in linked]
        g.loops = self.detect_cycles(g)
        self.assign_levels(g, seed_networks)
        self.graph = g
        return g

    def assign_levels(self, g: TopologyGraph,
                      seed_networks: Optional[Iterable[str]] = None) -> None:
        """Assign a 1-based hop level to every device.

        Level 1 = devices whose management IP lies inside one of the
        ``seed_networks`` (the networks the user asked to scan).  Level N =
        LLDP neighbour of a level N-1 device.  Devices unreachable from any
        seed (fully disconnected islands) default to level 2.
        """
        subnets: list[ipaddress._BaseNetwork] = []
        for entry in seed_networks or []:
            entry = (entry or '').strip()
            if not entry:
                continue
            try:
                subnets.append(ipaddress.ip_network(entry, strict=False))
            except ValueError:
                try:
                    subnets.append(ipaddress.ip_network(entry + '/32', strict=False))
                except ValueError:
                    continue

        def in_seed(ip: str) -> bool:
            if not ip:
                return False
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                return False
            return any(addr in subnet for subnet in subnets)

        for device in g.devices.values():
            device.layer = 0

        adj: dict[str, list[str]] = defaultdict(list)
        for link in g.links:
            adj[link.source_id].append(link.target_id)
            adj[link.target_id].append(link.source_id)

        queue: deque[str] = deque()
        for device in g.devices.values():
            if in_seed(device.ip):
                device.layer = 1
                queue.append(device.id)

        while queue:
            nid = queue.popleft()
            level = g.devices[nid].layer
            for nb in adj.get(nid, []):
                nd = g.devices.get(nb)
                if nd is None or nd.layer != 0:
                    continue
                nd.layer = level + 1
                queue.append(nb)

        for device in g.devices.values():
            if device.layer == 0:
                device.layer = 2

    @staticmethod
    def _build_index(devices: list[Device]) -> dict[str, dict[str, str]]:
        chassis: dict[str, str] = {}
        names: dict[str, str] = {}
        ips: dict[str, str] = {}
        for d in devices:
            if d.chassis_id:
                chassis.setdefault(normalize_port(d.chassis_id), d.id)
                chassis.setdefault(d.chassis_id.lower(), d.id)
            if d.hostname:
                names.setdefault(d.hostname.lower(), d.id)
            if d.ip:
                ips.setdefault(d.ip, d.id)
        return {'chassis': chassis, 'name': names, 'ip': ips}

    def _resolve_neighbor(self, n: LldpNeighbor, index: dict) -> Optional[str]:
        if n.remote_chassis_id:
            hit = index['chassis'].get(normalize_port(n.remote_chassis_id)) \
                or index['chassis'].get(n.remote_chassis_id.lower())
            if hit:
                return hit
        if n.remote_sys_name:
            hit = index['name'].get(n.remote_sys_name.lower())
            if hit:
                return hit
        if n.remote_mgmt_addr:
            hit = index['ip'].get(n.remote_mgmt_addr)
            if hit:
                return hit
        return None

    # ── cycle / loop detection ────────────────────────────────────────────

    def detect_cycles(self, g: TopologyGraph) -> list[list[str]]:
        adj: dict[str, list[str]] = defaultdict(list)
        for link in g.links:
            adj[link.source_id].append(link.target_id)
            adj[link.target_id].append(link.source_id)

        if HAS_NETWORKX:
            nxg = nx.Graph()
            nxg.add_edges_from((l.source_id, l.target_id) for l in g.links)
            try:
                return [list(c) for c in nx.cycle_basis(nxg)]
            except Exception:
                pass

        # fallback: iterative DFS detecting back-edges (fundamental cycles)
        visited: set[str] = set()
        cycles: list[list[str]] = []
        for start in adj:
            if start in visited:
                continue
            visited.add(start)
            stack = [(start, iter(adj[start]))]
            path = [start]
            in_path = {start}
            parent: dict[str, Optional[str]] = {start: None}
            while stack:
                node, it = stack[-1]
                advanced = False
                for nb in it:
                    if nb == parent[node]:
                        continue
                    if nb in in_path:          # back edge → cycle
                        idx = path.index(nb)
                        cycles.append(path[idx:] + [nb])
                        continue
                    if nb in visited:
                        continue
                    visited.add(nb)
                    parent[nb] = node
                    in_path.add(nb)
                    path.append(nb)
                    stack.append((nb, iter(adj[nb])))
                    advanced = True
                    break
                if not advanced:
                    stack.pop()
                    in_path.discard(node)
                    path.pop()
        return cycles

    # ── clustering ────────────────────────────────────────────────────────

    def group_children(self, g: TopologyGraph, threshold: int = 5) -> dict[str, list[str]]:
        """Find level-1 devices with more than ``threshold`` level-2 neighbours.

        Returns ``{parent_id: [child_id, ...]}`` for the over-populated parents.
        The returned children are candidates for visual collapsing (a single
        group node) so the map stays readable.
        """
        children: dict[str, set[str]] = defaultdict(set)
        for link in g.links:
            src = g.devices.get(link.source_id)
            dst = g.devices.get(link.target_id)
            if src is None or dst is None:
                continue
            if src.layer == 1 and dst.layer == 2:
                children[src.id].add(dst.id)
            elif dst.layer == 1 and src.layer == 2:
                children[dst.id].add(src.id)
        return {pid: sorted(ids) for pid, ids in children.items()
                if len(ids) > threshold}

    # ── layouts ───────────────────────────────────────────────────────────

    def layout_hierarchical(self, g: TopologyGraph,
                            clusters: Optional[dict[str, list[str]]] = None
                            ) -> tuple[dict[str, tuple[float, float]],
                                       dict[str, tuple[float, float]]]:
        """Return ``(node_pos, group_pos)``.

        Devices are layered vertically by hop level: level 1 on top, level 2
        below, and so on (spread horizontally within each row).  Children that
        belong to a ``clusters`` entry are removed from the row and replaced by
        a single group slot (keyed by the parent id) so collapsed groups still
        get a non-overlapping position.
        """
        if not g.devices:
            return {}, {}
        clusters = clusters or {}
        grouped: set[str] = set()
        for members in clusters.values():
            grouped.update(members)

        levels = {d.layer for d in g.devices.values()}
        if len(levels) > 1 or clusters:
            return self._layout_by_level(g, grouped, clusters)
        return self._layout_by_bfs(g, grouped), {}

    def layout_tree(self, g: TopologyGraph,
                    clusters: Optional[dict[str, list[str]]] = None
                    ) -> tuple[dict[str, tuple[float, float]],
                               dict[str, tuple[float, float]]]:
        """Column-per-parent layout: each level-1 device owns a column and its
        level-2 children (and/or its collapsed group circle) sit directly below
        it.  Remaining devices (deeper levels, orphans, same-level peers) are
        placed in flat rows underneath.

        This keeps every level-2 device visually attached to its level-1 parent,
        so nothing appears to float in a disconnected row.
        """
        if not g.devices:
            return {}, {}
        clusters = clusters or {}
        grouped: set[str] = set()
        for members in clusters.values():
            grouped.update(members)

        # level-2 children of each level-1 device
        children: dict[str, set[str]] = defaultdict(set)
        for link in g.links:
            src = g.devices.get(link.source_id)
            dst = g.devices.get(link.target_id)
            if src is None or dst is None:
                continue
            if src.layer <= 1 and dst.layer == 2:
                children[src.id].add(dst.id)
            elif dst.layer <= 1 and src.layer == 2:
                children[dst.id].add(src.id)

        l1 = sorted((d.id for d in g.devices.values() if d.layer <= 1),
                    key=lambda n: g.devices[n].label)
        pos: dict[str, tuple[float, float]] = {}
        group_pos: dict[str, tuple[float, float]] = {}

        spacing = self.SPACING
        l1_width = (len(l1) - 1) * spacing
        l1_x: dict[str, float] = {}
        for i, n in enumerate(l1):
            x = i * spacing - l1_width / 2
            l1_x[n] = x
            pos[n] = (x, 0.0)

        y2 = spacing * 1.4
        for parent in l1:
            kids = sorted([k for k in children.get(parent, ()) if k not in grouped],
                          key=lambda n: g.devices[n].label)
            has_group = parent in clusters
            slots = len(kids) + (1 if has_group else 0)
            start_x = l1_x[parent] - (slots - 1) * spacing / 2
            idx = 0
            if has_group:
                group_pos[parent] = (start_x + idx * spacing, y2)
                idx += 1
            for kid in kids:
                pos[kid] = (start_x + idx * spacing, y2)
                idx += 1

        # remaining devices → flat rows by level
        remaining = [d.id for d in g.devices.values()
                     if d.id not in pos and d.id not in grouped]
        by_layer: dict[int, list[str]] = defaultdict(list)
        for n in remaining:
            lvl = g.devices[n].layer if g.devices[n].layer > 0 else 1
            if lvl <= 2:
                lvl = 2
            by_layer[lvl].append(n)
        for lvl in sorted(by_layer):
            nodes = sorted(by_layer[lvl], key=lambda n: g.devices[n].label)
            width = (len(nodes) - 1) * spacing
            y = (lvl - 1) * spacing * 1.4
            for i, n in enumerate(nodes):
                pos[n] = (i * spacing - width / 2, y)
        return pos, group_pos

    def _layout_by_level(self, g: TopologyGraph, grouped: set[str],
                         clusters: dict[str, list[str]]
                         ) -> tuple[dict[str, tuple[float, float]],
                                    dict[str, tuple[float, float]]]:
        by_level: dict[int, list[str]] = defaultdict(list)
        for device_id, device in g.devices.items():
            if device_id in grouped:
                continue
            by_level[device.layer if device.layer > 0 else 1].append(device_id)

        group_levels: dict[int, list[str]] = defaultdict(list)
        for parent_id in clusters:
            group_levels[2].append(parent_id)

        pos: dict[str, tuple[float, float]] = {}
        group_pos: dict[str, tuple[float, float]] = {}
        for lvl in sorted(set(by_level) | set(group_levels)):
            entries: list[tuple[object, str]] = []
            for node in by_level.get(lvl, []):
                entries.append((node, g.devices[node].label))
            for pid in group_levels.get(lvl, []):
                entries.append((('__group__', pid), g.devices[pid].label))
            entries.sort(key=lambda e: e[1])
            width = (len(entries) - 1) * self.SPACING
            for i, (key, _label) in enumerate(entries):
                x = i * self.SPACING - width / 2
                y = (lvl - 1) * self.SPACING * 1.4
                if isinstance(key, tuple):
                    group_pos[key[1]] = (x, y)
                else:
                    pos[key] = (x, y)
        return pos, group_pos

    def _layout_by_bfs(self, g: TopologyGraph,
                       grouped: set[str]) -> dict[str, tuple[float, float]]:
        adj: dict[str, list[str]] = defaultdict(list)
        for link in g.links:
            adj[link.source_id].append(link.target_id)
            adj[link.target_id].append(link.source_id)

        roots = self._pick_roots(g, adj)
        layer: dict[str, int] = {}
        q = deque(roots)
        for r in roots:
            layer[r] = 0
        while q:
            node = q.popleft()
            for nb in adj[node]:
                if nb in layer:
                    continue
                layer[nb] = layer[node] + 1
                q.append(nb)

        for d in g.devices:
            layer.setdefault(d, 0)

        by_layer: dict[int, list[str]] = defaultdict(list)
        for node, lvl in layer.items():
            by_layer[lvl].append(node)

        pos: dict[str, tuple[float, float]] = {}
        for lvl in sorted(by_layer):
            nodes = sorted(by_layer[lvl], key=lambda n: (layer[n], g.devices[n].label))
            width = (len(nodes) - 1) * self.SPACING
            for i, node in enumerate(nodes):
                pos[node] = (
                    i * self.SPACING - width / 2,
                    lvl * self.SPACING * 1.4,
                )
        return pos

    def layout_force(self, g: TopologyGraph, clusters=None,
                     iterations: int = 300) -> tuple[dict[str, tuple[float, float]],
                                                     dict[str, tuple[float, float]]]:
        """Force-directed (Fruchterman–Reingold) layout, plus group positions."""
        if not g.devices:
            return {}, {}
        if HAS_NETWORKX:
            nxg = nx.Graph()
            nxg.add_nodes_from(g.devices)
            nxg.add_edges_from((l.source_id, l.target_id) for l in g.links)
            try:
                pos = nx.spring_layout(nxg, seed=42, iterations=iterations)
                pos = {n: (x * 400, y * 400) for n, (x, y) in pos.items()}
                return pos, self._group_positions(g, clusters, pos)
            except Exception:
                pass

        nodes = list(g.devices)
        n = len(nodes)
        area = (max(n, 1) * self.SPACING) ** 2
        k = math.sqrt(area / n) if n else self.SPACING

        rng = random.Random(42)
        pos = {node: (rng.uniform(-area, area), rng.uniform(-area, area)) for node in nodes}
        adj: dict[str, list[str]] = defaultdict(list)
        for link in g.links:
            adj[link.source_id].append(link.target_id)
            adj[link.target_id].append(link.source_id)

        t = area * 0.1
        for _ in range(iterations):
            disp = {node: [0.0, 0.0] for node in nodes}
            for i in range(n):
                for j in range(i + 1, n):
                    a, b = nodes[i], nodes[j]
                    dx = pos[a][0] - pos[b][0]
                    dy = pos[a][1] - pos[b][1]
                    dist = math.hypot(dx, dy) or 0.01
                    force = k * k / dist
                    fx = dx / dist * force
                    fy = dy / dist * force
                    disp[a][0] += fx
                    disp[a][1] += fy
                    disp[b][0] -= fx
                    disp[b][1] -= fy
            for a in nodes:
                for b in adj[a]:
                    dx = pos[a][0] - pos[b][0]
                    dy = pos[a][1] - pos[b][1]
                    dist = math.hypot(dx, dy) or 0.01
                    force = dist * dist / k
                    disp[a][0] -= dx / dist * force
                    disp[a][1] -= dy / dist * force
            for node in nodes:
                d = math.hypot(*disp[node]) or 0.01
                capped = min(d, t)
                pos[node] = (pos[node][0] + disp[node][0] / d * capped,
                             pos[node][1] + disp[node][1] / d * capped)
            t = max(t * 0.95, 1.0)
        return pos, self._group_positions(g, clusters, pos)

    def layout_concentric(self, g: TopologyGraph, clusters=None
                          ) -> tuple[dict[str, tuple[float, float]],
                                     dict[str, tuple[float, float]]]:
        """Concentric layout: roots at the centre, devices on rings by hop level."""
        if not g.devices:
            return {}, {}
        clusters = clusters or {}
        grouped: set[str] = {m for members in clusters.values() for m in members}

        adj: dict[str, list[str]] = defaultdict(list)
        for link in g.links:
            adj[link.source_id].append(link.target_id)
            adj[link.target_id].append(link.source_id)

        roots = self._pick_roots(g, adj)

        # hop level (distance from any root); unreachable → outermost ring
        level: dict[str, int] = {}
        q = deque(roots)
        for r in roots:
            level[r] = 0
        while q:
            node = q.popleft()
            for nb in adj[node]:
                if nb in level:
                    continue
                level[nb] = level[node] + 1
                q.append(nb)
        max_level = max(level.values(), default=0) or 1

        pos: dict[str, tuple[float, float]] = {}
        spacing = self.SPACING

        n_roots = len(roots)
        if n_roots == 1:
            pos[roots[0]] = (0.0, 0.0)
        else:
            r0 = spacing * 0.35
            for i, r in enumerate(sorted(roots, key=lambda n: g.devices[n].label)):
                ang = 2 * math.pi * i / n_roots
                pos[r] = (r0 * math.cos(ang), r0 * math.sin(ang))

        rings: dict[int, list[str]] = defaultdict(list)
        for d in g.devices:
            if d in grouped or d in pos:
                continue
            lvl = level.get(d, max_level + 1)
            rings[lvl if lvl > 0 else max_level + 1].append(d)

        for lvl, nodes in rings.items():
            nodes_sorted = sorted(nodes, key=lambda n: g.devices[n].label)
            radius = spacing * lvl
            n = len(nodes_sorted)
            for i, node in enumerate(nodes_sorted):
                ang = 2 * math.pi * i / n
                pos[node] = (radius * math.cos(ang), radius * math.sin(ang))

        return pos, self._group_positions(g, clusters, pos)

    def layout_bfs_tree(self, g: TopologyGraph, clusters=None
                        ) -> tuple[dict[str, tuple[float, float]],
                                   dict[str, tuple[float, float]]]:
        """Breadth-first tree layout, with group positions for collapsed clusters."""
        if not g.devices:
            return {}, {}
        clusters = clusters or {}
        grouped: set[str] = {m for members in clusters.values() for m in members}
        pos = self._layout_by_bfs(g, grouped)
        return pos, self._group_positions(g, clusters, pos)

    @staticmethod
    def _group_positions(g: TopologyGraph, clusters,
                         pos: dict[str, tuple[float, float]]
                         ) -> dict[str, tuple[float, float]]:
        """Position collapsed groups by averaging their members' coordinates."""
        group_pos: dict[str, tuple[float, float]] = {}
        for parent_id, member_ids in (clusters or {}).items():
            xs: list[float] = []
            ys: list[float] = []
            for m in member_ids:
                p = pos.get(m)
                if p:
                    xs.append(p[0])
                    ys.append(p[1])
            if xs:
                group_pos[parent_id] = (sum(xs) / len(xs), sum(ys) / len(ys))
            else:
                pp = pos.get(parent_id, (0.0, 0.0))
                group_pos[parent_id] = (pp[0], pp[1] + TopologyEngine.SPACING * 1.4)
        return group_pos

    @staticmethod
    def _pick_roots(g: TopologyGraph, adj: dict[str, list[str]]) -> list[str]:
        infra = [d.id for d in g.devices.values()
                 if d.role in (DeviceRole.CORE, DeviceRole.ROUTER)]
        if infra:
            return infra
        if g.devices:
            return sorted(g.devices, key=lambda n: len(adj[n]), reverse=True)[:1]
        return []


# Registry of layout modes → method name on TopologyEngine.  Each entry must
# accept ``(graph, clusters)`` and return ``(node_pos, group_pos)``.
LAYOUTS = {
    'hierarchical': 'layout_tree',
    'force': 'layout_force',
    'concentric': 'layout_concentric',
    'bfs': 'layout_bfs_tree',
}
