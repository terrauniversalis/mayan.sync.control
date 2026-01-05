"""Domain models for Mayan Sync Control."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class ConnectionType(str, Enum):
    """Supported physical and virtual connection types."""

    USB = "usb"
    BLUETOOTH = "bluetooth"
    WIFI = "wifi"
    LAN = "lan"
    OFFLINE = "offline"


class DeviceStatus(str, Enum):
    """High level state for a registered device."""

    ACTIVE = "active"
    DISCONNECTED = "disconnected"
    PENDING_VALIDATION = "pending-validation"


class RoutingMode(str, Enum):
    """Supported routing behaviour for a device assignment."""

    PRIMARY = "primary"
    MIRROR = "mirror"
    STANDBY = "standby"


@dataclass(frozen=True)
class DeviceDescriptor:
    """Canonical descriptor for a physical/virtual MIDI controller."""

    vendor: str
    product: str
    connection: ConnectionType
    identifiers: Dict[str, str] = field(default_factory=dict)
    metadata: Dict[str, str] = field(default_factory=dict)

    def canonical_payload(self) -> Dict[str, str]:
        """Return a sorted, serialisable payload for hashing purposes."""

        payload = {
            "vendor": self.vendor,
            "product": self.product,
            "connection": self.connection.value,
        }
        for label, data in (("identifiers", self.identifiers), ("metadata", self.metadata)):
            if data:
                payload[label] = {key: data[key] for key in sorted(data)}
        return payload


@dataclass
class DeviceRegistration:
    """Represents the lifecycle of a registered device."""

    descriptor: DeviceDescriptor
    u_sha: str
    status: DeviceStatus
    profiles: List[str] = field(default_factory=list)
    assigned_hosts: List[str] = field(default_factory=list)


@dataclass
class Host:
    """Host/scene that can receive MIDI routed devices."""

    host_id: str
    label: str
    priority: int = 0
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class RoutingAssignment:
    """Represents a routing relationship between a device and a host."""

    u_sha: str
    host_id: str
    mode: RoutingMode
    latency_ms: Optional[float] = None


@dataclass
class AgentConfig:
    """Configuration for an Agent runtime."""

    hosts: List[Host] = field(default_factory=list)
    default_profiles: Dict[str, List[str]] = field(default_factory=dict)
    inventory_path: Optional[str] = None
