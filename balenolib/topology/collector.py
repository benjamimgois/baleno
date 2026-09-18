"""Layer 2 discovery — SNMP LLDP collection and adjacency parsing.

Implements the LLDP-MIB (``1.0.8802.1.1.2``) reader over ``pysnmp`` using the
same ``v3arch.asyncio`` backend the rest of Baleno already uses.  Produces a
:class:`~balenolib.topology.models.Device` populated with local identity, the
IF-MIB interface table and the decoded LLDP remote-neighbor table.

CDP (``1.3.6.1.4.1.9.9.23``) is intentionally left as a future extension
point — see :class:`LldpCollector` docstring for the seam.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from balenolib.topology.models import Device, DeviceRole, Interface, LldpNeighbor

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
OID_IF_IN_OCTETS = '1.3.6.1.2.1.2.2.1.10'
OID_IF_OUT_OCTETS = '1.3.6.1.2.1.2.2.1.16'
OID_IF_SPEED = '1.3.6.1.2.1.2.2.1.5'
OID_IF_HC_IN_OCTETS = '1.3.6.1.2.1.31.1.1.1.6'
OID_IF_HC_OUT_OCTETS = '1.3.6.1.2.1.31.1.1.1.10'
OID_IF_HIGH_SPEED = '1.3.6.1.2.1.31.1.1.1.15'

# Performance OIDs (Multivendor)
# Huawei (VRP)
OID_HUAWEI_CPU = '1.3.6.1.4.1.2011.5.25.31.1.1.1.1.5'        # hwEntityCpuUsage
OID_HUAWEI_CPU_DUTY = '1.3.6.1.4.1.2011.6.3.4.1.4'           # hwCpuDevDuty
OID_HUAWEI_MEM = '1.3.6.1.4.1.2011.5.25.31.1.1.1.1.7'        # hwEntityMemUsage
OID_HUAWEI_MEM_DUTY = '1.3.6.1.4.1.2011.6.3.5.1.1.2'         # hwMemDevDuty

# HP / HPE (Comware & ProCurve)
OID_HP_COMWARE_CPU = '1.3.6.1.4.1.25506.2.6.1.1.1.1.6'       # hh3cEntityExtCpuUsage
OID_HP_COMWARE_MEM = '1.3.6.1.4.1.25506.2.6.1.1.1.1.8'       # hh3cEntityExtMemUsage
OID_HP_PROCURVE_CPU = '1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0'   # hpSwitchCpuStat
OID_HP_PROCURVE_MEM_ALLOC = '1.3.6.1.4.1.11.2.14.11.5.1.1.2.2.1.1.7.1' # hpSwitchMemoryAlloc %
OID_HP_PROCURVE_MEM_USED = '1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.5.1'  # hpGlobalMemAllocBytes
OID_HP_PROCURVE_MEM_FREE = '1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.6.1'  # hpGlobalMemFreeBytes

# Aruba (AOS-S uses ProCurve; AOS-CX)
OID_ARUBA_CX_CPU = '1.3.6.1.4.1.47196.4.1.1.3.11.1.1.1.1'

# Cisco (CISCO-PROCESS-MIB & CISCO-MEMORY-POOL-MIB)
OID_CISCO_CPU_5MIN_REV = '1.3.6.1.4.1.9.9.109.1.1.1.1.8'
OID_CISCO_CPU_1MIN_REV = '1.3.6.1.4.1.9.9.109.1.1.1.1.7'
OID_CISCO_CPU_LEGACY = '1.3.6.1.4.1.9.2.1.58.0'              # avgBusy5
OID_CISCO_MEM_POOL_USED = '1.3.6.1.4.1.9.9.48.1.1.1.5'
OID_CISCO_MEM_POOL_FREE = '1.3.6.1.4.1.9.9.48.1.1.1.6'

# TP-Link (JetStream / Omada)
OID_TPLINK_CPU_5MIN = '1.3.6.1.4.1.11863.6.4.1.1.1.1.3'      # tpSysMonitorCpuUtilization (5m)
OID_TPLINK_CPU_1MIN = '1.3.6.1.4.1.11863.6.4.1.1.1.1.2'
OID_TPLINK_CPU_GENERIC = '1.3.6.1.4.1.11863.1.1.1'
OID_TPLINK_MEM = '1.3.6.1.4.1.11863.6.4.1.2.1.1.1'          # tpSysMonitorMemoryUtilization

# Juniper (Junos)
OID_JUNIPER_CPU = '1.3.6.1.4.1.2636.3.1.13.1.8'              # jnxOperatingCPU
OID_JUNIPER_MEM = '1.3.6.1.4.1.2636.3.1.13.1.11'             # jnxOperatingBuffer

# MikroTik (RouterOS)
OID_MIKROTIK_CPU = '1.3.6.1.4.1.14988.1.1.1.3.1.5'           # mtxrProcessorLoad

# Host Resources & Net-SNMP (RFC 2790 / Linux / Generic)
OID_HR_PROCESSOR_LOAD = '1.3.6.1.2.1.25.3.3.1.2'             # HOST-RESOURCES-MIB
OID_UCD_CPU_IDLE = '1.3.6.1.4.1.2021.11.11.0'                # ssCpuIdle
OID_UCD_MEM_TOTAL = '1.3.6.1.4.1.2021.4.5.0'                 # memTotalReal
OID_UCD_MEM_AVAIL = '1.3.6.1.4.1.2021.4.6.0'                 # memAvailReal
OID_HR_STORAGE_TYPE = '1.3.6.1.2.1.25.2.3.1.2'               # hrStorageType
OID_HR_STORAGE_SIZE = '1.3.6.1.2.1.25.2.3.1.5'               # hrStorageSize
OID_HR_STORAGE_USED = '1.3.6.1.2.1.25.2.3.1.6'               # hrStorageUsed

# Multivendor candidate probe catalogs (in priority order: Huawei, HP, Aruba, Cisco, TP-Link, Juniper, MikroTik, Linux)
CPU_PROBES = [
    # (id, vendor_tag, probe_type, oid_or_oids)
    ('huawei_entity', 'huawei', 'walk_avg', OID_HUAWEI_CPU),
    ('huawei_duty', 'huawei', 'walk_avg', OID_HUAWEI_CPU_DUTY),
    ('hp_comware', 'hp', 'walk_avg', OID_HP_COMWARE_CPU),
    ('hp_procurve', 'hp', 'get_scalar', OID_HP_PROCURVE_CPU),
    ('aruba_cx', 'aruba', 'walk_avg', OID_ARUBA_CX_CPU),
    ('cisco_cpm_5m', 'cisco', 'walk_avg', OID_CISCO_CPU_5MIN_REV),
    ('cisco_cpm_1m', 'cisco', 'walk_avg', OID_CISCO_CPU_1MIN_REV),
    ('cisco_legacy', 'cisco', 'get_scalar', OID_CISCO_CPU_LEGACY),
    ('tplink_5m', 'tplink', 'walk_avg', OID_TPLINK_CPU_5MIN),
    ('tplink_1m', 'tplink', 'walk_avg', OID_TPLINK_CPU_1MIN),
    ('tplink_gen', 'tplink', 'get_scalar', OID_TPLINK_CPU_GENERIC),
    ('juniper_jnx', 'juniper', 'walk_avg', OID_JUNIPER_CPU),
    ('mikrotik_mtxr', 'mikrotik', 'walk_avg', OID_MIKROTIK_CPU),
    ('linux_hr', 'linux', 'walk_avg', OID_HR_PROCESSOR_LOAD),
    ('linux_ucd', 'linux', 'get_idle', OID_UCD_CPU_IDLE),
]

MEM_PROBES = [
    # (id, vendor_tag, probe_type, oid_or_oids)
    ('huawei_entity', 'huawei', 'walk_avg', OID_HUAWEI_MEM),
    ('huawei_duty', 'huawei', 'walk_avg', OID_HUAWEI_MEM_DUTY),
    ('hp_comware', 'hp', 'walk_avg', OID_HP_COMWARE_MEM),
    ('hp_procurve_alloc', 'hp', 'get_scalar', OID_HP_PROCURVE_MEM_ALLOC),
    ('hp_procurve_bytes', 'hp', 'get_used_free', (OID_HP_PROCURVE_MEM_USED, OID_HP_PROCURVE_MEM_FREE)),
    ('cisco_pool', 'cisco', 'walk_used_free', (OID_CISCO_MEM_POOL_USED, OID_CISCO_MEM_POOL_FREE)),
    ('tplink_mem', 'tplink', 'walk_avg', OID_TPLINK_MEM),
    ('juniper_jnx', 'juniper', 'walk_avg', OID_JUNIPER_MEM),
    ('mikrotik_ram', 'mikrotik', 'walk_hr_ram', None),
    ('linux_ucd', 'linux', 'get_ucd_mem', (OID_UCD_MEM_TOTAL, OID_UCD_MEM_AVAIL)),
    ('linux_hr', 'linux', 'walk_hr_ram', None),
]


def _order_probes(probes: list[tuple], vendor: str) -> list[tuple]:
    if not vendor:
        return list(probes)
    v = vendor.lower().replace('-', '').replace(' ', '')
    matching = []
    others = []
    for p in probes:
        tag = p[1]
        if tag in v or v in tag:
            matching.append(p)
        else:
            others.append(p)
    return matching + others

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

    # ── reusable session helpers (live monitoring) ─────────────────────────

    async def open_session(self, host: str):
        """Create a reusable ``(engine, auth, target)`` session for ``host``.

        The engine and transport are meant to live for many poll cycles (the
        intended long-lived usage of the ``v3arch.asyncio`` backend); call
        :meth:`close_session` once when done.
        """
        from pysnmp.hlapi.v3arch.asyncio import SnmpEngine, UdpTransportTarget
        engine = SnmpEngine()
        target = await UdpTransportTarget.create(
            (host, self.port), timeout=self.timeout, retries=self.retries)
        auth = self._auth_data()
        return engine, auth, target

    @staticmethod
    def close_session(engine) -> None:
        try:
            engine.close_dispatcher()
        except Exception:
            pass

    async def probe(self, engine, auth, target) -> bool:
        """Return True if the host answers SNMP (single cheap GET)."""
        try:
            return await self._get(engine, auth, target, OID_LOC_CHASSIS_ID) is not None
        except Exception:
            return False

    async def poll_counters_async(self, engine, auth, target) -> dict[int, list[int]]:
        """Return ``{ifIndex: [in_octets, out_octets]}`` (64-bit HC preferred).

        Reads only the octet counters — no CPU/memory walks — so it is cheap
        enough to run on the fast traffic cadence.
        """
        return await self._read_counters(engine, auth, target)

    async def poll_cpu_mem_async(self, engine, auth, target, vendor: str = '',
                                 cache: Optional[dict] = None) -> tuple:
        """Return ``(cpu_percent, memory_percent, updated_cache)``."""
        return await self._read_cpu_mem(engine, auth, target, vendor=vendor, cache=cache)

    async def poll_status_async(self, engine, auth, target) -> dict[int, str]:
        """Return ``{ifIndex: 'up'|'down'|'unknown'}`` using a live session.

        Lighter than :meth:`collect` — walks a single column so the live
        topology monitor can re-check port state on a longer cadence.
        """
        statuses: dict[int, str] = {}
        for oid, val in await self._walk(engine, auth, target, OID_IF_OPER_STATUS):
            try:
                idx = int(_oid_suffix(oid, OID_IF_OPER_STATUS)[-1])
            except (IndexError, ValueError):
                continue
            statuses[idx] = ('up' if val == '1'
                             else 'down' if val == '2' else 'unknown')
        return statuses

    async def poll_speed_async(self, engine, auth, target) -> dict[int, float]:
        """Return ``{ifIndex: Mbps}`` using a live session.

        Prefers ifHighSpeed (Mbps); falls back to ifSpeed (bps / 1e6) when the
        high-speed column is absent (older agents without ifXTable).
        """
        speeds: dict[int, float] = {}
        rows = await self._walk(engine, auth, target, OID_IF_HIGH_SPEED)
        base = OID_IF_HIGH_SPEED
        if not rows:
            rows = await self._walk(engine, auth, target, OID_IF_SPEED)
            base = OID_IF_SPEED
        for oid, val in rows:
            try:
                idx = int(_oid_suffix(oid, base)[-1])
            except (IndexError, ValueError):
                continue
            try:
                speed = float(val)
            except ValueError:
                continue
            if base == OID_IF_HIGH_SPEED:
                speeds[idx] = speed
            elif speed < 2 ** 31:
                # ifSpeed is a 32-bit counter; anything near/above 2^31 is a
                # wrapped (or sentinel) value from a >1G link — untrustworthy.
                speeds[idx] = speed / 1e6
        return speeds

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
                engine, auth, target, device)

            # CPU / memory (best-effort)
            await self._fill_perf(engine, auth, target, device)

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
        try:
            err_ind, err_stat, _, var_binds = await get_cmd(
                engine, auth, target, ContextData(),
                ObjectType(ObjectIdentity(oid)))
            if err_ind or err_stat or not var_binds:
                return None
            return _format_varbind(var_binds[0][1])
        except Exception:
            return None

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

        for oid, val in descrs:
            try:
                idx = int(_oid_suffix(oid, OID_IF_DESCR)[-1])
            except (IndexError, ValueError):
                continue
            if idx not in device.interfaces:
                device.interfaces[idx] = Interface(index=idx, name=val, descr=val)
            else:
                device.interfaces[idx].descr = val

        for oid, val in aliases:
            try:
                idx = int(_oid_suffix(oid, OID_IF_ALIAS)[-1])
            except (IndexError, ValueError):
                continue
            if idx in device.interfaces:
                device.interfaces[idx].alias = val
        for oid, val in statuses:
            try:
                idx = int(_oid_suffix(oid, OID_IF_OPER_STATUS)[-1])
            except (IndexError, ValueError):
                continue
            if idx in device.interfaces:
                device.interfaces[idx].oper_status = (
                    'up' if val == '1' else 'down' if val == '2' else 'unknown')

        await self._fill_if_stats(engine, auth, target, device)

    async def _fill_if_stats(self, engine, auth, target, device: Device) -> None:
        """Populate interface counters (64-bit HC, 32-bit fallback) and speed."""
        counters = await self._read_counters(engine, auth, target)
        for idx, (in_oct, out_oct) in counters.items():
            iface = device.interfaces.get(idx)
            if iface is not None:
                iface.in_octets = in_oct
                iface.out_octets = out_oct

        high_speed = await self._walk(engine, auth, target, OID_IF_HIGH_SPEED)
        for oid, val in high_speed:
            try:
                idx = int(_oid_suffix(oid, OID_IF_HIGH_SPEED)[-1])
                mbps = float(val)
            except (IndexError, ValueError):
                continue
            if idx in device.interfaces:
                device.interfaces[idx].speed_mbps = mbps

    async def _read_counters(self, engine, auth, target) -> dict[int, list[int]]:
        """Return ``{ifIndex: [in_octets, out_octets]}`` (64-bit HC preferred)."""
        hc_in = await self._walk(engine, auth, target, OID_IF_HC_IN_OCTETS)
        base_in = OID_IF_HC_IN_OCTETS
        if not hc_in:
            hc_in = await self._walk(engine, auth, target, OID_IF_IN_OCTETS)
            base_in = OID_IF_IN_OCTETS
        hc_out = await self._walk(engine, auth, target, OID_IF_HC_OUT_OCTETS)
        base_out = OID_IF_HC_OUT_OCTETS
        if not hc_out:
            hc_out = await self._walk(engine, auth, target, OID_IF_OUT_OCTETS)
            base_out = OID_IF_OUT_OCTETS

        counters: dict[int, list[int]] = {}
        for oid, val in hc_in:
            try:
                idx = int(_oid_suffix(oid, base_in)[-1])
                counters.setdefault(idx, [0, 0])[0] = int(val)
            except (IndexError, ValueError):
                continue
        for oid, val in hc_out:
            try:
                idx = int(_oid_suffix(oid, base_out)[-1])
                counters.setdefault(idx, [0, 0])[1] = int(val)
            except (IndexError, ValueError):
                continue
        return counters

    async def _probe_cpu_one(self, engine, auth, target, probe_type: str, oid_or_oids: Any) -> Optional[float]:
        if probe_type == 'walk_avg':
            rows = await self._walk(engine, auth, target, oid_or_oids)
            if not rows:
                return None
            vals: list[float] = []
            for _, v in rows:
                try:
                    fv = float(str(v).strip().rstrip('%'))
                    if 0.0 <= fv <= 100.0:
                        vals.append(fv)
                except (ValueError, AttributeError):
                    continue
            if vals:
                pos = [x for x in vals if x > 0]
                return round(sum(pos) / len(pos), 1) if pos else 0.0
            return None
        elif probe_type == 'get_scalar':
            res = await self._get(engine, auth, target, oid_or_oids)
            if res is not None:
                try:
                    fv = float(str(res).strip().rstrip('%'))
                    if 0.0 <= fv <= 100.0:
                        return round(fv, 1)
                except (ValueError, AttributeError):
                    pass
            return None
        elif probe_type == 'get_idle':
            res = await self._get(engine, auth, target, oid_or_oids)
            if res is not None:
                try:
                    fv = float(str(res).strip().rstrip('%'))
                    if 0.0 <= fv <= 100.0:
                        return round(100.0 - fv, 1)
                except (ValueError, AttributeError):
                    pass
            return None
        return None

    async def _probe_mem_one(self, engine, auth, target, probe_type: str, oid_or_oids: Any) -> Optional[float]:
        if probe_type == 'walk_avg':
            rows = await self._walk(engine, auth, target, oid_or_oids)
            if not rows:
                return None
            vals: list[float] = []
            for _, v in rows:
                try:
                    fv = float(str(v).strip().rstrip('%'))
                    if 0.0 <= fv <= 100.0:
                        vals.append(fv)
                except (ValueError, AttributeError):
                    continue
            if vals:
                pos = [x for x in vals if x > 0]
                return round(sum(pos) / len(pos), 1) if pos else 0.0
            return None
        elif probe_type == 'get_scalar':
            res = await self._get(engine, auth, target, oid_or_oids)
            if res is not None:
                try:
                    fv = float(str(res).strip().rstrip('%'))
                    if 0.0 <= fv <= 100.0:
                        return round(fv, 1)
                except (ValueError, AttributeError):
                    pass
            return None
        elif probe_type == 'get_used_free':
            used_oid, free_oid = oid_or_oids
            used_s = await self._get(engine, auth, target, used_oid)
            free_s = await self._get(engine, auth, target, free_oid)
            if used_s is not None and free_s is not None:
                try:
                    used = float(used_s)
                    free = float(free_s)
                    if used + free > 0:
                        return round(used / (used + free) * 100.0, 1)
                except (ValueError, AttributeError):
                    pass
            return None
        elif probe_type == 'walk_used_free':
            used_oid, free_oid = oid_or_oids
            used_rows = await self._walk(engine, auth, target, used_oid)
            free_rows = await self._walk(engine, auth, target, free_oid)
            if used_rows and free_rows:
                try:
                    used = sum(float(v) for _, v in used_rows)
                    free = sum(float(v) for _, v in free_rows)
                    if used + free > 0:
                        return round(used / (used + free) * 100.0, 1)
                except (ValueError, AttributeError):
                    pass
            return None
        elif probe_type == 'get_ucd_mem':
            total_oid, avail_oid = oid_or_oids
            tot_s = await self._get(engine, auth, target, total_oid)
            av_s = await self._get(engine, auth, target, avail_oid)
            if tot_s is not None and av_s is not None:
                try:
                    tot = float(tot_s)
                    av = float(av_s)
                    if tot > 0:
                        return round(max(0.0, (tot - av) / tot * 100.0), 1)
                except (ValueError, AttributeError):
                    pass
            return None
        elif probe_type == 'walk_hr_ram':
            types = await self._walk(engine, auth, target, OID_HR_STORAGE_TYPE)
            sizes = await self._walk(engine, auth, target, OID_HR_STORAGE_SIZE)
            useds = await self._walk(engine, auth, target, OID_HR_STORAGE_USED)

            size_map: dict[str, float] = {}
            for o, v in sizes:
                sfx = _oid_suffix(o, OID_HR_STORAGE_SIZE)
                if sfx:
                    try:
                        size_map[sfx[-1]] = float(v)
                    except ValueError:
                        pass
            used_map: dict[str, float] = {}
            for o, v in useds:
                sfx = _oid_suffix(o, OID_HR_STORAGE_USED)
                if sfx:
                    try:
                        used_map[sfx[-1]] = float(v)
                    except ValueError:
                        pass

            ram_idx = None
            for o, v in types:
                if v.endswith('.2') or '25.2.1.2' in v or v == OID_HR_STORAGE_RAM:
                    sfx = _oid_suffix(o, OID_HR_STORAGE_TYPE)
                    if sfx and sfx[-1] in size_map and size_map[sfx[-1]] > 0:
                        ram_idx = sfx[-1]
                        break
            if not ram_idx:
                if '65536' in size_map and size_map['65536'] > 0:
                    ram_idx = '65536'
                elif size_map:
                    ram_idx = max(size_map.keys(), key=lambda k: size_map[k])

            if ram_idx and ram_idx in size_map and ram_idx in used_map:
                tot = size_map[ram_idx]
                usd = used_map[ram_idx]
                if tot > 0:
                    return round(min(100.0, max(0.0, usd / tot * 100.0)), 1)
            return None
        return None

    async def _read_cpu_mem(self, engine, auth, target, vendor: str = '',
                            cache: Optional[dict] = None) -> tuple:
        """Return ``(cpu_percent, memory_percent, updated_cache)``."""
        cpu: Optional[float] = None
        mem: Optional[float] = None
        new_cache = dict(cache) if cache else {}
        fails = new_cache.get('fails', 0)

        # 1. Try cached probes if available and fails < 2
        cached_cpu_id = new_cache.get('cpu_id')
        cached_mem_id = new_cache.get('mem_id')
        cpu_probe = next((p for p in CPU_PROBES if p[0] == cached_cpu_id), None) if cached_cpu_id else None
        mem_probe = next((p for p in MEM_PROBES if p[0] == cached_mem_id), None) if cached_mem_id else None

        if cpu_probe is not None:
            cpu = await self._probe_cpu_one(engine, auth, target, cpu_probe[2], cpu_probe[3])
        if mem_probe is not None:
            mem = await self._probe_mem_one(engine, auth, target, mem_probe[2], mem_probe[3])

        if cpu is not None or mem is not None:
            new_cache['fails'] = 0
            return cpu, mem, new_cache

        # If cache had entries but both failed, increment fail count
        if cached_cpu_id or cached_mem_id:
            fails += 1
            new_cache['fails'] = fails
            if fails < 2:
                return None, None, new_cache
            # Invalidate cache after 2 consecutive failures
            new_cache = {'fails': 0}

        # 2. Cascaded discovery: sort by vendor hint then priority order
        ordered_cpu = _order_probes(CPU_PROBES, vendor)
        for p_id, tag, p_type, oid in ordered_cpu:
            cpu = await self._probe_cpu_one(engine, auth, target, p_type, oid)
            if cpu is not None:
                new_cache['cpu_id'] = p_id
                break

        ordered_mem = _order_probes(MEM_PROBES, vendor)
        for p_id, tag, p_type, oid in ordered_mem:
            mem = await self._probe_mem_one(engine, auth, target, p_type, oid)
            if mem is not None:
                new_cache['mem_id'] = p_id
                break

        if cpu is not None or mem is not None:
            new_cache['fails'] = 0
        return cpu, mem, new_cache

    async def _fill_perf(self, engine, auth, target, device: Device) -> None:
        res = await self._read_cpu_mem(engine, auth, target, vendor=device.vendor)
        cpu = res[0]
        mem = res[1]
        if cpu is not None:
            device.cpu_usage = round(cpu, 1)
        if mem is not None:
            device.memory_usage = mem

    async def _collect_neighbors(self, engine, auth, target,
                                  device: Optional[Device] = None) -> list[LldpNeighbor]:
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

        # Local port desc (lldpLocPortDesc) fallback
        local_port_descs: dict[int, str] = {}
        for full_oid, val in await self._walk(engine, auth, target, OID_LOC_PORT_DESC):
            suffix = _oid_suffix(full_oid, OID_LOC_PORT_DESC)
            if not suffix:
                continue
            try:
                local_port_descs[int(suffix[-1])] = val
            except ValueError:
                continue

        # Extract sorted physical interfaces from device if available
        phys_interfaces: list[Interface] = []
        if device is not None and device.interfaces:
            for idx in sorted(device.interfaces.keys()):
                iface = device.interfaces[idx]
                name = iface.name or iface.descr or ''
                lower_name = name.lower()
                if any(v in lower_name for v in ('vlan', 'loopback', 'inloop', 'null', 'console', 'meth', 'eth-trunk', 'port-channel', 'bundle')):
                    continue
                phys_interfaces.append(iface)

        def _resolve_local_port(port_num: int) -> str:
            # 1. Non-numeric lldpLocPortId
            loc_id = local_port_names.get(port_num)
            if loc_id and not loc_id.isdigit():
                return loc_id

            # 2. Check 1-based physical chassis port ordinal (e.g. port 35 in a 36-port switch)
            if 1 <= port_num <= len(phys_interfaces):
                p_iface = phys_interfaces[port_num - 1]
                if p_iface.name:
                    return p_iface.name

            # 3. Check lldpLocPortDesc
            desc = local_port_descs.get(port_num)
            if desc and not desc.isdigit():
                return desc

            # 4. Check if port_num matches an ifIndex in device.interfaces
            if device is not None and port_num in device.interfaces:
                iface = device.interfaces[port_num]
                if iface.name and not iface.name.isdigit():
                    return iface.name
                if iface.descr and not iface.descr.isdigit():
                    return iface.descr

            # 5. Return loc_id if present or string representation
            return loc_id or str(port_num)

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
            resolved_port_name = _resolve_local_port(local_port)
            neighbors.append(LldpNeighbor(
                local_port_num=local_port,
                local_port_name=resolved_port_name,
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
        if 'hpe' in d or 'procurve' in d:
            return 'HP', 'ProCurve'
        if 'comware' in d or 'h3c' in d:
            return 'HP', 'Comware'
        if 'hp ' in d or 'hp switch' in d or 'hewlett' in d:
            return 'HP', ''
        if 'tp-link' in d or 'tplink' in d or 'jetstream' in d or 'omada' in d:
            return 'TP-Link', 'JetStream'
        if 'ubiquiti' in d:
            return 'Ubiquiti', ''
        if 'linux' in d:
            return 'Linux', ''
        if 'windows' in d:
            return 'Microsoft', 'Windows'
        if desc:
            return desc.split()[0], ''
        return '', ''
