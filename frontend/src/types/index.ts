// Server types
export interface Server {
  id: number
  hostname: string
  ip_address: string
  status: 'online' | 'offline' | 'pending'
  os_info?: string
  cpu_info?: string
  cpu_cores?: number
  memory_total?: string
  disk_total?: string
  gpu_info?: string
  agent_installed: boolean
}

export interface ServerCredentials {
  hostname: string
  ip_address: string
  username: string
  password: string
  port: number
}

export interface SystemInfo {
  os?: string
  kernel?: string
  hostname?: string
  cpu?: string
  cpu_cores?: number
  memory_total?: string
  disk_total?: string
  disk_used?: string
  gpu?: string
}

export interface OnboardingResult {
  status: 'success' | 'error'
  server_id: number
  hostname: string
  ip_address: string
  key_exchanged: boolean
  agent_installed: boolean
  system_info: SystemInfo
  llm_analysis?: string
}

// Metrics types
export interface ServerMetric {
  server_id: number
  hostname: string
  ip_address: string
  status: string
  cpu_usage: number | null
  memory_percent: number | null
  disk_percent: number | null
  gpu_utilization: number | null
  gpu_temperature: number | null
  last_updated: string | null
}

export interface MetricsResponse {
  metrics: ServerMetric[]
}

export interface DetailedServerMetrics {
  server_id: number
  hostname: string
  status: string
  cpu: {
    usage: number
    cores: number
    per_core: Record<string, number>
  }
  memory: {
    used: number
    total: number
    percent: number
    available: number
    buffers: number
    cached: number
  }
  swap: {
    used: number
    total: number
  }
  disk: {
    used: number
    total: number
    percent: number
  }
  gpu: {
    utilization: number
    memory_used: number
    memory_total: number
    memory_percent: number
    temperature: number
    power: number
  } | null
  load_avg: {
    '1m': number
    '5m': number
    '15m': number
  }
  temperatures: Record<string, number>
  last_updated: string | null
}

// Project types
export interface Project {
  id: number
  name: string
  server_id: number
  path: string
  description?: string
  tech_stack?: string[]
  urls?: string[]
  ips?: string[]
  last_scanned?: string
}

export interface ProjectCreate {
  name: string
  server_id: number
  path: string
  description?: string
  urls?: string[]
}

// Chat types
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

// API Error type
export interface ApiError {
  detail: string
  code?: string
}

// Network Device types
export type DeviceType = 'switch' | 'router' | 'firewall' | 'access_point'
export type ConnectionType = 'snmp' | 'rest_api' | 'unifi' | 'ssh'
export type DeviceStatus = 'online' | 'offline' | 'pending'

export interface NetworkDevice {
  id: number
  name: string
  ip_address: string
  mac_address?: string
  device_type: DeviceType
  vendor?: string
  model?: string
  firmware_version?: string
  connection_type: ConnectionType
  location?: string
  description?: string
  port_count?: number
  poe_capable: boolean
  status: DeviceStatus
  last_seen?: string
  uptime_seconds?: number
}

export interface NetworkPort {
  id: number
  port_number: number
  port_name?: string
  enabled: boolean
  speed?: string
  duplex?: string
  vlan_id?: number
  vlan_name?: string
  poe_enabled: boolean
  poe_power?: number
  link_status: 'up' | 'down'
  admin_status: 'enabled' | 'disabled'
  connected_mac?: string
  connected_device?: string
  rx_bytes?: number
  tx_bytes?: number
}

export interface NetworkDeviceMetrics {
  device_id: number
  device_name: string
  timestamp?: string
  cpu_usage?: number
  memory_usage?: number
  temperature?: number
  uptime_seconds?: number
  total_rx_bytes?: number
  total_tx_bytes?: number
  rx_rate_mbps?: number
  tx_rate_mbps?: number
  port_metrics?: Record<string, { rx_bytes: number; tx_bytes: number }>
}

export interface SNMPConfig {
  version: '2c' | '3'
  community?: string
  username?: string
  auth_protocol?: 'MD5' | 'SHA'
  auth_password?: string
  priv_protocol?: 'DES' | 'AES'
  priv_password?: string
}

export interface NetworkDeviceOnboard {
  name: string
  ip_address: string
  device_type: DeviceType
  connection_type: ConnectionType
  snmp_config?: SNMPConfig
  location?: string
  description?: string
}

// Action types
export type ActionType = 'read' | 'write' | 'destructive'
export type ActionStatus = 'pending' | 'awaiting_confirmation' | 'confirmed' | 'executing' | 'completed' | 'failed' | 'cancelled' | 'expired'

export interface ActionAudit {
  action_id: string
  action_name: string
  action_type: ActionType
  category: string
  status: ActionStatus
  initiated_by?: string
  initiated_at?: string
  completed_at?: string
  natural_language_input?: string
  target_type?: string
  target_name?: string
  result?: Record<string, unknown>
  error_message?: string
  rollback_available: boolean
  rollback_executed: boolean
}

export interface PendingConfirmation {
  action_id: string
  confirmation_prompt: string
  risk_summary?: string
  affected_resources?: string[]
  expires_at: string
  created_at?: string
}

export interface ScheduledAction {
  id: number
  job_id: string
  name?: string
  action_name: string
  parameters?: Record<string, unknown>
  schedule_type: 'once' | 'cron' | 'interval' | 'conditional'
  schedule_config?: Record<string, unknown>
  condition_expression?: string
  status: 'active' | 'paused' | 'completed' | 'failed' | 'cancelled'
  enabled: boolean
  next_run?: string
  last_run?: string
  run_count: number
  error_count: number
  created_by?: string
  created_at?: string
}

export type ChatContext = 'general' | 'monitoring' | 'projects' | 'network' | 'actions' | 'home' | 'journal' | 'work'

// =============================================================================
// Home Automation types
// =============================================================================

export type HomePlatform = 'ring' | 'lg_thinq' | 'bosch' | 'homekit' | 'apple_media'
export type HomeDeviceType = 'doorbell' | 'camera' | 'chime' | 'washer' | 'dishwasher' | 'thermostat' | 'apple_tv' | 'homepod'
export type HomeDeviceStatus = 'online' | 'offline' | 'unavailable'
export type EventSeverity = 'info' | 'warning' | 'alert' | 'critical'

export interface HomeDevice {
  id: number
  device_id: string
  name: string
  device_type: HomeDeviceType
  platform: HomePlatform
  model?: string
  firmware_version?: string
  room?: string
  zone?: string
  status: HomeDeviceStatus
  state?: Record<string, unknown>
  capabilities?: string[]
  last_seen?: string
}

export interface HomeEvent {
  id: number
  event_id: string
  device_id: number
  event_type: string
  severity: EventSeverity
  title: string
  message?: string
  data?: Record<string, unknown>
  media_url?: string
  thumbnail_url?: string
  occurred_at: string
  acknowledged: boolean
}

export interface HomeAutomation {
  id: number
  automation_id: string
  name: string
  description?: string
  trigger_type: 'event' | 'schedule' | 'condition' | 'device_state'
  trigger_config: Record<string, unknown>
  conditions?: Record<string, unknown>[]
  actions: Record<string, unknown>[]
  enabled: boolean
  cooldown_seconds: number
  trigger_count: number
  last_triggered?: string
}

export interface HomePlatformStatus {
  id: string
  name: string
  available: boolean
  connected: boolean
}

export interface HomeDeviceAction {
  action: string
  params?: Record<string, unknown>
}

// Specific device state types
export interface ThermostatState {
  current_temperature?: number
  target_temperature?: number
  mode?: 'heat' | 'cool' | 'auto' | 'off'
  humidity?: number
  hvac_state?: 'heating' | 'cooling' | 'idle' | 'off'
  fan_mode?: 'auto' | 'on'
  occupancy?: 'home' | 'away' | 'sleep'
}

export interface DoorbellState {
  battery_level?: number
  is_online?: boolean
  volume?: number
  last_motion?: string
  last_ring?: string
}

export interface ApplianceState {
  power?: boolean
  cycle_state?: string
  remaining_time?: string
  door_locked?: boolean
  error?: string
}

export interface MediaPlayerState {
  power?: boolean
  playing?: boolean
  paused?: boolean
  idle?: boolean
  media_type?: string
  title?: string
  artist?: string
  album?: string
  genre?: string
  position?: number
  total_time?: number
  volume?: number
  shuffle?: string
  repeat?: string
}

// =============================================================================
// Journal types
// =============================================================================

export type JournalMood = 'happy' | 'excited' | 'neutral' | 'anxious' | 'sad' | 'stressed' | 'calm' | 'grateful'
export type JournalSource = 'manual' | 'chat_summary'
export type SummaryStatus = 'generated' | 'approved' | 'rejected'

export interface JournalEntry {
  entry_id: string
  date: string
  title?: string
  content: string
  mood?: JournalMood | string
  energy_level?: number
  tags: string[]
  source: JournalSource
  created_at?: string
  updated_at?: string
}

export interface JournalEntryCreate {
  content: string
  date?: string
  title?: string
  mood?: string
  energy_level?: number
  tags?: string[]
}

export interface JournalEntryUpdate {
  content?: string
  date?: string
  title?: string
  mood?: string
  energy_level?: number
  tags?: string[]
}

export interface JournalChatSummary {
  summary_id: string
  chat_session_id?: number
  summary_text: string
  key_topics: string[]
  sentiment?: string
  status: SummaryStatus
  model_used?: string
  tokens_used?: number
  created_at?: string
  journal_entry_id?: string
}

export interface JournalSearchResult extends JournalEntry {
  similarity: number
}

export interface JournalCalendarData {
  year: number
  month: number
  entries: Record<string, Array<{
    entry_id: string
    title?: string
    mood?: string
    source: string
  }>>
}

export interface JournalStats {
  total_entries: number
  current_streak: number
  mood_distribution: Record<string, number>
  source_distribution: Record<string, number>
  pending_summaries: number
}

// =============================================================================
// Work Notes Types
// =============================================================================

export type AccountStatus = 'active' | 'inactive' | 'prospect' | 'closed'
export type ActivityType = 'meeting' | 'call' | 'email' | 'task' | 'note' | 'follow_up'

export interface WorkContact {
  name: string
  role?: string
  email?: string
  phone?: string
}

export interface ActionItem {
  task: string
  due?: string
  status?: 'pending' | 'completed'
}

export interface AccountIntelligence {
  headquarters?: string
  industry?: string
  summary?: string
  employee_count?: number
  employee_count_range?: string
  founded_year?: number
  website_url?: string
  stock_ticker?: string
  stock_exchange?: string
  enriched_at?: string
  enrichment_source?: string
  enrichment_confidence?: number
}

export interface WorkAccount {
  account_id: string
  name: string
  description?: string
  contacts: WorkContact[]
  extra_data: {
    intelligence?: AccountIntelligence
    [key: string]: unknown
  }
  status: AccountStatus
  aliases: string[]
  created_at?: string
  updated_at?: string
}

export interface WorkNote {
  note_id: string
  account_id: number
  content: string
  activity_type?: ActivityType
  activity_date?: string
  mentioned_contacts: string[]
  action_items: ActionItem[]
  tags: string[]
  source: string
  created_at?: string
  updated_at?: string
}

export interface WorkNoteCreate {
  content: string
  activity_type?: ActivityType
  activity_date?: string
}

export interface AccountCreate {
  name: string
  description?: string
  contacts?: WorkContact[]
  extra_data?: Record<string, unknown>
}

export interface AccountUpdate {
  name?: string
  description?: string
  contacts?: WorkContact[]
  extra_data?: Record<string, unknown>
  aliases?: string[]
  status?: AccountStatus
}

export interface AccountStats {
  account_name: string
  total_notes: number
  activity_distribution: Record<string, number>
  last_activity?: string
  pending_action_items: ActionItem[]
  contact_count: number
}

export interface WorkSearchResult extends WorkNote {
  account_name: string
  similarity: number
}

export interface GlobalWorkStats {
  total_accounts: number
  total_notes: number
  status_distribution: Record<string, number>
  activity_distribution: Record<string, number>
  most_active_accounts: Array<{ name: string; note_count: number }>
}

export interface AccountEvent {
  type: 'action_item' | 'activity'
  task?: string
  activity_type?: string
  date: string
  note_id: string
  content_preview?: string
}

export interface AccountEvents {
  upcoming: AccountEvent[]
  recent: AccountEvent[]
  overdue: AccountEvent[]
}

export interface AccountSummary {
  account_overview: string
  recent_activity_summary: string
  model_used: string
}

// =============================================================================
// Work User Profile Types
// =============================================================================

export interface LearnedFact {
  id: string
  fact: string
  category: string
  confidence: number
  source_session_id?: string
  learned_at: string
  verified: boolean
}

export interface KeyRelationship {
  name: string
  role?: string
}

export interface WorkUserProfile {
  id: number | null
  name: string | null
  role: string | null
  company: string | null
  department: string | null
  responsibilities: string[]
  expertise_areas: string[]
  goals: string[]
  working_style: string | null
  key_relationships: KeyRelationship[]
  communication_prefs: string | null
  current_priorities: string[]
  learned_facts: LearnedFact[]
  last_learned_at: string | null
  created_at: string | null
  updated_at: string | null
}

export interface ProfileUpdate {
  name?: string
  role?: string
  company?: string
  department?: string
  responsibilities?: string[]
  expertise_areas?: string[]
  goals?: string[]
  working_style?: string
  key_relationships?: KeyRelationship[]
  communication_prefs?: string
  current_priorities?: string[]
}

export interface LearnResult {
  extracted: number
  added: number
  facts: Array<{
    fact: string
    category: string
    confidence: number
  }>
}

// =============================================================================
// Settings Types
// =============================================================================

export interface UserSettings {
  [key: string]: string
}

export interface ModelDefaults {
  general: string
  monitoring: string
  projects: string
  network: string
  actions: string
  home: string
  journal: string
  work: string
}
