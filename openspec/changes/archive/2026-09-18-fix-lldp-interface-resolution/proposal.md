# Proposal

## Why

During network discovery via SNMP LLDP, packet drops or timeouts during lldpLocPortId table walks can cause local port names to fall back to raw chassis port numbers (e.g. '35' instead of 'XGigabitEthernet0/0/3'). Furthermore, when both interconnected switches are collected, the topology engine fails to deduplicate reciprocal links if one switch reported a raw port number while the other reported the full interface name, resulting in non-existent ghost links and erroneously flagging legitimate single physical links as Link Aggregation Groups (LAG / trunks).

## What Changes

- **Robust Local Port Resolution**: Implement fallback resolution in LldpCollector: when lldpLocPortId walk is incomplete, missing, or returns pure numbers/local subtypes, resolve local interface names via device.interfaces (ifName / ifDescr from IF-MIB) and OID_LOC_PORT_DESC.
- **Extended Port Normalization**: Enhance normalize_port in TopologyEngine to recognize 10GE/100GE variants including xgigabitethernet and xge.
- **Reciprocal Link Reconciliation**: In TopologyEngine.build(), correlate bidirectional LLDP advertisements between pairs of devices so that if one end has an unresolved numeric or ambiguous port identifier, it is reconciled with the remote peer's advertised target port before link deduplication and LAG detection.

## Capabilities

### New Capabilities
- `topology-lldp-resolution`: Resolves local interface names using IF-MIB fallbacks, normalizes extended port aliases, and reconciles reciprocal LLDP neighbor links to prevent ghost interfaces and false LAG duplicates.

### Modified Capabilities

## Impact

- Affected code: `balenolib/topology/collector.py` and `balenolib/topology/engine.py`.
- No breaking API changes or database schema changes.
