import type {
  Server,
  Project,
  ChatMessage,
  ServerCredentials,
  OnboardingResult,
  MetricsResponse,
  DetailedServerMetrics,
  ProjectCreate,
  ChatContext,
  NetworkDevice,
  NetworkPort,
  NetworkDeviceMetrics,
  NetworkDeviceOnboard,
  ActionAudit,
  PendingConfirmation,
  ScheduledAction,
  HomeDevice,
  HomeEvent,
  HomeAutomation,
  HomePlatformStatus,
  HomeDeviceAction,
  JournalEntry,
  JournalEntryCreate,
  JournalEntryUpdate,
  JournalChatSummary,
  JournalSearchResult,
  JournalCalendarData,
  JournalStats,
  WorkAccount,
  WorkNote,
  WorkNoteCreate,
  WorkContact,
  AccountCreate,
  AccountUpdate,
  AccountStats,
  AccountEvents,
  AccountSummary,
  AccountIntelligence,
  WorkSearchResult,
  GlobalWorkStats,
  WorkUserProfile,
  ProfileUpdate,
  LearnResult,
  UserSettings,
  ModelDefaults,
} from '../types'

const API_URL = import.meta.env.VITE_API_URL || ''

// Re-export types for convenience
export type { Server, Project, ChatMessage }

class ApiService {
  private baseUrl: string

  constructor() {
    this.baseUrl = API_URL
  }

  // Servers
  async listServers(): Promise<Server[]> {
    try {
      const url = `${this.baseUrl}/api/servers/`
      console.log('Fetching servers from:', url)
      const response = await fetch(url, {
        method: 'GET',
        headers: {
          'Accept': 'application/json',
        },
        credentials: 'same-origin',
      })
      console.log('Response status:', response.status)
      if (!response.ok) {
        throw new Error(`Failed to fetch servers: ${response.status}`)
      }
      const data = await response.json()
      return data.servers
    } catch (e) {
      console.error('listServers error:', e)
      throw e
    }
  }

  async onboardServer(credentials: ServerCredentials): Promise<OnboardingResult> {
    const response = await fetch(`${this.baseUrl}/api/servers/onboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ credentials, install_agent: true }),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to onboard server')
    }
    return response.json()
  }

  async deleteServer(serverId: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/servers/${serverId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete server')
    }
  }

  // Projects
  async listProjects(): Promise<Project[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/projects/`)
      if (!response.ok) {
        throw new Error('Failed to fetch projects')
      }
      const data = await response.json()
      return data.projects
    } catch (e) {
      console.error('listProjects error:', e)
      return []
    }
  }

  async createProject(project: ProjectCreate): Promise<{ id: number }> {
    const response = await fetch(`${this.baseUrl}/api/projects/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(project),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create project')
    }
    return response.json()
  }

  async scanProject(projectId: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/projects/${projectId}/scan`, {
      method: 'POST',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to scan project')
    }
  }

  async deleteProject(projectId: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/projects/${projectId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete project')
    }
  }

  // Monitoring
  async getMetrics(): Promise<MetricsResponse> {
    try {
      const response = await fetch(`${this.baseUrl}/api/monitoring/`)
      if (!response.ok) {
        throw new Error('Failed to fetch metrics')
      }
      return response.json()
    } catch (e) {
      console.error('getMetrics error:', e)
      return { metrics: [] }
    }
  }

  async getServerMetrics(serverId: number): Promise<DetailedServerMetrics> {
    const response = await fetch(`${this.baseUrl}/api/monitoring/${serverId}/`)
    if (!response.ok) {
      throw new Error('Failed to fetch server metrics')
    }
    return response.json()
  }

  // Chat
  async sendMessage(
    message: string,
    sessionId: string,
    context: ChatContext,
    history: ChatMessage[]
  ): Promise<string> {
    const response = await fetch(`${this.baseUrl}/api/chat/message`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, session_id: sessionId, context, history }),
    })
    const data = await response.json()
    return data.response
  }

  async getModels(): Promise<{ models: { name: string; owned_by: string; created: number }[] }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/chat/models`)
      if (!response.ok) {
        throw new Error('Failed to fetch models')
      }
      return response.json()
    } catch (e) {
      console.error('getModels error:', e)
      return { models: [] }
    }
  }

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`)
      return response.ok
    } catch {
      return false
    }
  }

  // =============================================================================
  // Network Devices
  // =============================================================================

  async listNetworkDevices(): Promise<NetworkDevice[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/network/devices`)
      if (!response.ok) {
        throw new Error('Failed to fetch network devices')
      }
      const data = await response.json()
      return data.devices
    } catch (e) {
      console.error('listNetworkDevices error:', e)
      return []
    }
  }

  async getNetworkDevice(deviceId: number): Promise<NetworkDevice> {
    const response = await fetch(`${this.baseUrl}/api/network/devices/${deviceId}`)
    if (!response.ok) {
      throw new Error('Failed to fetch network device')
    }
    return response.json()
  }

  async onboardNetworkDevice(device: NetworkDeviceOnboard): Promise<NetworkDevice> {
    const response = await fetch(`${this.baseUrl}/api/network/devices/onboard`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(device),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to onboard network device')
    }
    return response.json()
  }

  async deleteNetworkDevice(deviceId: number): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/network/devices/${deviceId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete network device')
    }
  }

  async getDevicePorts(deviceId: number): Promise<NetworkPort[]> {
    const response = await fetch(`${this.baseUrl}/api/network/devices/${deviceId}/ports`)
    if (!response.ok) {
      throw new Error('Failed to fetch device ports')
    }
    const data = await response.json()
    return data.ports
  }

  async getNetworkMetrics(): Promise<NetworkDeviceMetrics[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/network/metrics`)
      if (!response.ok) {
        throw new Error('Failed to fetch network metrics')
      }
      const data = await response.json()
      return data.metrics
    } catch (e) {
      console.error('getNetworkMetrics error:', e)
      return []
    }
  }

  async getNetworkDeviceMetrics(deviceId: number): Promise<NetworkDeviceMetrics> {
    const response = await fetch(`${this.baseUrl}/api/network/metrics/${deviceId}`)
    if (!response.ok) {
      throw new Error('Failed to fetch network device metrics')
    }
    return response.json()
  }

  async discoverNetworkDevices(subnet: string): Promise<{ discovered: number; devices: NetworkDevice[] }> {
    const response = await fetch(`${this.baseUrl}/api/network/discover`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ subnet }),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to discover devices')
    }
    return response.json()
  }

  // =============================================================================
  // Actions & Confirmations
  // =============================================================================

  async confirmAction(actionId: string): Promise<{ success: boolean; data?: Record<string, unknown>; error?: string }> {
    const response = await fetch(`${this.baseUrl}/api/actions/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action_id: actionId }),
    })
    return response.json()
  }

  async cancelAction(actionId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/actions/cancel/${actionId}`, {
      method: 'POST',
    })
    return response.json()
  }

  async getPendingConfirmations(): Promise<PendingConfirmation[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/actions/pending`)
      if (!response.ok) {
        throw new Error('Failed to fetch pending confirmations')
      }
      const data = await response.json()
      return data.pending
    } catch (e) {
      console.error('getPendingConfirmations error:', e)
      return []
    }
  }

  async getAuditLog(params?: {
    limit?: number
    action_type?: string
    status?: string
    category?: string
  }): Promise<ActionAudit[]> {
    try {
      const searchParams = new URLSearchParams()
      if (params?.limit) searchParams.set('limit', String(params.limit))
      if (params?.action_type) searchParams.set('action_type', params.action_type)
      if (params?.status) searchParams.set('status', params.status)
      if (params?.category) searchParams.set('category', params.category)

      const url = `${this.baseUrl}/api/actions/audit${searchParams.toString() ? '?' + searchParams.toString() : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error('Failed to fetch audit log')
      }
      const data = await response.json()
      return data.audit_log
    } catch (e) {
      console.error('getAuditLog error:', e)
      return []
    }
  }

  async rollbackAction(actionId: string): Promise<{ success: boolean; error?: string }> {
    const response = await fetch(`${this.baseUrl}/api/actions/rollback/${actionId}`, {
      method: 'POST',
    })
    return response.json()
  }

  // =============================================================================
  // Scheduled Actions
  // =============================================================================

  async getScheduledActions(): Promise<ScheduledAction[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/actions/scheduled`)
      if (!response.ok) {
        throw new Error('Failed to fetch scheduled actions')
      }
      const data = await response.json()
      return data.scheduled
    } catch (e) {
      console.error('getScheduledActions error:', e)
      return []
    }
  }

  async createScheduledAction(action: {
    action_name: string
    parameters: Record<string, unknown>
    schedule_type: 'once' | 'cron' | 'interval' | 'conditional'
    schedule_config?: Record<string, unknown>
    condition_expression?: string
    name?: string
  }): Promise<ScheduledAction> {
    const response = await fetch(`${this.baseUrl}/api/actions/schedule`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create scheduled action')
    }
    return response.json()
  }

  async pauseScheduledAction(jobId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/actions/scheduled/${jobId}/pause`, {
      method: 'POST',
    })
    return response.json()
  }

  async resumeScheduledAction(jobId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/actions/scheduled/${jobId}/resume`, {
      method: 'POST',
    })
    return response.json()
  }

  async deleteScheduledAction(jobId: string): Promise<{ success: boolean }> {
    const response = await fetch(`${this.baseUrl}/api/actions/scheduled/${jobId}`, {
      method: 'DELETE',
    })
    return response.json()
  }

  // =============================================================================
  // Home Automation
  // =============================================================================

  async listHomePlatforms(): Promise<HomePlatformStatus[]> {
    try {
      const response = await fetch(`${this.baseUrl}/api/home/platforms`)
      if (!response.ok) {
        throw new Error('Failed to fetch platforms')
      }
      const data = await response.json()
      return data.platforms
    } catch (e) {
      console.error('listHomePlatforms error:', e)
      return []
    }
  }

  async connectHomePlatform(
    platform: string,
    credentials: Record<string, unknown>
  ): Promise<{ status: string; devices_discovered: number; devices: { id: number; name: string; type: string }[] }> {
    const response = await fetch(`${this.baseUrl}/api/home/platforms/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ platform, credentials }),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to connect platform')
    }
    return response.json()
  }

  async disconnectHomePlatform(platform: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/home/platforms/${platform}/disconnect`, {
      method: 'POST',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to disconnect platform')
    }
    return response.json()
  }

  async listHomeDevices(params?: {
    device_type?: string
    platform?: string
    room?: string
    status?: string
  }): Promise<{ devices: HomeDevice[]; count: number }> {
    try {
      const searchParams = new URLSearchParams()
      if (params?.device_type) searchParams.set('device_type', params.device_type)
      if (params?.platform) searchParams.set('platform', params.platform)
      if (params?.room) searchParams.set('room', params.room)
      if (params?.status) searchParams.set('status', params.status)

      const url = `${this.baseUrl}/api/home/devices${searchParams.toString() ? '?' + searchParams.toString() : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error('Failed to fetch home devices')
      }
      return response.json()
    } catch (e) {
      console.error('listHomeDevices error:', e)
      return { devices: [], count: 0 }
    }
  }

  async getHomeDevice(deviceId: number, refresh = false): Promise<HomeDevice> {
    const url = `${this.baseUrl}/api/home/devices/${deviceId}${refresh ? '?refresh=true' : ''}`
    const response = await fetch(url)
    if (!response.ok) {
      throw new Error('Failed to fetch home device')
    }
    return response.json()
  }

  async executeHomeDeviceAction(
    deviceId: number,
    action: HomeDeviceAction
  ): Promise<{
    success: boolean
    error?: string
    snapshot_url?: string
    recordings?: Array<{ id: string; url: string; created_at: string; type: string }>
  }> {
    const response = await fetch(`${this.baseUrl}/api/home/devices/${deviceId}/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(action),
    })
    return response.json()
  }

  // Build a proxy URL for media that needs to bypass CORS
  getMediaProxyUrl(url: string): string {
    return `${this.baseUrl}/api/home/media/proxy?url=${encodeURIComponent(url)}`
  }

  // Build URL for locally stored snapshots
  getSnapshotUrl(filename: string): string {
    return `${this.baseUrl}/api/home/snapshots/${filename}`
  }

  async updateHomeDevice(
    deviceId: number,
    updates: { name?: string; room?: string; zone?: string }
  ): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/home/devices/${deviceId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to update device')
    }
    return response.json()
  }

  async deleteHomeDevice(deviceId: number): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/home/devices/${deviceId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete device')
    }
    return response.json()
  }

  async listHomeEvents(params?: {
    device_id?: number
    event_type?: string
    severity?: string
    unacknowledged_only?: boolean
    limit?: number
    offset?: number
  }): Promise<{ events: HomeEvent[]; total: number }> {
    try {
      const searchParams = new URLSearchParams()
      if (params?.device_id) searchParams.set('device_id', String(params.device_id))
      if (params?.event_type) searchParams.set('event_type', params.event_type)
      if (params?.severity) searchParams.set('severity', params.severity)
      if (params?.unacknowledged_only) searchParams.set('unacknowledged_only', 'true')
      if (params?.limit) searchParams.set('limit', String(params.limit))
      if (params?.offset) searchParams.set('offset', String(params.offset))

      const url = `${this.baseUrl}/api/home/events${searchParams.toString() ? '?' + searchParams.toString() : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error('Failed to fetch home events')
      }
      return response.json()
    } catch (e) {
      console.error('listHomeEvents error:', e)
      return { events: [], total: 0 }
    }
  }

  async acknowledgeHomeEvent(eventId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/home/events/${eventId}/acknowledge`, {
      method: 'POST',
    })
    return response.json()
  }

  async acknowledgeAllHomeEvents(deviceId?: number): Promise<{ status: string; count: number }> {
    const url = deviceId
      ? `${this.baseUrl}/api/home/events/acknowledge-all?device_id=${deviceId}`
      : `${this.baseUrl}/api/home/events/acknowledge-all`
    const response = await fetch(url, { method: 'POST' })
    return response.json()
  }

  async listHomeAutomations(enabledOnly = false): Promise<{ automations: HomeAutomation[]; count: number }> {
    try {
      const url = `${this.baseUrl}/api/home/automations${enabledOnly ? '?enabled_only=true' : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error('Failed to fetch automations')
      }
      return response.json()
    } catch (e) {
      console.error('listHomeAutomations error:', e)
      return { automations: [], count: 0 }
    }
  }

  async createHomeAutomation(automation: {
    name: string
    description?: string
    trigger_type: string
    trigger_config: Record<string, unknown>
    conditions?: Record<string, unknown>[]
    actions: Record<string, unknown>[]
    enabled?: boolean
    cooldown_seconds?: number
  }): Promise<{ status: string; automation_id: string }> {
    const response = await fetch(`${this.baseUrl}/api/home/automations`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(automation),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create automation')
    }
    return response.json()
  }

  async getHomeAutomation(automationId: string): Promise<HomeAutomation> {
    const response = await fetch(`${this.baseUrl}/api/home/automations/${automationId}`)
    if (!response.ok) {
      throw new Error('Failed to fetch automation')
    }
    return response.json()
  }

  async updateHomeAutomation(
    automationId: string,
    updates: { enabled?: boolean; name?: string }
  ): Promise<{ status: string }> {
    const searchParams = new URLSearchParams()
    if (updates.enabled !== undefined) searchParams.set('enabled', String(updates.enabled))
    if (updates.name) searchParams.set('name', updates.name)

    const response = await fetch(
      `${this.baseUrl}/api/home/automations/${automationId}?${searchParams.toString()}`,
      { method: 'PATCH' }
    )
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to update automation')
    }
    return response.json()
  }

  async deleteHomeAutomation(automationId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/home/automations/${automationId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete automation')
    }
    return response.json()
  }

  // =============================================================================
  // Journal
  // =============================================================================

  async listJournalEntries(params?: {
    start_date?: string
    end_date?: string
    mood?: string
    tags?: string
    limit?: number
    offset?: number
  }): Promise<{ entries: JournalEntry[]; count: number }> {
    try {
      const searchParams = new URLSearchParams()
      if (params?.start_date) searchParams.set('start_date', params.start_date)
      if (params?.end_date) searchParams.set('end_date', params.end_date)
      if (params?.mood) searchParams.set('mood', params.mood)
      if (params?.tags) searchParams.set('tags', params.tags)
      if (params?.limit) searchParams.set('limit', String(params.limit))
      if (params?.offset) searchParams.set('offset', String(params.offset))

      const url = `${this.baseUrl}/api/journal/entries${searchParams.toString() ? '?' + searchParams.toString() : ''}`
      const response = await fetch(url)
      if (!response.ok) {
        throw new Error('Failed to fetch journal entries')
      }
      return response.json()
    } catch (e) {
      console.error('listJournalEntries error:', e)
      return { entries: [], count: 0 }
    }
  }

  async getJournalEntry(entryId: string): Promise<JournalEntry> {
    const response = await fetch(`${this.baseUrl}/api/journal/entries/${entryId}`)
    if (!response.ok) {
      throw new Error('Failed to fetch journal entry')
    }
    return response.json()
  }

  async createJournalEntry(entry: JournalEntryCreate): Promise<JournalEntry> {
    const response = await fetch(`${this.baseUrl}/api/journal/entries`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create journal entry')
    }
    return response.json()
  }

  async updateJournalEntry(entryId: string, updates: JournalEntryUpdate): Promise<JournalEntry> {
    const response = await fetch(`${this.baseUrl}/api/journal/entries/${entryId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to update journal entry')
    }
    return response.json()
  }

  async deleteJournalEntry(entryId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/journal/entries/${entryId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to delete journal entry')
    }
    return response.json()
  }

  async searchJournalEntries(query: string, limit = 5): Promise<{ query: string; results: JournalSearchResult[] }> {
    const response = await fetch(`${this.baseUrl}/api/journal/search?q=${encodeURIComponent(query)}&limit=${limit}`)
    if (!response.ok) {
      throw new Error('Failed to search journal entries')
    }
    return response.json()
  }

  async getJournalCalendar(year: number, month: number): Promise<JournalCalendarData> {
    const response = await fetch(`${this.baseUrl}/api/journal/calendar/${year}/${month}`)
    if (!response.ok) {
      throw new Error('Failed to fetch calendar data')
    }
    return response.json()
  }

  async getJournalStats(): Promise<JournalStats> {
    const response = await fetch(`${this.baseUrl}/api/journal/stats`)
    if (!response.ok) {
      throw new Error('Failed to fetch journal stats')
    }
    return response.json()
  }

  async generateJournalSummary(sessionId: string): Promise<JournalChatSummary> {
    const response = await fetch(`${this.baseUrl}/api/journal/sessions/${sessionId}/summarize`, {
      method: 'POST',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to generate summary')
    }
    return response.json()
  }

  async listPendingSummaries(): Promise<{ summaries: JournalChatSummary[]; count: number }> {
    try {
      const response = await fetch(`${this.baseUrl}/api/journal/summaries`)
      if (!response.ok) {
        throw new Error('Failed to fetch pending summaries')
      }
      return response.json()
    } catch (e) {
      console.error('listPendingSummaries error:', e)
      return { summaries: [], count: 0 }
    }
  }

  async approveSummary(
    summaryId: string,
    options?: { title?: string; mood?: string; energy_level?: number; tags?: string[] }
  ): Promise<{ status: string; entry: JournalEntry }> {
    const response = await fetch(`${this.baseUrl}/api/journal/summaries/${summaryId}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(options || {}),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to approve summary')
    }
    return response.json()
  }

  async rejectSummary(summaryId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/journal/summaries/${summaryId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to reject summary')
    }
    return response.json()
  }

  // =============================================================================
  // Work Notes
  // =============================================================================

  async listWorkAccounts(params?: {
    status?: string
    limit?: number
    offset?: number
  }): Promise<{ accounts: WorkAccount[]; count: number }> {
    try {
      const searchParams = new URLSearchParams()
      if (params?.status) searchParams.set('status', params.status)
      if (params?.limit) searchParams.set('limit', String(params.limit))
      if (params?.offset) searchParams.set('offset', String(params.offset))

      const url = `${this.baseUrl}/api/work/accounts${searchParams.toString() ? '?' + searchParams.toString() : ''}`
      const response = await fetch(url)
      if (!response.ok) throw new Error('Failed to fetch accounts')
      return response.json()
    } catch (e) {
      console.error('listWorkAccounts error:', e)
      return { accounts: [], count: 0 }
    }
  }

  async searchWorkAccounts(query: string, limit = 10): Promise<{
    query: string
    results: (WorkAccount & { match_score: number })[]
  }> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/search?q=${encodeURIComponent(query)}&limit=${limit}`)
    if (!response.ok) throw new Error('Failed to search accounts')
    return response.json()
  }

  async createWorkAccount(account: AccountCreate): Promise<WorkAccount> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(account),
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to create account')
    }
    return response.json()
  }

  async getWorkAccount(accountId: string): Promise<WorkAccount> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}`)
    if (!response.ok) throw new Error('Failed to fetch account')
    return response.json()
  }

  async updateWorkAccount(accountId: string, updates: AccountUpdate): Promise<WorkAccount> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!response.ok) throw new Error('Failed to update account')
    return response.json()
  }

  async deleteWorkAccount(accountId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Failed to delete account')
    return response.json()
  }

  async enrichAccount(accountId: string, force = false): Promise<WorkAccount> {
    const response = await fetch(
      `${this.baseUrl}/api/work/accounts/${accountId}/enrich?force=${force}`,
      { method: 'POST' }
    )
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to enrich account')
    }
    return response.json()
  }

  async getAccountIntelligence(accountId: string): Promise<{
    account_id: string
    account_name: string
    has_intelligence: boolean
    intelligence: AccountIntelligence | null
  }> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}/intelligence`)
    if (!response.ok) throw new Error('Failed to fetch intelligence')
    return response.json()
  }

  async getAccountStats(accountId: string): Promise<AccountStats> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}/stats`)
    if (!response.ok) throw new Error('Failed to fetch account stats')
    return response.json()
  }

  async getAccountEvents(
    accountId: string,
    daysBack: number = 30,
    daysAhead: number = 30
  ): Promise<AccountEvents> {
    const response = await fetch(
      `${this.baseUrl}/api/work/accounts/${accountId}/events?days_back=${daysBack}&days_ahead=${daysAhead}`
    )
    if (!response.ok) throw new Error('Failed to fetch account events')
    return response.json()
  }

  async getAccountSummary(accountId: string, days: number = 30): Promise<AccountSummary> {
    const response = await fetch(
      `${this.baseUrl}/api/work/accounts/${accountId}/summary?days=${days}`
    )
    if (!response.ok) throw new Error('Failed to generate account summary')
    return response.json()
  }

  async addAccountContact(accountId: string, contact: WorkContact): Promise<WorkAccount> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}/contacts`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(contact),
    })
    if (!response.ok) throw new Error('Failed to add contact')
    return response.json()
  }

  async listWorkNotes(accountId: string, params?: {
    limit?: number
    offset?: number
  }): Promise<{ account_name: string; notes: WorkNote[]; count: number }> {
    const searchParams = new URLSearchParams()
    if (params?.limit) searchParams.set('limit', String(params.limit))
    if (params?.offset) searchParams.set('offset', String(params.offset))

    const url = `${this.baseUrl}/api/work/accounts/${accountId}/notes${searchParams.toString() ? '?' + searchParams.toString() : ''}`
    const response = await fetch(url)
    if (!response.ok) throw new Error('Failed to fetch notes')
    return response.json()
  }

  async createWorkNote(accountId: string, note: WorkNoteCreate): Promise<WorkNote> {
    const response = await fetch(`${this.baseUrl}/api/work/accounts/${accountId}/notes`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(note),
    })
    if (!response.ok) throw new Error('Failed to create note')
    return response.json()
  }

  async getWorkNote(noteId: string): Promise<WorkNote> {
    const response = await fetch(`${this.baseUrl}/api/work/notes/${noteId}`)
    if (!response.ok) throw new Error('Failed to fetch note')
    return response.json()
  }

  async deleteWorkNote(noteId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/work/notes/${noteId}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Failed to delete note')
    return response.json()
  }

  async updateActionItem(
    noteId: string,
    task: string,
    updates: { status?: string; due?: string }
  ): Promise<WorkNote> {
    const response = await fetch(`${this.baseUrl}/api/work/notes/${noteId}/action-items`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task, ...updates }),
    })
    if (!response.ok) throw new Error('Failed to update action item')
    return response.json()
  }

  async deleteActionItem(noteId: string, task: string): Promise<{ status: string; remaining_items: number }> {
    const response = await fetch(
      `${this.baseUrl}/api/work/notes/${noteId}/action-items?task=${encodeURIComponent(task)}`,
      { method: 'DELETE' }
    )
    if (!response.ok) throw new Error('Failed to delete action item')
    return response.json()
  }

  async searchWorkNotes(query: string, accountId?: string, limit = 20): Promise<{
    query: string
    results: WorkSearchResult[]
  }> {
    const params = new URLSearchParams({ q: query, limit: String(limit) })
    if (accountId) params.set('account_id', accountId)
    const response = await fetch(`${this.baseUrl}/api/work/notes/search?${params.toString()}`)
    if (!response.ok) throw new Error('Failed to search notes')
    return response.json()
  }

  async getRecentWorkNotes(days = 30, limit = 50): Promise<{
    days: number
    notes: (WorkNote & { account_name: string })[]
    count: number
  }> {
    const response = await fetch(`${this.baseUrl}/api/work/notes/recent?days=${days}&limit=${limit}`)
    if (!response.ok) throw new Error('Failed to fetch recent notes')
    return response.json()
  }

  async getGlobalWorkStats(): Promise<GlobalWorkStats> {
    const response = await fetch(`${this.baseUrl}/api/work/stats`)
    if (!response.ok) throw new Error('Failed to fetch work stats')
    return response.json()
  }

  // =============================================================================
  // Work User Profile
  // =============================================================================

  async getWorkProfile(): Promise<WorkUserProfile> {
    const response = await fetch(`${this.baseUrl}/api/work/profile`)
    if (!response.ok) throw new Error('Failed to fetch work profile')
    return response.json()
  }

  async updateWorkProfile(updates: ProfileUpdate): Promise<WorkUserProfile> {
    const response = await fetch(`${this.baseUrl}/api/work/profile`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!response.ok) throw new Error('Failed to update profile')
    return response.json()
  }

  async learnFromChats(
    messages: Array<{ role: string; content: string }>,
    sessionId?: string
  ): Promise<LearnResult> {
    const response = await fetch(`${this.baseUrl}/api/work/profile/learn`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, session_id: sessionId }),
    })
    if (!response.ok) throw new Error('Failed to learn from chats')
    return response.json()
  }

  async verifyFact(factId: string, verified: boolean = true): Promise<WorkUserProfile> {
    const response = await fetch(`${this.baseUrl}/api/work/profile/facts/${factId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ verified }),
    })
    if (!response.ok) throw new Error('Failed to verify fact')
    return response.json()
  }

  async deleteFact(factId: string): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/work/profile/facts/${factId}`, {
      method: 'DELETE',
    })
    if (!response.ok) throw new Error('Failed to delete fact')
    return response.json()
  }

  // =============================================================================
  // Settings
  // =============================================================================

  async getSettings(): Promise<UserSettings> {
    try {
      const response = await fetch(`${this.baseUrl}/api/settings`)
      if (!response.ok) throw new Error('Failed to fetch settings')
      return response.json()
    } catch (e) {
      console.error('getSettings error:', e)
      return {}
    }
  }

  async updateSettings(settings: UserSettings): Promise<{ status: string; count: number }> {
    const response = await fetch(`${this.baseUrl}/api/settings`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ settings }),
    })
    if (!response.ok) throw new Error('Failed to update settings')
    return response.json()
  }

  async getModelDefaults(): Promise<ModelDefaults> {
    try {
      const response = await fetch(`${this.baseUrl}/api/settings/defaults/models`)
      if (!response.ok) throw new Error('Failed to fetch model defaults')
      return response.json()
    } catch (e) {
      console.error('getModelDefaults error:', e)
      // Return default fallback
      return {
        general: 'gpt-4o-mini',
        monitoring: 'gpt-4o-mini',
        projects: 'gpt-4o-mini',
        network: 'gpt-4o-mini',
        actions: 'gpt-4o-mini',
        home: 'gpt-4o-mini',
        journal: 'gpt-4o-mini',
        work: 'gpt-4o-mini',
      }
    }
  }

  async updateModelDefaults(defaults: Partial<ModelDefaults>): Promise<{ status: string; defaults: ModelDefaults }> {
    const response = await fetch(`${this.baseUrl}/api/settings/defaults/models`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ defaults }),
    })
    if (!response.ok) throw new Error('Failed to update model defaults')
    return response.json()
  }

  async getModelDefaultForContext(context: string): Promise<{ context: string; model: string }> {
    const response = await fetch(`${this.baseUrl}/api/settings/defaults/models/${context}`)
    if (!response.ok) throw new Error('Failed to fetch model default')
    return response.json()
  }

  async getModelRecommendations(): Promise<{
    recommendations: Record<string, { model: string; reason: string }>
    model_used: string
  }> {
    const response = await fetch(`${this.baseUrl}/api/settings/recommend-models`, {
      method: 'POST',
    })
    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.detail || 'Failed to get recommendations')
    }
    return response.json()
  }
}

export const api = new ApiService()
