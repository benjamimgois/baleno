# Design

## Context

During discovery, `LldpCollector.collect_async()` first populates `device.interfaces` via IF-MIB (`ifName`, `ifDescr`, `ifAlias`, `ifOperStatus`, etc.), and then calls `_collect_neighbors()`. However, `_collect_neighbors()` did not have access to `device` and relied solely on a single SNMP walk of `OID_LOC_PORT_ID` (`lldpLocPortId`).

If that walk times out or drops a UDP packet during parallel discovery (`MAX_CONCURRENT=8`), `_walk()` terminates prematurely via `break`, leaving all subsequent ports unmapped. Furthermore, some vendors (such as Huawei VRP with `local(7)` port subtype) return integer chassis port indices instead of text names. When unmapped, the code fell back to `str(local_port)` (e.g. `"35"`).

In `TopologyEngine.build()`, links are merged using:
```python
key = frozenset((
    (link.source_id, normalize_port(link.source_port)),
    (link.target_id, normalize_port(link.target_port)),
))
```
Because `"35"` != `"xgigabitethernet003"`, the reciprocal link reported by the remote peer was not matched, resulting in duplicate parallel edges flagged as a LAG bundle.

## Goals / Non-Goals

**Goals:**
- Provide robust multi-tier fallback for local port names in `LldpCollector`: `lldpLocPortId` -> `device.interfaces` (`ifIndex`) -> physical chassis port order -> `lldpLocPortDesc` -> `str(port)`.
- Update `_PORT_ALIASES` in `engine.py` to recognize `xgigabitethernet` and `xge`.
- Implement reciprocal link reconciliation in `TopologyEngine.build()` to resolve asymmetric link ends before deduplication.

**Non-Goals:**
- Altering manual link editing or link override mechanics.
- Altering live performance polling intervals.

## Decisions

### Decision 1: Pass `device` to `_collect_neighbors(engine, auth, target, device)`
Reusing `device.interfaces` costs zero extra network packets because IF-MIB is already queried prior to `_collect_neighbors()`. If `local_port` exists in `device.interfaces` (or matches a sorted physical port), the canonical interface name is immediately available.

### Decision 2: Multi-tier fallback hierarchy
For each neighbor row with index `local_port`:
1. Check `local_port_names` from `lldpLocPortId`. If it exists and is not purely a numeric representation when an interface name is known, use it.
2. Check `device.interfaces.get(local_port)`. If present and `iface.name` is non-empty, use `iface.name`.
3. Check sorted physical Ethernet interfaces in `device.interfaces`: if `1 <= local_port <= len(phys_interfaces)`, match to `phys_interfaces[local_port - 1].name`.
4. Check `local_port_descs` from `OID_LOC_PORT_DESC`.
5. Fall back to `str(local_port)`.

### Decision 3: Reciprocal Link Reconciliation in `TopologyEngine`
When two devices `A` and `B` have reciprocal LLDP reports:
- Link from A: `source=A, source_port='35', target=B, target_port='XGigabitEthernet0/0/3'`
- Link from B: `source=B, source_port='XGigabitEthernet0/0/3', target=A, target_port='XGigabitEthernet0/0/3'`
Since Link from B confirms that the port connecting to `B:XGigabitEthernet0/0/3` on device `A` is `'XGigabitEthernet0/0/3'`, `TopologyEngine` reconciles `A`'s `source_port` to `'XGigabitEthernet0/0/3'`, allowing both links to produce identical keys and cleanly merge into one physical link.

### Decision 4: Expand `_PORT_ALIASES`
Add:
- `'xgigabitethernet': 'xge'`
- `'xge': 'xge'`
- `'twentyfivegige': '25ge'`
- `'hundredgige': '100ge'`

## Risks / Trade-offs

- **[Risk] Multiple cables between same pair on same switch model**: If two devices actually have multiple physical links, will reciprocal reconciliation confuse them?
  → **Mitigation**: Reconciliation only updates an ambiguous/numeric port when the remote peer's target port matches exactly one reciprocal link. If both ends have distinct valid interface names, normal deduplication applies.
