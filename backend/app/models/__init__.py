from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, ForeignKey, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

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
