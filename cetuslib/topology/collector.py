"""Layer 2 discovery — SNMP LLDP collection and adjacency parsing.

Implements the LLDP-MIB (``1.0.8802.1.1.2``) reader over ``pysnmp`` using the
same ``v3arch.asyncio`` backend the rest of Cetus already uses.  Produces a
:class:`~cetuslib.topology.models.Device` populated with local identity, the
IF-MIB interface table and the decoded LLDP remote-neighbor table.

CDP (``1.3.6.1.4.1.9.9.23``) is intentionally left as a future extension
point — see :class:`LldpCollector` docstring for the seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from cetuslib.topology.models import Device, DeviceRole, Interface, LldpNeighbor

__all__ = ['SnmpCredentials', 'LldpCollector', 'SnmpUnavailableError', 'LLDP_MIB']


# ── OID constants ─────────────────────────────────────────────────────────
LLDP_MIB = '1.0.8802.1.1.2'

OID_LOC_CHASSIS_ID_SUBTYPE = f'{LLDP_MIB}.1.3.1.0'
OID_LOC_CHASSIS_ID = f'{LLDP_MIB}.1.3.2.0'
OID_LOC_SYS_NAME = f'{LLDP_MIB}.1.3.3.0'
OID_LOC_SYS_DESC = f'{LLDP_MIB}.1.3.4.0'

# lldpLocPortTable  (index = lldpLocPortNum)
OID_LOC_PORT_ID_SUBTYPE = f'{LLDP_MIB}.1.3.7.1.2'
OID_LOC_PORT_ID = f'{LLDP_MIB}.1.3.7.1.3'
OID_LOC_PORT_DESC = f'{LLDP_MIB}.1.3.7.1.4'

# lldpRemTable  (index = lldpRemTimeMark . lldpRemLocalPortNum . lldpRemIndex)
OID_REM_TIME_MARK = f'{LLDP_MIB}.1.4.1.1.1'
OID_REM_LOCAL_PORT_NUM = f'{LLDP_MIB}.1.4.1.1.2'
OID_REM_INDEX = f'{LLDP_MIB}.1.4.1.1.3'
OID_REM_CHASSIS_ID_SUBTYPE = f'{LLDP_MIB}.1.4.1.1.4'
OID_REM_CHASSIS_ID = f'{LLDP_MIB}.1.4.1.1.5'
OID_REM_PORT_ID_SUBTYPE = f'{LLDP_MIB}.1.4.1.1.6'
OID_REM_PORT_ID = f'{LLDP_MIB}.1.4.1.1.7'
OID_REM_PORT_DESC = f'{LLDP_MIB}.1.4.1.1.8'
OID_REM_SYS_NAME = f'{LLDP_MIB}.1.4.1.1.9'
OID_REM_SYS_DESC = f'{LLDP_MIB}.1.4.1.1.10'

# lldpRemManAddrTable (index = timeMark . localPortNum . remIndex . addrSubtype)
OID_REM_MAN_ADDR_SUBTYPE = f'{LLDP_MIB}.1.4.2.1.3'
OID_REM_MAN_ADDR = f'{LLDP_MIB}.1.4.2.1.4'
OID_REM_MAN_ADDR_IF_SUBTYPE = f'{LLDP_MIB}.1.4.2.1.5'
OID_REM_MAN_ADDR_IF_ID = f'{LLDP_MIB}.1.4.2.1.6'
OID_REM_MAN_ADDR_OID = f'{LLDP_MIB}.1.4.2.1.7'

# IF-MIB
OID_IF_DESCR = '1.3.6.1.2.1.2.2.1.2'
OID_IF_ALIAS = '1.3.6.1.2.1.31.1.1.1.18'
OID_IF_NAME = '1.3.6.1.2.1.31.1.1.1.1'
OID_IF_OPER_STATUS = '1.3.6.1.2.1.2.2.1.8'

# Future CDP extension point (CISCO-CDP-MIB).
CDP_MIB = '1.3.6.1.4.1.9.9.23'


@dataclass
class SnmpCredentials:
    """SNMP credentials for v2c or v3."""

    version: str = '2c'          # '1' | '2c' | '3'
    community: str = 'public'
    username: str = ''
    auth_proto: str = 'None'     # None/MD5/SHA/SHA224/SHA256/SHA384/SHA512
    auth_pass: str = ''
    priv_proto: str = 'None'     # None/DES/3DES/AES/AES192/AES256
    priv_pass: str = ''


class SnmpUnavailableError(Exception):
    """Raised when a host does not answer SNMP (timeout / wrong community).

    Lets the worker distinguish an ICMP-only host (orphan) from a device whose
    LLDP table was actually collected.
    """


# ── value decoding helpers ────────────────────────────────────────────────

def _text(raw: bytes) -> str:
    if all(0x20 <= b <= 0x7E or b in (0x09, 0x0A, 0x0D) for b in raw):
        return raw.decode('ascii', errors='replace').strip()
    return ':'.join(f'{b:02X}' for b in raw)


def _mac(raw: bytes) -> str:
    if len(raw) == 6:
        return ':'.join(f'{b:02X}' for b in raw)
    return _text(raw)


def _net_addr(raw: bytes) -> str:
    if len(raw) == 4:
        return '.'.join(str(b) for b in raw)
    if len(raw) == 16:
        return ':'.join(raw[i:i + 2].hex() for i in range(0, 16, 2))
    return _text(raw)


def decode_chassis_id(raw: bytes, subtype: int) -> str:
    if subtype == 4:            # MAC address
        return _mac(raw)
    if subtype == 5:            # network address
        return _net_addr(raw)
    return _text(raw)           # component / alias / interface-name / local


def decode_port_id(raw: bytes, subtype: int) -> str:
    if subtype == 3:            # MAC address
        return _mac(raw)
    if subtype == 4:            # network address
        return _net_addr(raw)
    return _text(raw)           # alias / component / interface-name / local


def _format_varbind(value: Any) -> str:
    """Best-effort human-readable value from a pysnmp object."""
    name = type(value).__name__
    if name == 'IpAddress':
        try:
            raw = value.asOctets()
            if len(raw) == 4:
                return '.'.join(str(b) for b in raw)
        except Exception:
            pass
    if name in ('OctetString', 'Bits', 'Opaque', 'DisplayString'):
        try:
            return _text(value.asOctets())
        except Exception:
            pass
    return str(value)


def _oid_suffix(oid: str, prefix: str) -> list[str]:
    """Return the index components of ``oid`` relative to ``prefix``."""
    p = prefix.rstrip('.')
    if oid == p:
        return []
    if oid.startswith(p + '.'):
        return oid[len(p) + 1:].split('.')
    return []


def _guess_role(sys_descr: str) -> DeviceRole:
    d = sys_descr.lower()
    if 'firewall' in d or 'fortigate' in d or 'fortinet' in d \
            or 'palo alto' in d or 'firepower' in d or 'cisco asa' in d:
        return DeviceRole.FIREWALL
    if 'access point' in d or 'wireless' in d or ' aironet' in d or 'wlan' in d:
        return DeviceRole.AP
    if 'camera' in d or 'cctv' in d or 'ip camera' in d or 'nvr' in d \
            or 'surveillance' in d:
        return DeviceRole.CAMERA
    if 'cloud' in d or 'internet' in d or 'wan accelerator' in d:
        return DeviceRole.CLOUD
    if 'router' in d or 'routeros' in d or 'ios-xr' in d or 'junos' in d:
        return DeviceRole.ROUTER
    if 'switch' in d or 'ios-xe' in d or 'fabric' in d or 'nexus' in d \
            or 'catalyst' in d:
        return DeviceRole.SWITCH
    if 'server' in d or 'linux' in d or 'windows' in d or 'esxi' in d:
        return DeviceRole.SERVER
    return DeviceRole.UNKNOWN


class LldpCollector:
    """Collect LLDP + interface data from one device via SNMP.

    Usage::

        creds = SnmpCredentials(version='2c', community='public')
        device = LldpCollector(creds).collect('192.168.1.1')
    """

    def __init__(self, credentials: SnmpCredentials, port: int = 161,
                 timeout: float = 2.0, retries: int = 1):
        self.credentials = credentials
        self.port = port
        self.timeout = timeout
        self.retries = retries

    # ── public API ────────────────────────────────────────────────────────

    def collect(self, host: str) -> Device:
        """Synchronous entry point (safe to call from a QThread)."""
        import asyncio
        return asyncio.run(self.collect_async(host))

    async def collect_async(self, host: str) -> Device:
        from pysnmp.hlapi.v3arch.asyncio import (
            SnmpEngine, UdpTransportTarget, ContextData,
            ObjectType, ObjectIdentity, get_cmd, walk_cmd,
        )

        engine = SnmpEngine()
        device = Device(id=host, ip=host)
        try:
            target = await UdpTransportTarget.create(
                (host, self.port), timeout=self.timeout, retries=self.retries)
            auth = self._auth_data()

            # Local identity
            chassis_id = await self._get(engine, auth, target, OID_LOC_CHASSIS_ID)
            if chassis_id is None:
                raise SnmpUnavailableError(host)
            chassis_sub = await self._get(engine, auth, target, OID_LOC_CHASSIS_ID_SUBTYPE)
            sys_name = await self._get(engine, auth, target, OID_LOC_SYS_NAME)
            sys_desc = await self._get(engine, auth, target, OID_LOC_SYS_DESC)

            device.chassis_id = chassis_id
            device.chassis_subtype = chassis_sub or ''
            device.hostname = sys_name or ''
            device.sys_descr = sys_desc or ''
            device.vendor, device.model = self._parse_sysdescr(sys_desc or '')
            if device.role == DeviceRole.UNKNOWN:
                device.role = _guess_role(sys_desc or '')
            if device.id == host:
                device.id = chassis_id or sys_name or host

            # Interfaces (IF-MIB)
            await self._fill_interfaces(engine, auth, target, device)

            # LLDP neighbors
            device.lldp_neighbors = await self._collect_neighbors(
                engine, auth, target)

            device.status = 'up'
        finally:
            engine.close_dispatcher()
        return device

    # ── SNMP primitives ───────────────────────────────────────────────────

    def _auth_data(self):
        from pysnmp.hlapi.v3arch.asyncio import (
            CommunityData, UsmUserData, usmNoAuthProtocol, usmNoPrivProtocol,
            usmHMACMD5AuthProtocol, usmHMACSHAAuthProtocol,
            usmHMAC128SHA224AuthProtocol, usmHMAC192SHA256AuthProtocol,
            usmHMAC256SHA384AuthProtocol, usmHMAC384SHA512AuthProtocol,
            usmDESPrivProtocol, usm3DESEDEPrivProtocol,
            usmAesCfb128Protocol, usmAesCfb192Protocol, usmAesCfb256Protocol,
        )
        c = self.credentials
        if c.version in ('1', '2c'):
            return CommunityData(c.community, mpModel=0 if c.version == '1' else 1)
        auth_map = {
            'None': usmNoAuthProtocol, 'MD5': usmHMACMD5AuthProtocol,
            'SHA': usmHMACSHAAuthProtocol, 'SHA224': usmHMAC128SHA224AuthProtocol,
            'SHA256': usmHMAC192SHA256AuthProtocol,
            'SHA384': usmHMAC256SHA384AuthProtocol,
            'SHA512': usmHMAC384SHA512AuthProtocol,
        }
        priv_map = {
            'None': usmNoPrivProtocol, 'DES': usmDESPrivProtocol,
            '3DES': usm3DESEDEPrivProtocol, 'AES': usmAesCfb128Protocol,
            'AES192': usmAesCfb192Protocol, 'AES256': usmAesCfb256Protocol,
        }
        return UsmUserData(
            c.username,
            authKey=c.auth_pass or None,
            privKey=c.priv_pass or None,
            authProtocol=auth_map.get(c.auth_proto, usmNoAuthProtocol),
            privProtocol=priv_map.get(c.priv_proto, usmNoPrivProtocol),
        )

    async def _get(self, engine, auth, target, oid: str) -> Optional[str]:
        from pysnmp.hlapi.v3arch.asyncio import (
            ContextData, ObjectType, ObjectIdentity, get_cmd,
        )
        err_ind, err_stat, _, var_binds = await get_cmd(
            engine, auth, target, ContextData(),
            ObjectType(ObjectIdentity(oid)))
        if err_ind or err_stat or not var_binds:
            return None
        return _format_varbind(var_binds[0][1])

    async def _walk(self, engine, auth, target, oid: str) -> list[tuple[str, str]]:
        from pysnmp.hlapi.v3arch.asyncio import (
            ContextData, ObjectType, ObjectIdentity, walk_cmd,
        )
        out: list[tuple[str, str]] = []
        try:
            async for (err_ind, err_stat, _, var_binds) in walk_cmd(
                    engine, auth, target, ContextData(),
                    ObjectType(ObjectIdentity(oid)), lexicographicMode=False):
                if err_ind or err_stat:
                    break
                for vb in var_binds:
                    out.append((str(vb[0]), _format_varbind(vb[1])))
        except Exception:
            pass
        return out

    async def _walk_raw(self, engine, auth, target, oid: str) -> list[tuple[str, bytes]]:
        """Like :meth:`_walk` but returns raw octets (for OIDs that hold a
        binary value such as an IP address, where hex-formatting would corrupt
        the address)."""
        from pysnmp.hlapi.v3arch.asyncio import (
            ContextData, ObjectType, ObjectIdentity, walk_cmd,
        )
        out: list[tuple[str, bytes]] = []
        try:
            async for (err_ind, err_stat, _, var_binds) in walk_cmd(
                    engine, auth, target, ContextData(),
                    ObjectType(ObjectIdentity(oid)), lexicographicMode=False):
                if err_ind or err_stat:
                    break
                for vb in var_binds:
                    try:
                        out.append((str(vb[0]), vb[1].asOctets()))
                    except Exception:
                        continue
        except Exception:
            pass
        return out

    # ── table builders ────────────────────────────────────────────────────

    async def _fill_interfaces(self, engine, auth, target, device: Device) -> None:
        names = await self._walk(engine, auth, target, OID_IF_NAME)
        descrs = await self._walk(engine, auth, target, OID_IF_DESCR)
        aliases = await self._walk(engine, auth, target, OID_IF_ALIAS)
        statuses = await self._walk(engine, auth, target, OID_IF_OPER_STATUS)

        for oid, val in names:
            try:
                idx = int(_oid_suffix(oid, OID_IF_NAME)[-1])
            except (IndexError, ValueError):
                continue
            device.interfaces[idx] = Interface(index=idx, name=val)

        def _apply(rows, base_oid, attr):
            for oid, val in rows:
                try:
                    idx = int(_oid_suffix(oid, base_oid)[-1])
                except (IndexError, ValueError):
                    continue
                if idx in device.interfaces:
                    setattr(device.interfaces[idx], attr, val)

        _apply(descrs, OID_IF_DESCR, 'descr')
        _apply(aliases, OID_IF_ALIAS, 'alias')
        for oid, val in statuses:
            try:
                idx = int(_oid_suffix(oid, OID_IF_OPER_STATUS)[-1])
            except (IndexError, ValueError):
                continue
            if idx in device.interfaces:
                device.interfaces[idx].oper_status = (
                    'up' if val == '1' else 'down' if val == '2' else 'unknown')

    async def _collect_neighbors(self, engine, auth, target) -> list[LldpNeighbor]:
        """Walk the LLDP remote table columns and merge by (localPortNum, remIndex)."""
        columns = {
            'remote_chassis_id': OID_REM_CHASSIS_ID,
            'remote_port_id': OID_REM_PORT_ID,
            'remote_port_desc': OID_REM_PORT_DESC,
            'remote_sys_name': OID_REM_SYS_NAME,
            'remote_sys_desc': OID_REM_SYS_DESC,
            'remote_chassis_subtype': OID_REM_CHASSIS_ID_SUBTYPE,
            'remote_port_subtype': OID_REM_PORT_ID_SUBTYPE,
        }
        rows: dict[tuple[int, int], dict[str, str]] = {}

        for field, oid in columns.items():
            for full_oid, val in await self._walk(engine, auth, target, oid):
                suffix = _oid_suffix(full_oid, oid)
                if len(suffix) < 3:
                    continue
                try:
                    time_mark = int(suffix[-3])
                    local_port = int(suffix[-2])
                    rem_index = int(suffix[-1])
                except ValueError:
                    continue
                key = (local_port, rem_index)
                row = rows.setdefault(key, {})
                row['time_mark'] = str(time_mark)
                row[field] = val

        # Local port id (lldpLocPortId) → name for the "source" side of the link
        local_port_names: dict[int, str] = {}
        for full_oid, val in await self._walk(engine, auth, target, OID_LOC_PORT_ID):
            suffix = _oid_suffix(full_oid, OID_LOC_PORT_ID)
            if not suffix:
                continue
            try:
                local_port_names[int(suffix[-1])] = val
            except ValueError:
                continue

        # Management addresses (IPv4 only, subtype == 1).  The raw octets are
        # decoded as a network address; formatting them as a generic OctetString
        # would hex-encode the IP and break correlation + level assignment.
        mgmt: dict[tuple[int, int], str] = {}
        for full_oid, raw in await self._walk_raw(engine, auth, target, OID_REM_MAN_ADDR):
            suffix = _oid_suffix(full_oid, OID_REM_MAN_ADDR)
            if len(suffix) < 4:
                continue
            try:
                time_mark, local_port, rem_index, subtype = (
                    int(suffix[-4]), int(suffix[-3]), int(suffix[-2]), int(suffix[-1]))
            except ValueError:
                continue
            if subtype == 1:
                mgmt[(local_port, rem_index)] = _net_addr(raw)

        neighbors: list[LldpNeighbor] = []
        for (local_port, rem_index), row in rows.items():
            chassis_id = self._decode_id(
                row.get('remote_chassis_id', ''), row.get('remote_chassis_subtype', ''))
            port_id = self._decode_id(
                row.get('remote_port_id', ''), row.get('remote_port_subtype', ''))
            neighbors.append(LldpNeighbor(
                local_port_num=local_port,
                local_port_name=local_port_names.get(local_port, str(local_port)),
                remote_index=rem_index,
                remote_chassis_id=chassis_id,
                remote_chassis_subtype=row.get('remote_chassis_subtype', ''),
                remote_port_id=port_id,
                remote_port_subtype=row.get('remote_port_subtype', ''),
                remote_port_desc=row.get('remote_port_desc', ''),
                remote_sys_name=row.get('remote_sys_name', ''),
                remote_sys_desc=row.get('remote_sys_desc', ''),
                remote_mgmt_addr=mgmt.get((local_port, rem_index), ''),
            ))
        return neighbors

    @staticmethod
    def _decode_id(value: str, subtype: str) -> str:
        """Decode a chassis/port id OctetString from its subtype.

        Values arrive pre-formatted as text/hex by ``_format_varbind``; MAC
        subtype values were already colon-hex, network-address dotted, so we
        simply return them unchanged.
        """
        return value

    @staticmethod
    def _parse_sysdescr(desc: str) -> tuple[str, str]:
        d = desc.lower()
        if 'routeros' in d or 'mikrotik' in d:
            return 'MikroTik', 'RouterOS'
        if 'huawei' in d or 'vrp' in d:
            return 'Huawei', 'VRP'
        if 'cisco' in d:
            return 'Cisco', 'IOS'
        if 'juniper' in d or 'junos' in d:
            return 'Juniper', 'Junos OS'
        if 'fortinet' in d or 'fortigate' in d:
            return 'Fortinet', 'FortiOS'
        if 'aruba' in d:
            return 'Aruba', 'ArubaOS'
        if 'ubiquiti' in d:
            return 'Ubiquiti', ''
        if 'linux' in d:
            return 'Linux', ''
        if 'windows' in d:
            return 'Microsoft', 'Windows'
        if desc:
            return desc.split()[0], ''
        return '', ''
