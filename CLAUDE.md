# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Jarvis is an AI/LLM-enabled lab monitoring, smart home automation, and personal productivity platform. It provides:
- Server onboarding with SSH key exchange and agent installation
- Real-time monitoring of CPU, GPU, memory, disk, and temperatures
- Network device management with SNMP support
- DNS security with threat detection, blocklists, and LLM-powered analysis
- Smart home integration (Ring, LG ThinQ, Bosch, HomeKit, Apple TV)
- Personal journaling with AI-powered search, summarization, and user profile learning
- Work account management with account intelligence and LLM-enriched notes
- LLM-powered chat with isolated contexts and comprehensive usage tracking
- Infrastructure automation with scheduled actions and confirmation workflows
- Project scanning with tech stack detection
- Web search integration via SearXNG

## Architecture

### Infrastructure
| Component | Host | Purpose |
|-----------|------|---------|
| Jarvis Web App | 10.10.20.235 | FastAPI backend + React frontend |
| Nginx | 10.10.20.235 | HTTPS reverse proxy (port 443) |
| OpenAI API | External | Primary LLM provider |
| Ollama (Legacy) | 10.10.20.62 | Llama 3.1 8B with RTX 3090 |
| SearXNG | 10.10.20.235:8888 | Self-hosted web search |
| AdGuard Home | 10.10.20.235:3053 | DNS server with filtering |
| PostgreSQL | 10.10.20.235:5432 | TimescaleDB for metrics |

### Tech Stack
- **Backend**: Python 3.11, FastAPI, SQLAlchemy, Paramiko, pysnmp
- **Frontend**: React 18, TypeScript, Vite, TailwindCSS, Recharts
- **Database**: PostgreSQL 15 with TimescaleDB
- **LLM**: OpenAI API (primary), Ollama (legacy)
- **Task Scheduling**: APScheduler
- **DNS**: AdGuard Home integration

## Development Commands

```bash
# Start development environment
docker-compose up -d

# Backend only (for local dev)
cd backend && pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Frontend only (for local dev)
cd frontend && npm install
npm run dev

# Run database migrations
cd backend && alembic upgrade head

# Run tests
cd backend && pytest
cd frontend && npm test

# View logs
docker-compose logs -f backend
docker-compose logs -f frontend
```

## Project Structure

```
Jarvis/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # SQLAlchemy setup
│   │   ├── api/routes/          # API endpoints
│   │   │   ├── chat.py          # LLM chat with streaming
│   │   │   ├── servers.py       # Server management
│   │   │   ├── monitoring.py    # Metrics & WebSocket
│   │   │   ├── projects.py      # Project scanning
│   │   │   ├── network.py       # SNMP device management
│   │   │   ├── actions.py       # Infrastructure automation
│   │   │   ├── home.py          # Smart home control
│   │   │   ├── journal.py       # Personal journaling
│   │   │   ├── work.py          # Work accounts & notes
│   │   │   ├── dns.py           # DNS security & analytics
│   │   │   ├── usage.py         # LLM usage tracking
│   │   │   └── settings.py      # User preferences
│   │   ├── services/            # Business logic
│   │   │   ├── ssh.py           # SSH operations
│   │   │   ├── openai_service.py # OpenAI LLM client
│   │   │   ├── ollama.py        # Ollama LLM client (legacy)
│   │   │   ├── search.py        # SearXNG client
│   │   │   ├── snmp.py          # SNMP device polling
│   │   │   ├── actions.py       # Action execution & scheduling
│   │   │   ├── journal.py       # Journal management & RAG
│   │   │   ├── journal_tasks.py # Journal background tasks
│   │   │   ├── work_notes.py    # Work account management
│   │   │   ├── account_intelligence.py # Company info gathering
│   │   │   ├── llm_usage.py     # LLM usage tracking
│   │   │   ├── dns.py           # AdGuard Home integration
│   │   │   ├── dns_tasks.py     # DNS query logging
│   │   │   ├── dns_advanced_detection.py # Threat detection
│   │   │   ├── dns_client_profiling.py   # Client behavior
│   │   │   ├── dns_domain_reputation.py  # Domain scoring
│   │   │   ├── dns_llm_analysis.py       # LLM threat analysis
│   │   │   ├── dns_alert_manager.py      # WebSocket alerts
│   │   │   ├── dns_analytics_tasks.py    # Analytics processing
│   │   │   └── home/            # Smart home integrations
│   │   ├── models/              # SQLAlchemy models
│   │   ├── tools/               # LLM tool definitions
│   │   │   ├── base.py          # Tool base classes
│   │   │   ├── server_tools.py  # Server metrics
│   │   │   ├── project_tools.py # Project scanning
│   │   │   ├── network_tools.py # Network devices
│   │   │   ├── home_tools.py    # Smart home
│   │   │   ├── journal_tools.py # Journal operations
│   │   │   ├── work_tools.py    # Work accounts
│   │   │   ├── web_search.py    # SearXNG search
│   │   │   ├── infrastructure_actions.py # Command execution
│   │   │   ├── dns_tools.py     # DNS queries & rules
│   │   │   └── dns_analytics_tools.py    # DNS threat analysis
│   │   └── core/                # Security, logging, exceptions
│   ├── alembic/                 # Database migrations
│   ├── tests/                   # Test suite
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.tsx              # Main app with routing
│   │   ├── components/
│   │   │   ├── layout/          # Sidebar, Layout
│   │   │   ├── chat/            # ChatPanel
│   │   │   └── servers/         # OnboardingWizard
│   │   ├── pages/               # Page components
│   │   │   ├── Dashboard.tsx    # System overview
│   │   │   ├── Servers.tsx      # Server management
│   │   │   ├── Monitoring.tsx   # Real-time metrics
│   │   │   ├── Chat.tsx         # LLM chat interface
│   │   │   ├── Projects.tsx     # Project scanning
│   │   │   ├── Network.tsx      # Network devices
│   │   │   ├── Actions.tsx      # Infrastructure automation
│   │   │   ├── Home.tsx         # Smart home control
│   │   │   ├── Journal.tsx      # Personal journaling
│   │   │   ├── Work.tsx         # Work management
│   │   │   ├── DNS.tsx          # DNS security dashboard
│   │   │   ├── Usage.tsx        # LLM usage analytics
│   │   │   └── Settings.tsx     # User preferences
│   │   ├── services/            # API client
│   │   └── types/               # TypeScript definitions
│   └── package.json
├── agent/                       # Remote monitoring agent
├── nginx/                       # HTTPS proxy config
├── scripts/                     # Setup scripts
├── docker-compose.yml           # Development environment
└── docker-compose.prod.yml      # Production environment
```

## Key APIs

### Server Onboarding
```
POST /api/servers/onboard
{
  "credentials": {
    "hostname": "server-01",
    "ip_address": "10.10.20.x",
    "username": "root",
    "password": "...",
    "port": 22
  },
  "install_agent": true
}
```

### Chat (Streaming)
```
POST /api/chat/message/stream
{
  "message": "...",
  "session_id": "...",
  "context": "general|monitoring|projects|network|actions|home|journal|work|dns",
  "history": [...]
}
```

### Network Device Onboarding
```
POST /api/network/devices/onboard
{
  "name": "switch-01",
  "ip_address": "10.10.20.x",
  "device_type": "switch",
  "connection_method": "snmp",
  "snmp_community": "public",
  "snmp_version": "2c"
}
```

### DNS Security
```
GET  /api/dns/stats                    # Query statistics
GET  /api/dns/query-log                # Recent queries
POST /api/dns/rules                    # Add block/allow rule
GET  /api/dns/blocklists               # List blocklists
GET  /api/dns/alerts                   # Security alerts
POST /api/dns/alerts/{id}/acknowledge  # Acknowledge alert
```

### LLM Usage
```
GET /api/usage/summary?hours=24        # Usage summary
GET /api/usage/by-feature?hours=24     # Breakdown by feature
GET /api/usage/trends?hours=168        # Usage trends
GET /api/usage/daily-history?days=30   # Daily history
GET /api/usage/monthly-history         # Monthly history
```

### Metrics WebSocket
```
WS /api/monitoring/ws
```

### Smart Home
```
POST /api/home/devices/{device_id}/action
{
  "action": "unlock|lock|arm|disarm|set_temperature|...",
  "params": {}
}
```

## LLM Integration

The OpenAI service (`backend/app/services/openai_service.py`) is the primary LLM provider:
- `chat()` - Single response with tool support
- `chat_stream()` - Streaming response (SSE)
- `list_models()` - Available models
- Embedding generation for semantic search (text-embedding-3-small)

All LLM calls are tracked via `llm_usage.py` with per-request logging of tokens and costs.

Legacy Ollama support in `backend/app/services/ollama.py`:
- `chat()` - Single response
- `chat_stream()` - Streaming response (SSE)
- `chat_with_tools()` - Tool calling support

### Chat Contexts
- **general**: Full lab context, all tools available
- **monitoring**: Server metrics focus, monitoring tools
- **projects**: Project info, code analysis tools
- **network**: Network device management, SNMP tools
- **actions**: Infrastructure automation, command execution
- **home**: Smart home device control, automation
- **journal**: Personal journal entries, search, summaries, fact extraction
- **work**: Work accounts, notes, action items, account intelligence
- **dns**: DNS security, threat analysis, blocklist management

## LLM Tools

Tools are defined in `backend/app/tools/` and registered for LLM function calling:

### Core Tools
- `server_tools.py` - Server metrics: `list_servers`, `get_server_metrics`, `get_server_cpu/memory/disk/gpu`
- `project_tools.py` - Project scanning: `list_projects`, `scan_project`, `get_project_info`
- `network_tools.py` - SNMP queries: `list_network_devices`, `get_device_metrics`, `get_port_info`
- `home_tools.py` - Smart home: `list_home_devices`, `get_device_status`, `ring_snapshot`
- `journal_tools.py` - Journal: `search_journal`, `create_journal_entry`, `summarize_journal`
- `work_tools.py` - Work accounts: `search_work_accounts`, `create_work_note`, `get_work_user_profile`
- `web_search.py` - SearXNG: `search_web`, `get_search_results`
- `infrastructure_actions.py` - Commands: `reboot_server`, `restart_service`, `execute_command`

### DNS Security Tools
- `dns_tools.py` - DNS queries: `get_dns_stats`, `block_domain`, `allow_domain`, `search_query_log`
- `dns_analytics_tools.py` - Threat analysis: `analyze_dns_threat`, `get_domain_reputation`, `investigate_client`

## Database Models

Core models in `backend/app/models/`:

### Server Monitoring
- **Server** - Monitored servers with SSH credentials
- **Metric** - Time-series performance data (TimescaleDB hypertable)
- **Project** - Codebase metadata per server

### Chat
- **ChatSession** - Session with context type
- **ChatMessage** - Message history with tool calls

### Network
- **NetworkDevice** - Switches, routers, APs with SNMP config
- **NetworkPort** - Port info with VLAN, PoE status
- **NetworkMetric** - Time-series network metrics
- **WiFiClient** - Connected WiFi clients

### Actions
- **ActionAudit** - Full audit trail with confirmation workflow
- **PendingConfirmation** - Actions awaiting approval
- **ScheduledAction** - Cron/interval/conditional scheduling

### Smart Home
- **HomeDevice** - Device with capabilities and state
- **HomeDeviceCredential** - OAuth tokens and API keys
- **HomeEvent** - Device events with media attachments
- **HomeAutomation** - Automation rules
- **HomePlatformCredential** - Platform-level auth

### Journal
- **JournalEntry** - Entries with mood, energy, tags, embeddings
- **JournalChatSummary** - AI-generated summaries from chat
- **JournalUserProfile** - Learned identity, relationships, interests, goals
- **JournalFactExtraction** - Fact extraction audit trail

### Work
- **WorkAccount** - Customer/client with aliases for matching
- **WorkNote** - Notes with extracted metadata (contacts, action items)
- **WorkUserProfile** - Learned role, company, expertise

### DNS Security
- **DnsConfig** - Service configuration (DNSSEC, DoH/DoT, filtering)
- **DnsBlocklist** - Blocklist subscriptions
- **DnsCustomRule** - User-defined rules (block/allow/rewrite)
- **DnsClient** - Known clients with per-client settings
- **DnsQueryLog** - Query logs (TimescaleDB hypertable)
- **DnsStats** - Hourly/daily aggregations

### DNS Analytics
- **DnsClientProfile** - Behavioral baselines, device type inference
- **DnsDomainReputation** - Domain scoring with entropy, threat indicators
- **DnsSecurityAlert** - Alerts with LLM analysis and remediation
- **DnsThreatAnalysis** - Cached LLM threat analyses

### LLM Usage
- **LlmUsageLog** - Per-request tracking (feature, function, tokens, cost)
- **LlmUsageStats** - Hourly/daily aggregations by feature and model

### Settings
- **UserSetting** - Key-value settings storage

## DNS Security Features

The DNS security module provides comprehensive threat detection and analysis:

### Threat Detection
- **DGA Detection** - Identifies algorithmically generated domains using entropy analysis
- **DNS Tunneling** - Detects data exfiltration via long subdomains and high query rates
- **Fast-Flux Networks** - Identifies botnets using IP diversity and TTL analysis
- **Behavioral Anomalies** - Compares client behavior against learned baselines

### Domain Reputation
- Entropy-based scoring
- TLD reputation (trusted .gov/.edu vs suspicious .tk/.ml)
- Domain age and registration analysis
- Query pattern classification

### Client Profiling
- Device type inference (IoT, mobile, desktop, server)
- Behavioral baseline generation
- Anomaly sensitivity configuration

### LLM-Powered Analysis
- Natural language threat explanations
- Remediation recommendations
- Confidence scoring

## UI Design

Cisco Magnetic / Meraki style:
- Primary: `#00bceb`
- Background: `#1a1a2e`
- Surface: `#252542`
- Use `magnetic-card`, `magnetic-button-primary` utility classes

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://jarvis:password@db:5432/jarvis

# LLM Providers
OPENAI_API_KEY=sk-...
OLLAMA_URL=http://10.10.20.62:11434

# Search
SEARXNG_URL=http://localhost:8888

# DNS
ADGUARD_URL=http://localhost:3053
ADGUARD_USERNAME=admin
ADGUARD_PASSWORD=...

# Security
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Smart Home (optional)
RING_USERNAME=...
RING_PASSWORD=...
LG_THINQ_USERNAME=...
LG_THINQ_PASSWORD=...
```

## Background Tasks

The application runs several background tasks via APScheduler:

- **Home Automation** - Event polling and automation triggers
- **Journal Processing** - Periodic fact extraction and summarization
- **DNS Query Logging** - Real-time query capture from AdGuard
- **DNS Analytics** - Threat detection loops, reputation analysis
- **LLM Usage Aggregation** - Hourly/daily stats generation

## Setup Scripts

```bash
# Set up Ollama on Alpha (run on 10.10.20.62)
./scripts/setup-ollama.sh

# Set up Nginx HTTPS (run on 10.10.20.235)
./scripts/setup-nginx.sh
```

## Testing

```bash
# Backend tests
cd backend && pytest

# Frontend tests
cd frontend && npm test

# With coverage
cd backend && pytest --cov=app
```

## Production Deployment

```bash
# Build and start production containers
docker-compose -f docker-compose.prod.yml up -d --build

# Run migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head
```

## Database Migrations

Recent migrations:
- `008_journal_user_profile.py` - Journal user profile storage
- `009_journal_fact_extractions.py` - Fact extraction audit trail
- `010_dns_security.py` - Core DNS security models
- `011_dns_analytics.py` - DNS analytics models
- `012_llm_usage_tracking.py` - LLM usage tracking
- `013_fix_llm_usage_cost_precision.py` - Cost precision fix for embeddings
