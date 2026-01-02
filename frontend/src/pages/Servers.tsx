import { useState, useEffect } from 'react'
import { Plus, Server, Wifi, WifiOff, RefreshCw, Trash2 } from 'lucide-react'
import OnboardingWizard from '../components/servers/OnboardingWizard'
import { api, Server as ServerType } from '../services/api'

interface ServerInfo {
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
  agent_installed?: boolean
}

export default function Servers() {
  const [showWizard, setShowWizard] = useState(false)
  const [servers, setServers] = useState<ServerInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchServers = async () => {
    try {
      setLoading(true)
      setError(null)
      const data = await api.listServers()
      setServers(data as ServerInfo[])
    } catch (err: any) {
      setError(err.message || 'Failed to fetch servers')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchServers()
  }, [])

  const handleServerAdded = () => {
    setShowWizard(false)
    fetchServers()
  }

  const handleDeleteServer = async (serverId: number) => {
    if (!confirm('Are you sure you want to remove this server?')) return
    try {
      await api.deleteServer(serverId)
      fetchServers()
    } catch (err: any) {
      setError(err.message || 'Failed to delete server')
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Servers</h1>
          <p className="text-surface-300 mt-1">Manage monitored servers</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={fetchServers}
            className="magnetic-button-secondary p-2"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>
          <button
            onClick={() => setShowWizard(true)}
            className="magnetic-button-primary flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Add Server
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3 bg-error/20 border border-error rounded-magnetic text-error text-sm">
          {error}
        </div>
      )}

      {showWizard && (
        <OnboardingWizard
          onClose={() => setShowWizard(false)}
          onComplete={handleServerAdded}
        />
      )}

      {loading && servers.length === 0 ? (
        <div className="magnetic-card text-center py-12">
          <RefreshCw className="w-8 h-8 text-surface-400 mx-auto mb-4 animate-spin" />
          <p className="text-surface-300">Loading servers...</p>
        </div>
      ) : servers.length === 0 ? (
        <div className="magnetic-card text-center py-12">
          <Server className="w-12 h-12 text-surface-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-white mb-2">No servers yet</h3>
          <p className="text-surface-300 mb-4">
            Add your first server to start monitoring
          </p>
          <button
            onClick={() => setShowWizard(true)}
            className="magnetic-button-primary"
          >
            Add Server
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {servers.map((server) => (
            <div key={server.id} className="magnetic-card group">
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="font-medium text-white">{server.hostname}</h3>
                  <p className="text-sm text-surface-300">{server.ip_address}</p>
                </div>
                <div className="flex items-center gap-2">
                  {server.status === 'online' ? (
                    <Wifi className="w-5 h-5 text-success" />
                  ) : (
                    <WifiOff className="w-5 h-5 text-error" />
                  )}
                  <button
                    onClick={() => handleDeleteServer(server.id)}
                    className="opacity-0 group-hover:opacity-100 text-surface-400 hover:text-error transition-opacity"
                    title="Remove server"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="space-y-1 text-xs">
                {server.os_info && (
                  <p className="text-surface-400 truncate" title={server.os_info}>
                    {server.os_info.split('\n')[0]}
                  </p>
                )}
                {server.cpu_info && (
                  <p className="text-surface-400">
                    {server.cpu_info} ({server.cpu_cores} cores)
                  </p>
                )}
                {server.memory_total && (
                  <p className="text-surface-400">RAM: {server.memory_total}</p>
                )}
                {server.gpu_info && (
                  <p className="text-primary">{server.gpu_info}</p>
                )}
              </div>
              <div className="mt-3 pt-3 border-t border-surface-600 flex items-center justify-between">
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    server.agent_installed
                      ? 'bg-success/20 text-success'
                      : 'bg-surface-600 text-surface-400'
                  }`}
                >
                  {server.agent_installed ? 'Agent Active' : 'No Agent'}
                </span>
                <span
                  className={`text-xs px-2 py-1 rounded-full ${
                    server.status === 'online'
                      ? 'bg-success/20 text-success'
                      : 'bg-error/20 text-error'
                  }`}
                >
                  {server.status}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
