const API_URL = import.meta.env.VITE_API_URL || ''

export interface Server {
  id: number
  hostname: string
  ip_address: string
  status: 'online' | 'offline' | 'pending'
  os_info?: string
  cpu_info?: string
  memory_total?: string
  gpu_info?: string
}

export interface Project {
  id: number
  name: string
  server_id: number
  path: string
  description?: string
  tech_stack?: string[]
  urls?: string[]
}

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

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

  async onboardServer(credentials: {
    hostname: string
    ip_address: string
    username: string
    password: string
    port: number
  }): Promise<any> {
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

  async createProject(project: {
    name: string
    server_id: number
    path: string
    description?: string
  }): Promise<{ id: number }> {
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
  async getMetrics(): Promise<{ metrics: any[] }> {
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

  async getServerMetrics(serverId: number): Promise<any> {
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
    context: 'general' | 'monitoring' | 'projects',
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

  // Health check
  async healthCheck(): Promise<boolean> {
    try {
      const response = await fetch(`${this.baseUrl}/health`)
      return response.ok
    } catch {
      return false
    }
  }
}

export const api = new ApiService()
