import { useState, useEffect } from 'react'
import { Plus, FolderGit2, ExternalLink, RefreshCw, Trash2, Search, Loader2 } from 'lucide-react'
import ChatPanel from '../components/chat/ChatPanel'
import { api } from '../services/api'

interface ServerInfo {
  id: number
  hostname: string
  ip_address: string
}

interface Project {
  id: number
  name: string
  path: string
  server_id: number
  description?: string
  tech_stack?: string[]
  urls?: string[]
  ips?: string[]
  last_scanned?: string
}

export default function Projects() {
  const [sessionId] = useState(() => `projects-${Date.now()}`)
  const [projects, setProjects] = useState<Project[]>([])
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [showAddForm, setShowAddForm] = useState(false)
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState<number | null>(null)
  const [error, setError] = useState<string | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    server_id: 0,
    path: '',
    description: '',
    url: '',
  })

  const fetchProjects = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await api.listProjects()
      setProjects(data as Project[])
    } catch (err: any) {
      setError(err.message || 'Failed to fetch projects')
    } finally {
      setLoading(false)
    }
  }

  const fetchServers = async () => {
    try {
      const data = await api.listServers()
      setServers(data)
      if (data.length > 0 && formData.server_id === 0) {
        setFormData((prev) => ({ ...prev, server_id: data[0].id }))
      }
    } catch (err) {
      console.error('Failed to fetch servers:', err)
    }
  }

  useEffect(() => {
    fetchProjects()
    fetchServers()
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!formData.name || !formData.path || !formData.server_id) return

    try {
      const project = await api.createProject({
        name: formData.name,
        server_id: formData.server_id,
        path: formData.path,
        description: formData.description || undefined,
        urls: formData.url ? [formData.url] : undefined,
      })

      // Trigger scan
      await api.scanProject(project.id)

      setShowAddForm(false)
      setFormData({ name: '', server_id: servers[0]?.id || 0, path: '', description: '', url: '' })
      fetchProjects()
    } catch (err: any) {
      setError(err.message || 'Failed to create project')
    }
  }

  const handleScan = async (projectId: number) => {
    try {
      setScanning(projectId)
      await api.scanProject(projectId)
      // Poll for updates
      setTimeout(() => {
        fetchProjects()
        setScanning(null)
      }, 5000)
    } catch (err: any) {
      setError(err.message || 'Failed to scan project')
      setScanning(null)
    }
  }

  const handleDelete = async (projectId: number) => {
    if (!confirm('Are you sure you want to delete this project?')) return
    try {
      await api.deleteProject(projectId)
      fetchProjects()
    } catch (err: any) {
      setError(err.message || 'Failed to delete project')
    }
  }

  return (
    <div className="h-full flex gap-6">
      {/* Main projects area */}
      <div className="flex-1 space-y-6 overflow-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Projects</h1>
            <p className="text-surface-300 mt-1">Manage and monitor projects</p>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={fetchProjects}
              className="magnetic-button-secondary p-2"
              title="Refresh"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
            <button
              onClick={() => setShowAddForm(true)}
              className="magnetic-button-primary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Project
            </button>
          </div>
        </div>

        {error && (
          <div className="p-3 bg-error/20 border border-error rounded-magnetic text-error text-sm">
            {error}
          </div>
        )}

        {showAddForm && (
          <div className="magnetic-card">
            <h3 className="text-lg font-medium text-white mb-4">Add New Project</h3>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm text-surface-300 mb-1">Project Name</label>
                <input
                  type="text"
                  className="magnetic-input"
                  placeholder="My Project"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-surface-300 mb-1">Server</label>
                <select
                  className="magnetic-input"
                  value={formData.server_id}
                  onChange={(e) => setFormData({ ...formData, server_id: parseInt(e.target.value) })}
                  required
                >
                  <option value={0}>Select a server...</option>
                  {servers.map((server) => (
                    <option key={server.id} value={server.id}>
                      {server.hostname} ({server.ip_address})
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm text-surface-300 mb-1">Path</label>
                <input
                  type="text"
                  className="magnetic-input"
                  placeholder="/var/www/project"
                  value={formData.path}
                  onChange={(e) => setFormData({ ...formData, path: e.target.value })}
                  required
                />
              </div>
              <div>
                <label className="block text-sm text-surface-300 mb-1">Description (optional)</label>
                <input
                  type="text"
                  className="magnetic-input"
                  placeholder="Brief description..."
                  value={formData.description}
                  onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-sm text-surface-300 mb-1">App URL (optional)</label>
                <input
                  type="url"
                  className="magnetic-input"
                  placeholder="https://myapp.example.com"
                  value={formData.url}
                  onChange={(e) => setFormData({ ...formData, url: e.target.value })}
                />
              </div>
              <div className="flex gap-3">
                <button type="submit" className="magnetic-button-primary">
                  Add & Scan
                </button>
                <button
                  type="button"
                  onClick={() => setShowAddForm(false)}
                  className="magnetic-button-secondary"
                >
                  Cancel
                </button>
              </div>
            </form>
          </div>
        )}

        {loading && projects.length === 0 ? (
          <div className="magnetic-card text-center py-12">
            <RefreshCw className="w-8 h-8 text-surface-400 mx-auto mb-4 animate-spin" />
            <p className="text-surface-300">Loading projects...</p>
          </div>
        ) : projects.length === 0 ? (
          <div className="magnetic-card text-center py-12">
            <FolderGit2 className="w-12 h-12 text-surface-400 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-white mb-2">No projects yet</h3>
            <p className="text-surface-300 mb-4">
              Add a project to let Jarvis analyze its tech stack
            </p>
            <button onClick={() => setShowAddForm(true)} className="magnetic-button-primary">
              Add Project
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {projects.map((project) => (
              <div key={project.id} className="magnetic-card group">
                <div className="flex items-start justify-between mb-2">
                  <div>
                    <h3 className="font-medium text-white">{project.name}</h3>
                    <p className="text-sm text-surface-400">{project.path}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {project.urls && project.urls.length > 0 && (
                      <a
                        href={project.urls[0]}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="magnetic-button-primary px-3 py-1 text-xs flex items-center gap-1"
                        title="Open application"
                      >
                        <ExternalLink className="w-3 h-3" />
                        Open
                      </a>
                    )}
                    <button
                      onClick={() => handleScan(project.id)}
                      disabled={scanning === project.id}
                      className="text-surface-400 hover:text-primary transition-colors"
                      title="Rescan project"
                    >
                      {scanning === project.id ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <Search className="w-4 h-4" />
                      )}
                    </button>
                    <button
                      onClick={() => handleDelete(project.id)}
                      className="opacity-0 group-hover:opacity-100 text-surface-400 hover:text-error transition-opacity"
                      title="Delete project"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                {project.description && (
                  <p className="text-sm text-surface-300 mb-3">{project.description}</p>
                )}

                {project.tech_stack && project.tech_stack.length > 0 && (
                  <div className="mb-3">
                    <span className="text-xs text-surface-400 mb-1 block">Tech Stack:</span>
                    <div className="flex flex-wrap gap-2">
                      {project.tech_stack.map((tech) => (
                        <span
                          key={tech}
                          className="px-2 py-1 text-xs bg-primary/20 text-primary rounded"
                        >
                          {tech}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {project.urls && project.urls.length > 0 && (
                  <div className="mb-3">
                    <span className="text-xs text-surface-400 mb-1 block">URLs:</span>
                    <div className="space-y-1">
                      {project.urls.slice(0, 3).map((url) => (
                        <a
                          key={url}
                          href={url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="flex items-center gap-1 text-xs text-primary hover:underline"
                        >
                          <ExternalLink className="w-3 h-3" />
                          {url}
                        </a>
                      ))}
                    </div>
                  </div>
                )}

                {project.last_scanned && (
                  <div className="text-xs text-surface-400 pt-2 border-t border-surface-600">
                    Last scanned: {new Date(project.last_scanned).toLocaleString()}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Chat Panel */}
      <div className="w-96 flex flex-col">
        <h2 className="text-lg font-medium text-white mb-3">Project Assistant</h2>
        <div className="flex-1 min-h-0">
          <ChatPanel
            sessionId={sessionId}
            context="projects"
            placeholder="Ask about projects, tech stacks, or code..."
          />
        </div>
      </div>
    </div>
  )
}
