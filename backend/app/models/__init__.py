import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class Server(Base):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True, index=True)
    hostname = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=False, unique=True)
    port = Column(Integer, default=22)
    username = Column(String(255), nullable=False)
    ssh_key_path = Column(String(512))
    status = Column(String(20), default="pending")  # online, offline, pending
    os_info = Column(Text)
    cpu_info = Column(String(255))
    cpu_cores = Column(Integer)
    memory_total = Column(String(50))
    disk_total = Column(String(50))
    gpu_info = Column(String(255))
    agent_installed = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    metrics = relationship("Metric", back_populates="server")
    projects = relationship("Project", back_populates="server")


class Metric(Base):
    __tablename__ = "metrics"

    id = Column(Integer, primary_key=True, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # CPU metrics
    cpu_usage = Column(Float)
    cpu_per_core = Column(JSON)  # {"cpu0": 25.5, "cpu1": 35.2, ...}

    # Memory metrics
    memory_used = Column(Float)
    memory_total = Column(Float)
    memory_percent = Column(Float)
    memory_available = Column(Float)
    memory_buffers = Column(Float)
    memory_cached = Column(Float)
    swap_used = Column(Float)
    swap_total = Column(Float)

    # Disk metrics
    disk_used = Column(Float)
    disk_total = Column(Float)
    disk_percent = Column(Float)

    # GPU metrics
    gpu_utilization = Column(Float)
    gpu_memory_used = Column(Float)
    gpu_memory_total = Column(Float)
    gpu_memory_percent = Column(Float)
    gpu_temperature = Column(Float)
    gpu_power = Column(Float)

    # System metrics
    load_avg_1m = Column(Float)
    load_avg_5m = Column(Float)
    load_avg_15m = Column(Float)

    # Temperatures
    temperatures = Column(JSON)

    server = relationship("Server", back_populates="metrics")


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    server_id = Column(Integer, ForeignKey("servers.id"), nullable=False)
    path = Column(String(512), nullable=False)
    description = Column(Text)
    tech_stack = Column(JSON)  # List of technologies
    urls = Column(JSON)  # List of URLs found
    ips = Column(JSON)  # List of IPs found
    last_scanned = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    server = relationship("Server", back_populates="projects")


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), unique=True, nullable=False, index=True)
    context = Column(String(50), nullable=False)  # general, monitoring, projects
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages = relationship("ChatMessage", back_populates="session")


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    tool_calls = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)

    session = relationship("ChatSession", back_populates="messages")


# =============================================================================
# Network Device Models
# =============================================================================


class NetworkDevice(Base):
    """Network device entity (switches, routers, APs)."""

    __tablename__ = "network_devices"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    ip_address = Column(String(45), nullable=False, unique=True)
    mac_address = Column(String(17))

    # Device classification
    device_type = Column(String(50), nullable=False)  # switch, router, firewall, access_point
    vendor = Column(String(50))  # cisco, hp, ubiquiti, pfsense, opnsense, aruba
    model = Column(String(100))
    firmware_version = Column(String(100))

    # Connection configuration
    connection_type = Column(String(20), nullable=False)  # snmp, rest_api, unifi, ssh
    snmp_community = Column(String(100))  # For SNMP v2c
    snmp_version = Column(String(10), default="2c")  # 2c or 3
    snmp_v3_config = Column(
        JSON
    )  # For SNMP v3: {user, auth_protocol, auth_pass, priv_protocol, priv_pass}
    api_url = Column(String(255))  # For REST APIs
    api_credentials = Column(JSON)  # {username, password/api_key}
    ssh_username = Column(String(100))
    ssh_key_path = Column(String(512))

    # Device info
    location = Column(String(255))
    description = Column(Text)
    port_count = Column(Integer)
    uplink_ports = Column(JSON)  # List of uplink port numbers
    poe_capable = Column(Boolean, default=False)
    management_vlan = Column(Integer)

    # Status
    status = Column(String(20), default="pending")  # online, offline, pending
    last_seen = Column(DateTime)
    uptime_seconds = Column(Integer)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    metrics = relationship("NetworkMetric", back_populates="device", cascade="all, delete-orphan")
    ports = relationship("NetworkPort", back_populates="device", cascade="all, delete-orphan")
    wifi_clients = relationship("WiFiClient", back_populates="device", cascade="all, delete-orphan")


class NetworkPort(Base):
    """Individual port information for switches."""

    __tablename__ = "network_ports"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("network_devices.id"), nullable=False)
    port_number = Column(Integer, nullable=False)
    port_name = Column(String(50))
    if_index = Column(Integer)  # SNMP interface index

    # Port configuration
    enabled = Column(Boolean, default=True)
    speed = Column(String(20))  # 10M, 100M, 1G, 10G, auto
    duplex = Column(String(10))  # full, half, auto
    vlan_id = Column(Integer)
    vlan_name = Column(String(100))
    port_type = Column(String(20))  # access, trunk, hybrid
    allowed_vlans = Column(JSON)  # For trunk ports

    # PoE
    poe_enabled = Column(Boolean, default=False)
    poe_power = Column(Float)  # Current power draw in watts
    poe_max_power = Column(Float)  # Max power budget

    # Status
    link_status = Column(String(10))  # up, down
    admin_status = Column(String(10))  # enabled, disabled

    # Connected device info (if discovered)
    connected_mac = Column(String(17))
    connected_device = Column(String(255))

    device = relationship("NetworkDevice", back_populates="ports")


class NetworkMetric(Base):
    """Time-series metrics for network devices."""

    __tablename__ = "network_metrics"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("network_devices.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)

    # System metrics
    cpu_usage = Column(Float)
    memory_usage = Column(Float)
    memory_total = Column(BigInteger)
    temperature = Column(Float)
    uptime_seconds = Column(Integer)

    # Aggregate traffic
    total_rx_bytes = Column(BigInteger)
    total_tx_bytes = Column(BigInteger)
    total_rx_packets = Column(BigInteger)
    total_tx_packets = Column(BigInteger)

    # Error counters
    total_errors = Column(Integer)
    total_drops = Column(Integer)
    total_collisions = Column(Integer)

    # Per-port metrics (JSON for flexibility)
    port_metrics = Column(JSON)  # {port_num: {rx_bytes, tx_bytes, rx_rate, tx_rate, errors, ...}}

    # WiFi-specific metrics (for APs)
    wifi_clients = Column(Integer)
    wifi_channel = Column(Integer)
    wifi_channel_width = Column(Integer)
    wifi_noise = Column(Float)
    wifi_utilization = Column(Float)

    device = relationship("NetworkDevice", back_populates="metrics")


class WiFiClient(Base):
    """Connected WiFi clients (for APs)."""

    __tablename__ = "wifi_clients"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("network_devices.id"), nullable=False)
    mac_address = Column(String(17), nullable=False)
    hostname = Column(String(255))
    ip_address = Column(String(45))

    # Connection info
    ssid = Column(String(100))
    bssid = Column(String(17))
    band = Column(String(10))  # 2.4GHz, 5GHz, 6GHz
    channel = Column(Integer)
    signal_strength = Column(Integer)  # dBm
    noise = Column(Integer)  # dBm
    snr = Column(Integer)  # Signal-to-noise ratio
    tx_rate = Column(Integer)  # Mbps
    rx_rate = Column(Integer)  # Mbps

    # Session info
    connected_at = Column(DateTime)
    last_seen = Column(DateTime, default=datetime.utcnow)
    rx_bytes = Column(BigInteger, default=0)
    tx_bytes = Column(BigInteger, default=0)

    # Authentication
    auth_type = Column(String(50))  # WPA2, WPA3, etc.
    is_authorized = Column(Boolean, default=True)
    is_blocked = Column(Boolean, default=False)

    device = relationship("NetworkDevice", back_populates="wifi_clients")


# =============================================================================
# Action System Models
# =============================================================================


class ActionAudit(Base):
    """Full audit trail of all executed actions."""

    __tablename__ = "action_audit"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True
    )
    action_name = Column(String(255), nullable=False, index=True)
    action_type = Column(String(50), nullable=False)  # read, write, destructive
    category = Column(String(100))  # server, network, firewall, service, monitoring, system

    # Action details
    parameters = Column(JSON)
    target_type = Column(String(50))  # server, network_device, service
    target_id = Column(Integer)
    target_name = Column(String(255))

    # Initiator
    initiated_by = Column(String(255))  # User ID or session ID
    session_id = Column(String(255))
    natural_language_input = Column(Text)  # Original user request
    llm_interpretation = Column(Text)  # How LLM understood it

    # Timing
    initiated_at = Column(DateTime, default=datetime.utcnow, index=True)
    completed_at = Column(DateTime)

    # Status and result
    status = Column(
        String(50), default="pending"
    )  # pending, confirmed, executing, completed, failed, cancelled
    result = Column(JSON)
    error_message = Column(Text)

    # Confirmation
    confirmation_required = Column(Boolean, default=False)
    confirmed_by = Column(String(255))
    confirmed_at = Column(DateTime)

    # Rollback
    rollback_available = Column(Boolean, default=False)
    rollback_executed = Column(Boolean, default=False)
    rollback_at = Column(DateTime)
    rollback_result = Column(JSON)

    pending_confirmation = relationship(
        "PendingConfirmation", back_populates="audit", uselist=False, cascade="all, delete-orphan"
    )


class PendingConfirmation(Base):
    """Actions awaiting user approval."""

    __tablename__ = "pending_confirmations"

    id = Column(Integer, primary_key=True, index=True)
    action_id = Column(
        UUID(as_uuid=True), ForeignKey("action_audit.action_id"), unique=True, nullable=False
    )
    expires_at = Column(DateTime, nullable=False)
    confirmation_prompt = Column(Text, nullable=False)
    risk_summary = Column(Text)
    affected_resources = Column(JSON)  # List of resources that will be affected
    created_at = Column(DateTime, default=datetime.utcnow)

    audit = relationship("ActionAudit", back_populates="pending_confirmation")


class ScheduledAction(Base):
    """Scheduled and conditional actions."""

    __tablename__ = "scheduled_actions"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255))  # Human-readable name for the schedule
    action_name = Column(String(255), nullable=False)
    parameters = Column(JSON)

    # Schedule configuration
    schedule_type = Column(String(50), nullable=False)  # once, cron, interval, conditional
    schedule_config = Column(JSON)  # cron expression, interval config, or condition params

    # For conditional actions
    condition_expression = Column(Text)  # Human-readable: "cpu > 95% for 10m"
    condition_metric = Column(String(100))  # Metric to monitor
    condition_operator = Column(String(10))  # >, <, >=, <=, ==
    condition_threshold = Column(Float)
    condition_duration_seconds = Column(Integer)  # How long condition must be true
    last_condition_check = Column(DateTime)
    condition_met_since = Column(DateTime)  # When condition first became true

    # Metadata
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Execution tracking
    next_run = Column(DateTime)
    last_run = Column(DateTime)
    last_result = Column(JSON)
    run_count = Column(Integer, default=0)
    error_count = Column(Integer, default=0)

    # Status
    status = Column(String(50), default="active")  # active, paused, completed, failed, cancelled
    enabled = Column(Boolean, default=True)
    max_runs = Column(Integer)  # NULL = unlimited
    expires_at = Column(DateTime)


# =============================================================================
# Home Automation Models
# =============================================================================


class HomeDevice(Base):
    """Home automation device entity."""

    __tablename__ = "home_devices"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(String(255), unique=True, nullable=False, index=True)  # External device ID
    name = Column(String(255), nullable=False)

    # Device classification
    device_type = Column(
        String(50), nullable=False
    )  # doorbell, camera, washer, dishwasher, thermostat, apple_tv, homepod
    platform = Column(String(50), nullable=False)  # ring, lg_thinq, bosch, homekit, apple_media
    model = Column(String(255))
    firmware_version = Column(String(100))

    # Location/grouping
    room = Column(String(100))  # living_room, kitchen, bedroom, etc.
    zone = Column(String(100))  # upstairs, downstairs, outdoor

    # Connection status
    status = Column(String(20), default="offline")  # online, offline, unavailable
    last_seen = Column(DateTime)

    # Device capabilities (JSON array of capability strings)
    capabilities = Column(JSON)  # ["motion_detect", "video_stream", "two_way_audio", "battery"]

    # Current state (device-type specific)
    state = Column(JSON)  # {"is_ringing": false, "battery_level": 85, "motion_detected": false}

    # Configuration
    config = Column(JSON)  # Device-specific settings

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    credentials = relationship(
        "HomeDeviceCredential", back_populates="device", uselist=False, cascade="all, delete-orphan"
    )
    events = relationship("HomeEvent", back_populates="device", cascade="all, delete-orphan")


class HomeDeviceCredential(Base):
    """Encrypted credential storage for home device APIs."""

    __tablename__ = "home_device_credentials"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("home_devices.id"), unique=True, nullable=False)
    platform = Column(String(50), nullable=False)  # ring, lg_thinq, bosch, homekit

    # OAuth tokens
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)

    # API keys/credentials
    api_key = Column(Text)
    client_id = Column(String(255))
    client_secret = Column(Text)

    # Platform-specific auth data
    auth_data = Column(JSON)  # {username, hardware_id, 2fa_token, etc.}

    # Token refresh tracking
    last_refresh = Column(DateTime)
    refresh_failures = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    device = relationship("HomeDevice", back_populates="credentials")


class HomeEvent(Base):
    """Events from home automation devices."""

    __tablename__ = "home_events"

    id = Column(Integer, primary_key=True, index=True)
    device_id = Column(Integer, ForeignKey("home_devices.id"), nullable=False)
    event_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)

    # Event classification
    event_type = Column(
        String(50), nullable=False
    )  # motion, ring, cycle_complete, temp_alert, media_change
    severity = Column(String(20), default="info")  # info, warning, alert, critical

    # Event data
    title = Column(String(255), nullable=False)
    message = Column(Text)
    data = Column(JSON)  # Event-specific payload

    # Media attachments (for Ring snapshots, etc.)
    media_url = Column(String(512))
    thumbnail_url = Column(String(512))

    # Timestamps
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Processing status
    acknowledged = Column(Boolean, default=False)
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(255))

    # Automation trigger tracking
    triggered_automations = Column(JSON)  # List of automation IDs triggered

    device = relationship("HomeDevice", back_populates="events")


class HomeAutomation(Base):
    """Automation rules for home devices."""

    __tablename__ = "home_automations"

    id = Column(Integer, primary_key=True, index=True)
    automation_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)

    # Trigger configuration
    trigger_type = Column(String(50), nullable=False)  # event, schedule, condition, device_state
    trigger_config = Column(JSON, nullable=False)
    # Examples:
    # {"type": "event", "device_id": 1, "event_type": "ring"}
    # {"type": "schedule", "cron": "0 7 * * *"}
    # {"type": "device_state", "device_id": 2, "state_key": "temperature", "operator": ">", "value": 75}

    # Conditions (all must be true)
    conditions = Column(JSON)  # [{"type": "time_range", "start": "06:00", "end": "22:00"}, ...]

    # Actions to execute
    actions = Column(JSON, nullable=False)
    # [{"device_id": 3, "action": "set_temperature", "params": {"target": 72}},
    #  {"type": "notification", "message": "Doorbell rang while you were away"}]

    # Execution settings
    enabled = Column(Boolean, default=True)
    cooldown_seconds = Column(Integer, default=0)  # Minimum time between executions
    last_triggered = Column(DateTime)

    # Metadata
    created_by = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Statistics
    trigger_count = Column(Integer, default=0)
    last_result = Column(JSON)


class HomePlatformCredential(Base):
    """Platform-level credentials (for platforms that auth at account level, not device level)."""

    __tablename__ = "home_platform_credentials"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), unique=True, nullable=False)  # ring, lg_thinq, bosch

    # OAuth tokens
    access_token = Column(Text)
    refresh_token = Column(Text)
    token_expires_at = Column(DateTime)

    # API keys/credentials
    api_key = Column(Text)
    client_id = Column(String(255))
    client_secret = Column(Text)

    # Platform-specific auth data
    auth_data = Column(JSON)  # {username, hardware_id, etc.}

    # Status
    connected = Column(Boolean, default=False)
    last_refresh = Column(DateTime)
    refresh_failures = Column(Integer, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# Journal Models
# =============================================================================


class JournalEntry(Base):
    """Personal journal entries with embeddings for RAG."""

    __tablename__ = "journal_entries"

    id = Column(Integer, primary_key=True, index=True)
    entry_id = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True
    )
    date = Column(DateTime, nullable=False)  # The date this entry is for
    title = Column(String(255))
    content = Column(Text, nullable=False)

    # Emotional state tracking
    mood = Column(String(50))  # happy, neutral, sad, anxious, excited, etc.
    energy_level = Column(Integer)  # 1-5 scale

    # Tags for categorization
    tags = Column(JSON)  # ['work', 'family', 'health']

    # Source tracking
    source = Column(String(50), default="manual")  # manual, chat_summary
    source_session_id = Column(String(255))  # If created from chat summary

    # Note: embedding column is defined as vector(1536) in migration
    # SQLAlchemy doesn't have native vector support, so we handle it in the service

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to summaries that created this entry
    source_summary = relationship(
        "JournalChatSummary", back_populates="journal_entry", uselist=False
    )


class JournalChatSummary(Base):
    """Summaries generated from chat sessions for journal entries."""

    __tablename__ = "journal_chat_summaries"

    id = Column(Integer, primary_key=True, index=True)
    summary_id = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True
    )
    chat_session_id = Column(Integer, ForeignKey("chat_sessions.id", ondelete="CASCADE"))
    journal_entry_id = Column(Integer, ForeignKey("journal_entries.id", ondelete="SET NULL"))

    # Summary content
    summary_text = Column(Text, nullable=False)
    key_topics = Column(JSON)  # ['work stress', 'family dinner', 'exercise']
    sentiment = Column(String(50))  # positive, negative, neutral, mixed

    # Generation metadata
    model_used = Column(String(100))
    tokens_used = Column(Integer)

    # Approval workflow
    status = Column(String(50), default="generated")  # generated, approved, rejected

    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    chat_session = relationship("ChatSession")
    journal_entry = relationship("JournalEntry", back_populates="source_summary")


# =============================================================================
# Work Notes Models
# =============================================================================


class WorkAccount(Base):
    """Customer/client account for work notes."""

    __tablename__ = "work_accounts"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True
    )
    name = Column(String(255), nullable=False, index=True)
    normalized_name = Column(String(255), nullable=False, index=True)  # Lowercase for matching

    # Semi-structured data - LLM helps maintain
    description = Column(Text)
    contacts = Column(JSON)  # [{"name": "John", "role": "CTO", "email": "...", "phone": "..."}]
    extra_data = Column(JSON)  # {"industry": "mining", "size": "enterprise", "location": "Denver"}

    # Relationship tracking
    status = Column(String(50), default="active")  # active, inactive, prospect, closed

    # Aliases for smart matching - LLM can populate these
    aliases = Column(JSON)  # ["Covia Holdings", "Covia Corp"]

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    notes = relationship("WorkNote", back_populates="account", cascade="all, delete-orphan")


class WorkNote(Base):
    """Individual work notes attached to accounts."""

    __tablename__ = "work_notes"

    id = Column(Integer, primary_key=True, index=True)
    note_id = Column(
        UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False, index=True
    )
    account_id = Column(Integer, ForeignKey("work_accounts.id"), nullable=False)

    # Note content
    content = Column(Text, nullable=False)

    # Semi-structured activity data (LLM extracts from content)
    activity_type = Column(String(50))  # meeting, call, email, task, note, follow_up
    activity_date = Column(DateTime)  # When the activity occurred

    # Extracted entities (LLM populates)
    mentioned_contacts = Column(JSON)  # ["John Smith", "Jane Doe"]
    action_items = Column(
        JSON
    )  # [{"task": "Send proposal", "due": "2024-01-10", "status": "pending"}]
    tags = Column(JSON)  # ["proposal", "pricing", "technical"]

    # Source tracking
    source = Column(String(50), default="manual")  # manual, chat
    source_session_id = Column(String(255))

    # Note: embedding column is defined as vector(1536) in migration

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    account = relationship("WorkAccount", back_populates="notes")


# =============================================================================
# User Settings
# =============================================================================


class UserSetting(Base):
    """Key-value settings storage."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# Work User Profile
# =============================================================================


class WorkUserProfile(Base):
    """User profile learned from work conversations."""

    __tablename__ = "work_user_profile"

    id = Column(Integer, primary_key=True, index=True)

    # Core identity (LLM extracts these)
    name = Column(String(255))
    role = Column(String(255))  # "Solutions Architect"
    company = Column(String(255))  # "Cisco"
    department = Column(String(255))  # "Enterprise Sales"

    # Rich context (JSON for flexibility)
    responsibilities = Column(JSON)  # ["Pre-sales technical support", "POC delivery"]
    expertise_areas = Column(JSON)  # ["Networking", "Security", "Cloud"]
    goals = Column(JSON)  # ["Q1: Close 3 enterprise deals"]
    working_style = Column(Text)  # Free-form learned preferences
    key_relationships = Column(JSON)  # [{"name": "Bob", "role": "Manager"}]
    communication_prefs = Column(Text)  # "Prefers brief summaries"
    current_priorities = Column(JSON)  # ["Covia deal", "Training certification"]

    # Learning metadata
    # Each fact: {"id": uuid, "fact": "...", "category": "role", "confidence": 0.9,
    #             "source_session_id": "...", "learned_at": "...", "verified": false}
    learned_facts = Column(JSON, default=list)
    last_learned_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# Journal User Profile
# =============================================================================


class JournalUserProfile(Base):
    """User profile learned from journal conversations."""

    __tablename__ = "journal_user_profile"

    id = Column(Integer, primary_key=True, index=True)

    # Core identity
    name = Column(String(255))
    nickname = Column(String(255))  # How user refers to themselves

    # Life context (JSON for flexibility)
    life_context = Column(
        JSON
    )  # {"relationships": [...], "living_situation": "...", "pets": [...]}
    interests = Column(JSON)  # ["hiking", "cooking", "reading"]
    goals = Column(JSON)  # ["learn Spanish", "run a marathon"]
    challenges = Column(JSON)  # ["managing stress", "work-life balance"]
    values = Column(JSON)  # ["family", "creativity", "health"]
    communication_style = Column(Text)  # Free-form notes about how they express themselves

    # Learning metadata
    # Each fact: {"id": uuid, "fact": "...", "category": "identity|relationships|interests|goals|challenges|values|life_events",
    #             "confidence": 0.9, "source_session_id": "...", "learned_at": "...", "verified": false}
    learned_facts = Column(JSON, default=list)
    last_learned_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# =============================================================================
# Journal Fact Extraction History
# =============================================================================


class JournalFactExtraction(Base):
    """Records fact extraction attempts for visibility and debugging."""

    __tablename__ = "journal_fact_extractions"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True)
    extracted_at = Column(DateTime, default=datetime.utcnow, index=True)

    # The extracted fact
    fact_text = Column(Text, nullable=False)
    category = Column(String(50))
    confidence = Column(Float)

    # What happened to this fact
    status = Column(String(20), nullable=False)  # "added", "duplicate", "low_confidence"
    duplicate_of = Column(Text)  # If duplicate, what it matched against


# =============================================================================
# DNS Security Models
# =============================================================================


class DnsConfig(Base):
    """DNS service configuration."""

    __tablename__ = "dns_config"

    id = Column(Integer, primary_key=True, index=True)
    enabled = Column(Boolean, default=True)

    # Upstream DNS servers
    upstream_dns = Column(JSON)  # ["https://dns.cloudflare.com/dns-query"]
    bootstrap_dns = Column(JSON)  # ["9.9.9.9", "1.1.1.1"]

    # Feature flags
    dnssec_enabled = Column(Boolean, default=True)
    doh_enabled = Column(Boolean, default=True)
    dot_enabled = Column(Boolean, default=True)

    # Filtering
    filtering_enabled = Column(Boolean, default=True)
    safe_browsing = Column(Boolean, default=True)
    parental_control = Column(Boolean, default=False)

    # Caching
    cache_size = Column(Integer, default=4194304)  # 4MB
    cache_ttl_min = Column(Integer, default=60)
    cache_ttl_max = Column(Integer, default=86400)

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DnsBlocklist(Base):
    """DNS blocklist subscriptions."""

    __tablename__ = "dns_blocklists"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    url = Column(String(512), nullable=False, unique=True)
    category = Column(String(50))  # ads, tracking, malware, phishing, adult
    enabled = Column(Boolean, default=True)
    rules_count = Column(Integer, default=0)
    last_updated = Column(DateTime)
    update_frequency_hours = Column(Integer, default=24)
    created_at = Column(DateTime, default=datetime.utcnow)


class DnsCustomRule(Base):
    """User-defined DNS rules (block/allow/rewrite)."""

    __tablename__ = "dns_custom_rules"

    id = Column(Integer, primary_key=True, index=True)
    rule_type = Column(String(20), nullable=False)  # block, allow, rewrite
    domain = Column(String(255), nullable=False, index=True)
    answer = Column(String(255))  # For rewrites
    comment = Column(Text)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    created_by = Column(String(255))


class DnsClient(Base):
    """Known DNS clients with per-client settings."""

    __tablename__ = "dns_clients"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(100), unique=True, nullable=False)  # IP or MAC
    name = Column(String(255))
    ip_addresses = Column(JSON)  # ["10.10.20.50"]
    mac_address = Column(String(17))

    # Per-client settings
    use_global_settings = Column(Boolean, default=True)
    filtering_enabled = Column(Boolean, default=True)
    safe_browsing = Column(Boolean)
    parental_control = Column(Boolean)
    blocked_services = Column(JSON)  # ["facebook", "tiktok"]
    custom_upstream = Column(JSON)  # Override upstream for this client

    # Statistics
    queries_count = Column(BigInteger, default=0)
    blocked_count = Column(BigInteger, default=0)
    last_seen = Column(DateTime)

    # Profiling
    has_profile = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DnsQueryLog(Base):
    """DNS query log entries (TimescaleDB hypertable)."""

    __tablename__ = "dns_query_log"

    id = Column(BigInteger, primary_key=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Query details
    client_ip = Column(String(45), nullable=False, index=True)
    client_name = Column(String(255))
    domain = Column(String(255), nullable=False, index=True)
    query_type = Column(String(10))  # A, AAAA, CNAME, MX, etc.

    # Response
    response_code = Column(String(20))  # NOERROR, NXDOMAIN, SERVFAIL
    response_ip = Column(String(45))
    answer = Column(Text)

    # Classification
    status = Column(String(20), index=True)  # allowed, blocked, filtered
    block_reason = Column(String(100))  # adblock, safebrowsing, parental, custom
    blocklist_id = Column(Integer, ForeignKey("dns_blocklists.id"))

    # Performance
    upstream = Column(String(255))
    response_time_ms = Column(Float)
    cached = Column(Boolean, default=False)

    # Security indicators
    is_encrypted = Column(Boolean)  # DoH/DoT
    dnssec_validated = Column(Boolean)

    blocklist = relationship("DnsBlocklist")


class DnsStats(Base):
    """Aggregated DNS statistics (hourly/daily rollups)."""

    __tablename__ = "dns_stats"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    period = Column(String(10))  # hour, day

    total_queries = Column(BigInteger, default=0)
    blocked_queries = Column(BigInteger, default=0)
    cached_queries = Column(BigInteger, default=0)

    avg_response_time = Column(Float)

    # Top lists (JSON for flexibility)
    top_domains = Column(JSON)  # [{"domain": "google.com", "count": 1500}]
    top_blocked = Column(JSON)
    top_clients = Column(JSON)

    # Category breakdown
    block_by_category = Column(JSON)  # {"ads": 500, "tracking": 200}


# =============================================================================
# DNS Analytics Models
# =============================================================================


class DnsClientProfile(Base):
    """Behavioral baseline profile for DNS clients."""

    __tablename__ = "dns_client_profile"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(
        String(100), ForeignKey("dns_clients.client_id"), unique=True, nullable=False
    )

    # Behavioral baselines
    baseline_domains = Column(JSON)  # {"google.com": {"hourly_avg": 15, "std_dev": 3}}
    typical_query_hours = Column(JSON)  # {"0": 2, "1": 1, ... "23": 45}
    typical_query_types = Column(JSON)  # {"A": 85, "AAAA": 10, "MX": 5}
    typical_categories = Column(JSON)  # {"cdn": 40, "social": 20}

    # Device inference
    device_type_inference = Column(String(50))  # desktop, mobile, iot, server
    device_type_confidence = Column(Float)

    # Query rate statistics
    normal_query_rate_per_hour = Column(Float)
    query_rate_std_dev = Column(Float)
    max_query_rate_observed = Column(Float)

    # Baseline metadata
    baseline_generated_at = Column(DateTime)
    baseline_data_points = Column(Integer, default=0)
    baseline_days_analyzed = Column(Integer, default=7)

    # Sensitivity settings
    anomaly_sensitivity = Column(Float, default=2.0)  # Std dev multiplier

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationship to client
    client = relationship("DnsClient")


class DnsDomainReputation(Base):
    """Cached reputation scores for domains."""

    __tablename__ = "dns_domain_reputation"

    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String(255), unique=True, nullable=False)

    # Reputation scoring
    reputation_score = Column(Float)  # 0-100 (100 = trusted)
    entropy_score = Column(Float)  # Shannon entropy

    # Domain metadata
    domain_age_days = Column(Integer)
    typical_ttl = Column(Integer)
    registrar = Column(String(255))

    # Categorization
    category = Column(String(50), index=True)  # cdn, advertising, social, etc.
    category_confidence = Column(Float)
    category_source = Column(String(50))  # llm, manual

    # Query statistics
    first_seen = Column(DateTime)
    last_seen = Column(DateTime)
    query_count = Column(BigInteger, default=0)
    unique_clients = Column(Integer, default=0)

    # Threat indicators
    threat_indicators = Column(JSON)  # {"dga_score": 0.85, "tunneling_score": 0.1}

    # LLM analysis cache
    llm_analysis = Column(Text)  # JSON with full analysis
    llm_analyzed_at = Column(DateTime)

    # External reputation (optional)
    external_reputation = Column(JSON)  # {"virustotal": {...}}

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DnsSecurityAlert(Base):
    """DNS security alerts with LLM analysis."""

    __tablename__ = "dns_security_alert"

    id = Column(Integer, primary_key=True, index=True)
    alert_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Alert classification
    alert_type = Column(
        String(50), nullable=False, index=True
    )  # dga, tunneling, fast_flux, behavioral, reputation
    severity = Column(String(20), nullable=False, index=True)  # low, medium, high, critical

    # Context
    client_ip = Column(String(45), index=True)
    domain = Column(String(255))
    domains = Column(JSON)  # For multi-domain alerts

    # Alert content
    title = Column(String(255), nullable=False)
    description = Column(Text)
    raw_data = Column(JSON)  # Full detection context

    # LLM analysis
    llm_analysis = Column(Text)  # Natural language explanation
    remediation = Column(Text)  # LLM recommendations
    confidence = Column(Float)  # Analysis confidence

    # Status tracking
    status = Column(
        String(20), default="open", index=True
    )  # open, acknowledged, resolved, false_positive
    acknowledged_at = Column(DateTime)
    acknowledged_by = Column(String(255))
    resolved_at = Column(DateTime)
    resolution_notes = Column(Text)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DnsThreatAnalysis(Base):
    """Cached LLM threat analyses."""

    __tablename__ = "dns_threat_analysis"

    id = Column(Integer, primary_key=True, index=True)
    analysis_id = Column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, nullable=False)

    # Analysis target
    analysis_type = Column(String(50), nullable=False)  # domain, pattern, client_behavior
    target_identifier = Column(String(255), nullable=False)  # domain or client_ip

    # Analysis result
    analysis_result = Column(JSON)  # Full LLM response
    threat_level = Column(String(20))
    classification = Column(String(50))
    confidence = Column(Float)
    recommendations = Column(JSON)

    # Metadata
    model_used = Column(String(100))
    tokens_used = Column(Integer)
    analysis_duration_ms = Column(Float)

    # Cache control
    analyzed_at = Column(DateTime)
    expires_at = Column(DateTime, index=True)


# =============================================================================
# LLM Usage Tracking
# =============================================================================


class LlmUsageLog(Base):
    """Per-request LLM usage tracking."""

    __tablename__ = "llm_usage_log"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)

    # Request context
    feature = Column(String(50), nullable=False, index=True)  # chat, journal, dns, work, settings
    function_name = Column(String(100), index=True)  # chat_stream, fact_extraction, etc.
    context = Column(String(50))  # general, monitoring, projects, network, dns, etc.
    session_id = Column(String(255))

    # Model info
    model = Column(String(100), nullable=False)

    # Token counts
    prompt_tokens = Column(Integer, nullable=False)
    completion_tokens = Column(Integer, nullable=False)
    total_tokens = Column(Integer, nullable=False)

    # Cost in cents (Float for precision with cheap models/embeddings)
    cost_cents = Column(Float, nullable=False, default=0.0)

    # Optional metadata
    tool_calls_count = Column(Integer, default=0)
    cached = Column(Boolean, default=False)


class LlmUsageStats(Base):
    """Aggregated LLM usage statistics (hourly/daily)."""

    __tablename__ = "llm_usage_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, index=True)
    period = Column(String(10), nullable=False)  # hour, day

    # Aggregation keys
    feature = Column(String(50), nullable=False, index=True)
    model = Column(String(100))

    # Totals
    request_count = Column(Integer, default=0)
    prompt_tokens = Column(BigInteger, default=0)
    completion_tokens = Column(BigInteger, default=0)
    total_tokens = Column(BigInteger, default=0)
    total_cost_cents = Column(Float, default=0.0)
