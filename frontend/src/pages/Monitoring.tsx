import { useState, useEffect } from 'react'
import { Activity, Cpu, HardDrive, Thermometer, Wifi, WifiOff, Zap } from 'lucide-react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'
import ChatPanel from '../components/chat/ChatPanel'
import { useWebSocket } from '../hooks/useWebSocket'
import { api } from '../services/api'

interface ServerMetric {
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

interface HistoryPoint {
  timestamp: string
  value: number
}

export default function Monitoring() {
  const [sessionId] = useState(() => `monitoring-${Date.now()}`)
  const [serverMetrics, setServerMetrics] = useState<ServerMetric[]>([])
  const [selectedServer, setSelectedServer] = useState<number | null>(null)
  const [cpuHistory, setCpuHistory] = useState<HistoryPoint[]>([])

  const { connected } = useWebSocket({
    onMessage: (data) => {
      // Update server metrics in real-time
      setServerMetrics((prev) =>
        prev.map((s) =>
          s.server_id === data.server_id
            ? {
                ...s,
                cpu_usage: data.cpu_usage,
                memory_percent: data.memory_percent,
                disk_percent: data.disk_percent,
                gpu_utilization: data.gpu_utilization,
                gpu_temperature: data.gpu_temperature,
                last_updated: data.timestamp,
                status: 'online',
              }
            : s
        )
      )
      // Add to history if it's the selected server
      if (selectedServer === data.server_id && data.cpu_usage !== null) {
        setCpuHistory((prev) => {
          const newPoint = {
            timestamp: new Date(data.timestamp).toLocaleTimeString(),
            value: data.cpu_usage!,
          }
          // Keep last 60 data points
          const updated = [...prev, newPoint].slice(-60)
          return updated
        })
      }
    },
  })

  useEffect(() => {
    fetchMetrics() // Initial fetch

    // Only poll if WebSocket is disconnected
    let interval: NodeJS.Timeout | null = null
    if (!connected) {
      interval = setInterval(fetchMetrics, 30000) // Refresh every 30s when disconnected
    }

    return () => {
      if (interval) clearInterval(interval)
    }
  }, [connected]) // Re-run when connection status changes

  const fetchMetrics = async () => {
    try {
      const data = await api.getMetrics()
      setServerMetrics(data.metrics)
      if (data.metrics.length > 0 && !selectedServer) {
        setSelectedServer(data.metrics[0].server_id)
      }
    } catch (err) {
      console.error('Failed to fetch metrics:', err)
    }
  }

  // Calculate aggregated metrics across all servers
  const avgCpu =
    serverMetrics.length > 0
      ? serverMetrics.reduce((sum, s) => sum + (s.cpu_usage || 0), 0) / serverMetrics.length
      : null
  const avgMemory =
    serverMetrics.length > 0
      ? serverMetrics.reduce((sum, s) => sum + (s.memory_percent || 0), 0) / serverMetrics.length
      : null
  const avgDisk =
    serverMetrics.length > 0
      ? serverMetrics.reduce((sum, s) => sum + (s.disk_percent || 0), 0) / serverMetrics.length
      : null
  const gpuServer = serverMetrics.find((s) => s.gpu_utilization !== null)

  return (
    <div className="h-full flex gap-6">
      {/* Main monitoring area */}
      <div className="flex-1 space-y-6 overflow-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Monitoring</h1>
            <p className="text-surface-300 mt-1">Real-time server metrics</p>
          </div>
          <div className="flex items-center gap-2">
            <span
              className={`flex items-center gap-1 text-xs px-2 py-1 rounded-full ${
                connected ? 'bg-success/20 text-success' : 'bg-error/20 text-error'
              }`}
              role="status"
              aria-live="polite"
            >
              {connected ? (
                <Wifi className="w-3 h-3" aria-hidden="true" />
              ) : (
                <WifiOff className="w-3 h-3" aria-hidden="true" />
              )}
              <span>{connected ? 'Live' : 'Disconnected'}</span>
              <span className="sr-only">
                {connected ? 'Real-time updates active' : 'Connection lost, polling for updates'}
              </span>
            </span>
          </div>
        </div>

        {/* Metrics Overview */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            icon={Cpu}
            label="Avg CPU"
            value={avgCpu !== null ? avgCpu.toFixed(1) : '--'}
            unit="%"
            color="text-primary"
            progress={avgCpu}
          />
          <MetricCard
            icon={Activity}
            label="Avg Memory"
            value={avgMemory !== null ? avgMemory.toFixed(1) : '--'}
            unit="%"
            color="text-success"
            progress={avgMemory}
          />
          <MetricCard
            icon={HardDrive}
            label="Avg Disk"
            value={avgDisk !== null ? avgDisk.toFixed(1) : '--'}
            unit="%"
            color="text-warning"
            progress={avgDisk}
          />
          <MetricCard
            icon={Thermometer}
            label="GPU Temp"
            value={gpuServer?.gpu_temperature?.toFixed(0) || '--'}
            unit="°C"
            color="text-error"
          />
        </div>

        {/* CPU History Chart */}
        {cpuHistory.length > 0 && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4">CPU Usage History</h2>
            <div className="h-48">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={cpuHistory}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                  <XAxis dataKey="timestamp" stroke="#9CA3AF" fontSize={10} />
                  <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={10} />
                  <Tooltip
                    contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                    labelStyle={{ color: '#9CA3AF' }}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke="#00bceb"
                    strokeWidth={2}
                    dot={false}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* Server List */}
        <div className="magnetic-card">
          <h2 className="text-lg font-medium text-white mb-4">Server Status</h2>
          {serverMetrics.length === 0 ? (
            <div className="text-surface-300 text-sm">
              No servers connected. Add a server from the Servers page.
            </div>
          ) : (
            <div className="space-y-3">
              {serverMetrics.map((server) => (
                <div
                  key={server.server_id}
                  onClick={() => setSelectedServer(server.server_id)}
                  className={`p-3 rounded-magnetic cursor-pointer transition-colors ${
                    selectedServer === server.server_id
                      ? 'bg-primary/20 border border-primary'
                      : 'bg-surface-600 hover:bg-surface-500'
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      {server.status === 'online' ? (
                        <>
                          <Wifi className="w-4 h-4 text-success" aria-hidden="true" />
                          <span className="sr-only">Online</span>
                        </>
                      ) : (
                        <>
                          <WifiOff className="w-4 h-4 text-error" aria-hidden="true" />
                          <span className="sr-only">Offline</span>
                        </>
                      )}
                      <span className="font-medium text-white">{server.hostname}</span>
                      <span className="text-xs text-surface-400">{server.ip_address}</span>
                    </div>
                    {server.last_updated && (
                      <span className="text-xs text-surface-400">
                        {new Date(server.last_updated).toLocaleTimeString()}
                      </span>
                    )}
                  </div>
                  <div className="grid grid-cols-4 gap-4 text-sm">
                    <div>
                      <span className="text-surface-400">CPU:</span>{' '}
                      <span className="text-white">
                        {server.cpu_usage?.toFixed(1) || '--'}%
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-400">Mem:</span>{' '}
                      <span className="text-white">
                        {server.memory_percent?.toFixed(1) || '--'}%
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-400">Disk:</span>{' '}
                      <span className="text-white">
                        {server.disk_percent?.toFixed(1) || '--'}%
                      </span>
                    </div>
                    <div>
                      <span className="text-surface-400">GPU:</span>{' '}
                      <span className="text-primary">
                        {server.gpu_utilization?.toFixed(0) || '--'}%
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* GPU Metrics (for Alpha) */}
        {gpuServer && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-primary" />
              GPU Metrics - {gpuServer.hostname}
            </h2>
            <div className="grid grid-cols-3 gap-4">
              <div className="bg-surface-600 rounded-magnetic p-4">
                <div className="text-surface-400 text-sm mb-1">Utilization</div>
                <div className="text-2xl font-semibold text-primary">
                  {gpuServer.gpu_utilization?.toFixed(0) || '--'}%
                </div>
              </div>
              <div className="bg-surface-600 rounded-magnetic p-4">
                <div className="text-surface-400 text-sm mb-1">Temperature</div>
                <div className="text-2xl font-semibold text-warning">
                  {gpuServer.gpu_temperature?.toFixed(0) || '--'}°C
                </div>
              </div>
              <div className="bg-surface-600 rounded-magnetic p-4">
                <div className="text-surface-400 text-sm mb-1">Status</div>
                <div className="text-2xl font-semibold text-success">Active</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Chat Panel */}
      <div className="w-96 flex flex-col">
        <h2 className="text-lg font-medium text-white mb-3">Monitoring Assistant</h2>
        <div className="flex-1 min-h-0">
          <ChatPanel
            sessionId={sessionId}
            context="monitoring"
            placeholder="Ask about server status, metrics, or alerts..."
          />
        </div>
      </div>
    </div>
  )
}

interface MetricCardProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  unit: string
  color: string
  progress?: number | null
}

function MetricCard({ icon: Icon, label, value, unit, color, progress }: MetricCardProps) {
  return (
    <div className="magnetic-card">
      <div className="flex items-center gap-3 mb-2">
        <Icon className={`w-5 h-5 ${color}`} />
        <span className="text-surface-300 text-sm">{label}</span>
      </div>
      <div className="flex items-baseline gap-1 mb-2">
        <span className="text-2xl font-semibold text-white">{value}</span>
        <span className="text-surface-400 text-sm">{unit}</span>
      </div>
      {progress !== undefined && progress !== null && (
        <div className="w-full bg-surface-600 rounded-full h-1.5">
          <div
            className={`h-1.5 rounded-full ${
              progress > 80 ? 'bg-error' : progress > 60 ? 'bg-warning' : 'bg-success'
            }`}
            style={{ width: `${Math.min(progress, 100)}%` }}
          />
        </div>
      )}
    </div>
  )
}
