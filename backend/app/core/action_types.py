"""Action type definitions - kept separate to avoid circular imports."""
from enum import Enum


class ActionType(str, Enum):
    """Classification of action risk level."""

    READ = "read"  # Safe, read-only queries
    WRITE = "write"  # Modifies state but generally reversible
    DESTRUCTIVE = "destructive"  # Potentially dangerous, may be irreversible


class ActionCategory(str, Enum):
    """Category of infrastructure being acted upon."""

    SERVER = "server"
    NETWORK = "network"
    FIREWALL = "firewall"
    SERVICE = "service"
    MONITORING = "monitoring"
    PROJECT = "project"
    SEARCH = "search"
    SYSTEM = "system"
