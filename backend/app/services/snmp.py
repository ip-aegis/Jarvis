"""
SNMP Service for network device polling.
Supports SNMP v2c and v3 for Cisco switches and other network devices.
Uses pysnmp async API.
"""
from dataclasses import dataclass
from typing import Any, Optional

from pysnmp.hlapi.asyncio import (
    CommunityData,
    ContextData,
    ObjectIdentity,
    ObjectType,
    SnmpEngine,
    UdpTransportTarget,
    UsmUserData,
    usmAesCfb128Protocol,
    usmDESPrivProtocol,
    usmHMACMD5AuthProtocol,
    usmHMACSHAAuthProtocol,
)

# Handle different pysnmp versions (pysnmp vs pysnmp-lextudio)
try:
    from pysnmp.hlapi.asyncio import bulkWalkCmd as bulk_walk_cmd
    from pysnmp.hlapi.asyncio import getCmd as get_cmd
    from pysnmp.hlapi.asyncio import walkCmd as walk_cmd
except ImportError:
    from pysnmp.hlapi.asyncio import bulk_walk_cmd, get_cmd, walk_cmd

from app.core.logging import get_logger

logger = get_logger(__name__)


# Standard SNMP OIDs
class OIDs:
    """Common SNMP OIDs for network device monitoring."""

    # System MIB (RFC 1213)
    SYS_DESCR = "1.3.6.1.2.1.1.1.0"
    SYS_OBJECT_ID = "1.3.6.1.2.1.1.2.0"
    SYS_UPTIME = "1.3.6.1.2.1.1.3.0"
    SYS_CONTACT = "1.3.6.1.2.1.1.4.0"
    SYS_NAME = "1.3.6.1.2.1.1.5.0"
    SYS_LOCATION = "1.3.6.1.2.1.1.6.0"

    # Interfaces MIB (IF-MIB)
    IF_NUMBER = "1.3.6.1.2.1.2.1.0"
    IF_TABLE = "1.3.6.1.2.1.2.2"
    IF_INDEX = "1.3.6.1.2.1.2.2.1.1"
    IF_DESCR = "1.3.6.1.2.1.2.2.1.2"
    IF_TYPE = "1.3.6.1.2.1.2.2.1.3"
    IF_MTU = "1.3.6.1.2.1.2.2.1.4"
    IF_SPEED = "1.3.6.1.2.1.2.2.1.5"
    IF_PHYS_ADDRESS = "1.3.6.1.2.1.2.2.1.6"
    IF_ADMIN_STATUS = "1.3.6.1.2.1.2.2.1.7"
    IF_OPER_STATUS = "1.3.6.1.2.1.2.2.1.8"
    IF_IN_OCTETS = "1.3.6.1.2.1.2.2.1.10"
    IF_IN_ERRORS = "1.3.6.1.2.1.2.2.1.14"
    IF_OUT_OCTETS = "1.3.6.1.2.1.2.2.1.16"
    IF_OUT_ERRORS = "1.3.6.1.2.1.2.2.1.20"

    # 64-bit counters (IF-MIB)
    IF_HC_IN_OCTETS = "1.3.6.1.2.1.31.1.1.1.6"
    IF_HC_OUT_OCTETS = "1.3.6.1.2.1.31.1.1.1.10"
    IF_NAME = "1.3.6.1.2.1.31.1.1.1.1"
    IF_ALIAS = "1.3.6.1.2.1.31.1.1.1.18"

    # Entity MIB (ENTITY-MIB) - for device info
    ENT_PHYSICAL_DESCR = "1.3.6.1.2.1.47.1.1.1.1.2"
    ENT_PHYSICAL_NAME = "1.3.6.1.2.1.47.1.1.1.1.7"
    ENT_PHYSICAL_SERIAL = "1.3.6.1.2.1.47.1.1.1.1.11"
    ENT_PHYSICAL_MODEL = "1.3.6.1.2.1.47.1.1.1.1.13"

    # Cisco-specific OIDs
    CISCO_CPU_5SEC = "1.3.6.1.4.1.9.2.1.56.0"
    CISCO_CPU_1MIN = "1.3.6.1.4.1.9.2.1.57.0"
    CISCO_CPU_5MIN = "1.3.6.1.4.1.9.2.1.58.0"
    CISCO_MEMORY_POOL_USED = "1.3.6.1.4.1.9.9.48.1.1.1.5"
    CISCO_MEMORY_POOL_FREE = "1.3.6.1.4.1.9.9.48.1.1.1.6"
    CISCO_TEMP_VALUE = "1.3.6.1.4.1.9.9.13.1.3.1.3"
    CISCO_POE_PORT_POWER = "1.3.6.1.4.1.9.9.402.1.2.1.7"

    # VLAN info
    CISCO_VLAN_STATE = "1.3.6.1.4.1.9.9.46.1.3.1.1.2"
    CISCO_VLAN_NAME = "1.3.6.1.4.1.9.9.46.1.3.1.1.4"

    # Bridge MIB for MAC table
    DOT1D_TP_FDB_ADDRESS = "1.3.6.1.2.1.17.4.3.1.1"
    DOT1D_TP_FDB_PORT = "1.3.6.1.2.1.17.4.3.1.2"

    # Vendor OID prefixes for identification
    VENDOR_PREFIXES = {
        "1.3.6.1.4.1.9": "cisco",
        "1.3.6.1.4.1.11": "hp",
        "1.3.6.1.4.1.2636": "juniper",
        "1.3.6.1.4.1.41112": "ubiquiti",
        "1.3.6.1.4.1.14988": "mikrotik",
        "1.3.6.1.4.1.6486": "alcatel",
        "1.3.6.1.4.1.171": "dlink",
        "1.3.6.1.4.1.1991": "brocade",
    }


@dataclass
class SNMPCredentials:
    """SNMP credentials for device access."""

    version: str = "2c"  # "2c" or "3"
    community: str = "public"  # For v2c
    # For v3
    username: Optional[str] = None
    auth_protocol: Optional[str] = None  # MD5, SHA
    auth_password: Optional[str] = None
    priv_protocol: Optional[str] = None  # DES, AES
    priv_password: Optional[str] = None


class SNMPService:
    """Service for SNMP operations on network devices."""

    def __init__(self, timeout: int = 5, retries: int = 2):
        self.timeout = timeout
        self.retries = retries

    def _get_auth_data(self, credentials: SNMPCredentials):
        """Get appropriate authentication data based on SNMP version."""
        if credentials.version == "2c":
            return CommunityData(credentials.community)
        else:
            # SNMPv3
            auth_proto = None
            priv_proto = None

            if credentials.auth_protocol:
                if credentials.auth_protocol.upper() == "MD5":
                    auth_proto = usmHMACMD5AuthProtocol
                elif credentials.auth_protocol.upper() == "SHA":
                    auth_proto = usmHMACSHAAuthProtocol

            if credentials.priv_protocol:
                if credentials.priv_protocol.upper() == "DES":
                    priv_proto = usmDESPrivProtocol
                elif credentials.priv_protocol.upper() == "AES":
                    priv_proto = usmAesCfb128Protocol

            return UsmUserData(
                credentials.username,
                credentials.auth_password,
                credentials.priv_password,
                authProtocol=auth_proto,
                privProtocol=priv_proto,
            )

    def _get_transport(self, host: str, port: int):
        """Get UDP transport target."""
        return UdpTransportTarget(
            (host, port),
            timeout=self.timeout,
            retries=self.retries,
        )

    async def get(
        self,
        host: str,
        oids: list[str],
        credentials: SNMPCredentials,
        port: int = 161,
    ) -> dict[str, Any]:
        """
        Perform SNMP GET for one or more OIDs.
        Returns a dict mapping OID to value.
        """
        engine = SnmpEngine()
        auth_data = self._get_auth_data(credentials)
        transport = self._get_transport(host, port)

        object_types = [ObjectType(ObjectIdentity(oid)) for oid in oids]

        error_indication, error_status, error_index, var_binds = await get_cmd(
            engine,
            auth_data,
            transport,
            ContextData(),
            *object_types,
        )

        results = {}
        if error_indication:
            logger.warning(
                "snmp_get_error",
                host=host,
                error=str(error_indication),
            )
            return results

        if error_status:
            logger.warning(
                "snmp_get_status_error",
                host=host,
                error=error_status.prettyPrint(),
                index=error_index,
            )
            return results

        for var_bind in var_binds:
            oid = str(var_bind[0])
            value = var_bind[1]
            if hasattr(value, "prettyPrint"):
                results[oid] = self._convert_value(value)
            else:
                results[oid] = value

        return results

    async def walk(
        self,
        host: str,
        oid: str,
        credentials: SNMPCredentials,
        port: int = 161,
        max_rows: int = 1000,
    ) -> list[tuple[str, Any]]:
        """
        Perform SNMP WALK on an OID subtree.
        Returns a list of (oid, value) tuples.
        """
        engine = SnmpEngine()
        auth_data = self._get_auth_data(credentials)
        transport = self._get_transport(host, port)

        results = []
        row_count = 0

        async for error_indication, error_status, error_index, var_binds in walk_cmd(
            engine,
            auth_data,
            transport,
            ContextData(),
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                logger.warning(
                    "snmp_walk_error",
                    host=host,
                    oid=oid,
                    error=str(error_indication),
                )
                break

            if error_status:
                logger.warning(
                    "snmp_walk_status_error",
                    host=host,
                    oid=oid,
                    error=error_status.prettyPrint(),
                )
                break

            for var_bind in var_binds:
                results.append((str(var_bind[0]), self._convert_value(var_bind[1])))

            row_count += 1
            if row_count >= max_rows:
                break

        return results

    async def bulk_get(
        self,
        host: str,
        oid: str,
        credentials: SNMPCredentials,
        port: int = 161,
        max_repetitions: int = 25,
    ) -> list[tuple[str, Any]]:
        """
        Perform SNMP GETBULK for efficient table retrieval.
        Returns a list of (oid, value) tuples.
        """
        engine = SnmpEngine()
        auth_data = self._get_auth_data(credentials)
        transport = self._get_transport(host, port)

        results = []

        async for error_indication, error_status, error_index, var_binds in bulk_walk_cmd(
            engine,
            auth_data,
            transport,
            ContextData(),
            0,  # nonRepeaters
            max_repetitions,
            ObjectType(ObjectIdentity(oid)),
            lexicographicMode=False,
        ):
            if error_indication:
                logger.warning(
                    "snmp_bulk_error",
                    host=host,
                    oid=oid,
                    error=str(error_indication),
                )
                break

            if error_status:
                break

            for var_bind in var_binds:
                results.append((str(var_bind[0]), self._convert_value(var_bind[1])))

        return results

    def _convert_value(self, value) -> Any:
        """Convert SNMP value to Python native type."""
        type_name = value.__class__.__name__

        if type_name in ("Integer", "Integer32", "Gauge32", "Counter32", "Counter64", "Unsigned32"):
            return int(value)
        elif type_name == "OctetString":
            # Try to decode as UTF-8, fall back to hex representation
            try:
                return value.prettyPrint()
            except Exception:
                return value.hexValue if hasattr(value, "hexValue") else str(value)
        elif type_name == "IpAddress":
            return value.prettyPrint()
        elif type_name == "TimeTicks":
            return int(value) / 100  # Convert to seconds
        elif type_name == "ObjectIdentifier":
            return str(value)
        else:
            return value.prettyPrint() if hasattr(value, "prettyPrint") else str(value)

    async def get_system_info(
        self,
        host: str,
        credentials: SNMPCredentials,
        port: int = 161,
    ) -> dict[str, Any]:
        """Get basic system information from a device."""
        oids = [
            OIDs.SYS_DESCR,
            OIDs.SYS_OBJECT_ID,
            OIDs.SYS_UPTIME,
            OIDs.SYS_NAME,
            OIDs.SYS_LOCATION,
            OIDs.SYS_CONTACT,
        ]

        results = await self.get(host, oids, credentials, port)

        # Identify vendor from sysObjectID
        vendor = "unknown"
        sys_oid = results.get(OIDs.SYS_OBJECT_ID, "")
        for prefix, vendor_name in OIDs.VENDOR_PREFIXES.items():
            if sys_oid.startswith(prefix):
                vendor = vendor_name
                break

        return {
            "description": results.get(OIDs.SYS_DESCR, ""),
            "object_id": sys_oid,
            "uptime_seconds": results.get(OIDs.SYS_UPTIME, 0),
            "name": results.get(OIDs.SYS_NAME, ""),
            "location": results.get(OIDs.SYS_LOCATION, ""),
            "contact": results.get(OIDs.SYS_CONTACT, ""),
            "vendor": vendor,
        }

    async def get_interfaces(
        self,
        host: str,
        credentials: SNMPCredentials,
        port: int = 161,
    ) -> list[dict[str, Any]]:
        """Get interface information from a device."""
        # Get interface descriptions
        descr_results = await self.walk(host, OIDs.IF_DESCR, credentials, port)

        # Get operational status
        oper_results = await self.walk(host, OIDs.IF_OPER_STATUS, credentials, port)

        # Get admin status
        admin_results = await self.walk(host, OIDs.IF_ADMIN_STATUS, credentials, port)

        # Get speeds
        speed_results = await self.walk(host, OIDs.IF_SPEED, credentials, port)

        # Build index-based lookups
        def extract_index(oid_str: str) -> str:
            return oid_str.split(".")[-1]

        oper_map = {extract_index(o): v for o, v in oper_results}
        admin_map = {extract_index(o): v for o, v in admin_results}
        speed_map = {extract_index(o): v for o, v in speed_results}

        interfaces = []
        for oid, descr in descr_results:
            idx = extract_index(oid)
            oper_status = oper_map.get(idx, 0)
            admin_status = admin_map.get(idx, 0)
            speed = speed_map.get(idx, 0)

            interfaces.append(
                {
                    "index": int(idx),
                    "description": descr,
                    "oper_status": "up" if oper_status == 1 else "down",
                    "admin_status": "enabled" if admin_status == 1 else "disabled",
                    "speed_bps": speed,
                    "speed_formatted": self._format_speed(speed),
                }
            )

        return interfaces

    async def get_interface_traffic(
        self,
        host: str,
        credentials: SNMPCredentials,
        port: int = 161,
        use_64bit: bool = True,
    ) -> dict[int, dict[str, int]]:
        """
        Get interface traffic counters.
        Returns dict mapping interface index to in/out octets.
        """
        if use_64bit:
            in_oid = OIDs.IF_HC_IN_OCTETS
            out_oid = OIDs.IF_HC_OUT_OCTETS
        else:
            in_oid = OIDs.IF_IN_OCTETS
            out_oid = OIDs.IF_OUT_OCTETS

        in_results = await self.walk(host, in_oid, credentials, port)
        out_results = await self.walk(host, out_oid, credentials, port)

        def extract_index(oid_str: str) -> int:
            return int(oid_str.split(".")[-1])

        traffic = {}
        for oid, value in in_results:
            idx = extract_index(oid)
            if idx not in traffic:
                traffic[idx] = {}
            traffic[idx]["in_octets"] = value

        for oid, value in out_results:
            idx = extract_index(oid)
            if idx not in traffic:
                traffic[idx] = {}
            traffic[idx]["out_octets"] = value

        return traffic

    async def get_cisco_cpu_memory(
        self,
        host: str,
        credentials: SNMPCredentials,
        port: int = 161,
    ) -> dict[str, Any]:
        """Get CPU and memory usage from Cisco devices."""
        oids = [
            OIDs.CISCO_CPU_5SEC,
            OIDs.CISCO_CPU_1MIN,
            OIDs.CISCO_CPU_5MIN,
        ]

        results = await self.get(host, oids, credentials, port)

        # Get memory pool info
        mem_used = await self.walk(host, OIDs.CISCO_MEMORY_POOL_USED, credentials, port)
        mem_free = await self.walk(host, OIDs.CISCO_MEMORY_POOL_FREE, credentials, port)

        total_used = sum(v for _, v in mem_used) if mem_used else 0
        total_free = sum(v for _, v in mem_free) if mem_free else 0
        total_mem = total_used + total_free

        return {
            "cpu_5sec": results.get(OIDs.CISCO_CPU_5SEC, 0),
            "cpu_1min": results.get(OIDs.CISCO_CPU_1MIN, 0),
            "cpu_5min": results.get(OIDs.CISCO_CPU_5MIN, 0),
            "memory_used": total_used,
            "memory_free": total_free,
            "memory_total": total_mem,
            "memory_percent": round(total_used / total_mem * 100, 1) if total_mem > 0 else 0,
        }

    async def get_cisco_temperature(
        self,
        host: str,
        credentials: SNMPCredentials,
        port: int = 161,
    ) -> list[dict[str, Any]]:
        """Get temperature readings from Cisco devices."""
        temp_results = await self.walk(host, OIDs.CISCO_TEMP_VALUE, credentials, port)

        temperatures = []
        for oid, value in temp_results:
            sensor_idx = oid.split(".")[-1]
            temperatures.append(
                {
                    "sensor_index": int(sensor_idx),
                    "temperature_celsius": value,
                }
            )

        return temperatures

    async def get_cisco_poe_ports(
        self,
        host: str,
        credentials: SNMPCredentials,
        port: int = 161,
    ) -> dict[int, float]:
        """Get PoE power consumption per port from Cisco devices."""
        poe_results = await self.walk(host, OIDs.CISCO_POE_PORT_POWER, credentials, port)

        poe_ports = {}
        for oid, value in poe_results:
            port_idx = int(oid.split(".")[-1])
            # Value is in milliwatts
            poe_ports[port_idx] = value / 1000.0

        return poe_ports

    def _format_speed(self, speed_bps: int) -> str:
        """Format interface speed for display."""
        if speed_bps >= 1000000000:
            return f"{speed_bps // 1000000000} Gbps"
        elif speed_bps >= 1000000:
            return f"{speed_bps // 1000000} Mbps"
        elif speed_bps >= 1000:
            return f"{speed_bps // 1000} Kbps"
        else:
            return f"{speed_bps} bps"
