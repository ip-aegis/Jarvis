import { useState, useEffect, useCallback } from 'react'
import { Cpu, Activity, HardDrive, Thermometer, Wifi, WifiOff, Zap, Server, Gauge } from 'lucide-react'
import {
  LineChart,
  Line,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from 'recharts'
import { api } from '../services/api'

// Alpha server ID (from database)
const ALPHA_SERVER_ID = 3
const REFRESH_INTERVAL = 2000 // 2 seconds
const HISTORY_LENGTH = 60 // 2 minutes of data at 2s intervals

interface AlphaMetrics {
  server_id: number
  hostname: string
  status: string
  cpu: {
    usage: number | null
    cores: number
    per_core: Record<string, number>
  }
  memory: {
    used: number | null
    total: number | null
    percent: number | null
    available: number | null
    buffers: number | null
    cached: number | null
  }
  swap: {
    used: number | null
    total: number | null
  }
  disk: {
    used: number | null
    total: number | null
    percent: number | null
  }
  gpu: {
    utilization: number | null
    memory_used: number | null
    memory_total: number | null
    memory_percent: number | null
    temperature: number | null
    power: number | null
  } | null
  load_avg: {
    '1m': number | null
    '5m': number | null
    '15m': number | null
  }
  temperatures: Record<string, number>
  last_updated: string | null
}

interface HistoryPoint {
  time: string
  [key: string]: number | string | null
}

export default function Alpha() {
  const [metrics, setMetrics] = useState<AlphaMetrics | null>(null)
  const [connected, setConnected] = useState(false)
  const [cpuHistory, setCpuHistory] = useState<HistoryPoint[]>([])
  const [gpuHistory, setGpuHistory] = useState<HistoryPoint[]>([])
  const [memoryHistory, setMemoryHistory] = useState<HistoryPoint[]>([])
  const [error, setError] = useState<string | null>(null)

  const fetchMetrics = useCallback(async () => {
    try {
      const data = await api.getServerMetrics(ALPHA_SERVER_ID)
      setMetrics(data)
      setConnected(true)
      setError(null)

      const now = new Date().toLocaleTimeString()

      // Update CPU history (overall usage only)
      if (data.cpu?.usage !== null) {
        setCpuHistory((prev) => {
          const point: HistoryPoint = { time: now, overall: data.cpu.usage }
          return [...prev, point].slice(-HISTORY_LENGTH)
        })
      }

      // Update GPU history
      if (data.gpu) {
        setGpuHistory((prev) => {
          const point: HistoryPoint = {
            time: now,
            utilization: data.gpu?.utilization ?? null,
            memory: data.gpu?.memory_percent ?? null,
            temperature: data.gpu?.temperature ?? null,
            power: data.gpu?.power ?? null,
          }
          return [...prev, point].slice(-HISTORY_LENGTH)
        })
      }

      // Update memory history (utilization only)
      if (data.memory?.percent !== null) {
        setMemoryHistory((prev) => {
          const point: HistoryPoint = { time: now, percent: data.memory.percent }
          return [...prev, point].slice(-HISTORY_LENGTH)
        })
      }
    } catch (err) {
      console.error('Failed to fetch Alpha metrics:', err)
      setConnected(false)
      setError('Failed to connect to Alpha')
    }
  }, [])

  useEffect(() => {
    fetchMetrics()
    const interval = setInterval(fetchMetrics, REFRESH_INTERVAL)
    return () => clearInterval(interval)
  }, [fetchMetrics])

  const formatBytes = (bytes: number | null) => {
    if (bytes === null) return '--'
    const gb = bytes / (1024 * 1024 * 1024)
    return `${gb.toFixed(1)} GB`
  }

  const coreNames = metrics?.cpu?.per_core ? Object.keys(metrics.cpu.per_core).sort() : []

  return (
    <div className="h-full overflow-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Server className="w-8 h-8 text-primary" />
          <div>
            <h1 className="text-2xl font-semibold text-white">Alpha Server Monitor</h1>
            <p className="text-surface-300 mt-1">LLM Host &amp; VM Server - 10.10.20.62</p>
          </div>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-surface-400 text-sm">
            {REFRESH_INTERVAL / 1000}s refresh
          </span>
          <span
            className={`flex items-center gap-1 text-xs px-3 py-1.5 rounded-full ${
              connected ? 'bg-success/20 text-success' : 'bg-error/20 text-error'
            }`}
          >
            {connected ? <Wifi className="w-3 h-3" /> : <WifiOff className="w-3 h-3" />}
            {connected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {error && (
        <div className="bg-error/20 border border-error rounded-magnetic p-4 text-error">
          {error}
        </div>
      )}

      {/* Quick Stats Row */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <QuickStat
          icon={Cpu}
          label="CPU"
          value={metrics?.cpu?.usage?.toFixed(1) ?? '--'}
          unit="%"
          color="text-primary"
        />
        <QuickStat
          icon={Activity}
          label="Memory"
          value={metrics?.memory?.percent?.toFixed(1) ?? '--'}
          unit="%"
          color="text-success"
        />
        <QuickStat
          icon={Zap}
          label="GPU"
          value={metrics?.gpu?.utilization?.toFixed(0) ?? '--'}
          unit="%"
          color="text-warning"
        />
        <QuickStat
          icon={Thermometer}
          label="GPU Temp"
          value={metrics?.gpu?.temperature?.toFixed(0) ?? '--'}
          unit="°C"
          color={
            (metrics?.gpu?.temperature ?? 0) > 80
              ? 'text-error'
              : (metrics?.gpu?.temperature ?? 0) > 60
              ? 'text-warning'
              : 'text-success'
          }
        />
        <QuickStat
          icon={Zap}
          label="GPU Power"
          value={metrics?.gpu?.power?.toFixed(0) ?? '--'}
          unit="W"
          color="text-primary"
        />
        <QuickStat
          icon={HardDrive}
          label="Disk"
          value={metrics?.disk?.percent?.toFixed(1) ?? '--'}
          unit="%"
          color="text-surface-300"
        />
      </div>

      {/* CPU Usage Chart */}
      <div className="magnetic-card">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-medium text-white flex items-center gap-2">
            <Cpu className="w-5 h-5 text-primary" />
            CPU Usage ({coreNames.length} cores)
          </h2>
          <span className="text-surface-400 text-sm">{cpuHistory.length} samples</span>
        </div>
        <div className="h-48">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={cpuHistory}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
              <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={10} />
              <Tooltip
                contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                labelStyle={{ color: '#9CA3AF' }}
                formatter={(value: number) => [`${value?.toFixed(1)}%`, 'CPU']}
              />
              <Area
                type="monotone"
                dataKey="overall"
                stroke="#00bceb"
                fill="#00bceb"
                fillOpacity={0.3}
                strokeWidth={2}
              />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* GPU Metrics - 2x2 Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* GPU Utilization */}
        <div className="magnetic-card">
          <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-warning" />
            GPU Utilization
          </h3>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={gpuHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                />
                <Line type="monotone" dataKey="utilization" stroke="#ffcc00" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* GPU VRAM */}
        <div className="magnetic-card">
          <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-primary" />
            GPU VRAM ({formatBytes(metrics?.gpu?.memory_used ?? null)} / {formatBytes(metrics?.gpu?.memory_total ?? null)})
          </h3>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={gpuHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                />
                <Line type="monotone" dataKey="memory" stroke="#00bceb" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* GPU Temperature */}
        <div className="magnetic-card">
          <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
            <Thermometer className="w-4 h-4 text-error" />
            GPU Temperature
          </h3>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={gpuHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                />
                <Line type="monotone" dataKey="temperature" stroke="#cf2030" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* GPU Power */}
        <div className="magnetic-card">
          <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
            <Zap className="w-4 h-4 text-success" />
            GPU Power Draw
          </h3>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={gpuHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                <YAxis stroke="#9CA3AF" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                  formatter={(value: number) => [`${value?.toFixed(0) ?? '--'} W`, 'Power']}
                />
                <Line type="monotone" dataKey="power" stroke="#6cc04a" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Memory & System Row */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Memory Usage */}
        <div className="magnetic-card">
          <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4 text-success" />
            Memory Usage ({formatBytes(metrics?.memory?.total ?? null)} total)
          </h3>
          <div className="h-40">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={memoryHistory}>
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
                <XAxis dataKey="time" stroke="#9CA3AF" fontSize={10} />
                <YAxis domain={[0, 100]} stroke="#9CA3AF" fontSize={10} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1F2937', border: 'none', borderRadius: '8px' }}
                  formatter={(value: number) => [`${value?.toFixed(1)}%`, 'Memory']}
                />
                <Area
                  type="monotone"
                  dataKey="percent"
                  stroke="#6cc04a"
                  fill="#6cc04a"
                  fillOpacity={0.3}
                  strokeWidth={2}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Load Averages */}
        <div className="magnetic-card">
          <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
            <Gauge className="w-4 h-4 text-primary" />
            System Load Averages
          </h3>
          <div className="grid grid-cols-3 gap-4 h-40 items-center">
            <LoadGauge label="1 min" value={metrics?.load_avg?.['1m']} cores={coreNames.length} />
            <LoadGauge label="5 min" value={metrics?.load_avg?.['5m']} cores={coreNames.length} />
            <LoadGauge label="15 min" value={metrics?.load_avg?.['15m']} cores={coreNames.length} />
          </div>
        </div>
      </div>

      {/* Temperatures */}
      <div className="magnetic-card">
        <h3 className="text-md font-medium text-white mb-3 flex items-center gap-2">
          <Thermometer className="w-4 h-4 text-warning" />
          System Temperatures
        </h3>
        <div className="flex flex-wrap gap-3">
          {metrics?.temperatures && Object.keys(metrics.temperatures).length > 0 ? (
            Object.entries(metrics.temperatures).map(([name, temp]) => (
              <TempBadge key={name} name={name} temp={temp} />
            ))
          ) : (
            <span className="text-surface-400 text-sm">No temperature sensors available</span>
          )}
          {metrics?.gpu?.temperature && (
            <TempBadge name="GPU" temp={metrics.gpu.temperature} />
          )}
        </div>
      </div>
    </div>
  )
}

interface QuickStatProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  unit: string
  color: string
}

function QuickStat({ icon: Icon, label, value, unit, color }: QuickStatProps) {
  return (
    <div className="magnetic-card flex items-center gap-3">
      <Icon className={`w-6 h-6 ${color}`} />
      <div>
        <div className="text-surface-400 text-xs">{label}</div>
        <div className="flex items-baseline gap-1">
          <span className="text-xl font-semibold text-white">{value}</span>
          <span className="text-surface-400 text-sm">{unit}</span>
        </div>
      </div>
    </div>
  )
}

interface LoadGaugeProps {
  label: string
  value: number | null | undefined
  cores: number
}

function LoadGauge({ label, value, cores }: LoadGaugeProps) {
  const numValue = value ?? 0
  const percentage = cores > 0 ? (numValue / cores) * 100 : 0
  const color = percentage > 100 ? 'text-error' : percentage > 75 ? 'text-warning' : 'text-success'

  return (
    <div className="text-center">
      <div className="text-surface-400 text-sm mb-2">{label}</div>
      <div className={`text-3xl font-bold ${color}`}>{numValue.toFixed(2)}</div>
      <div className="text-surface-500 text-xs mt-1">
        {percentage.toFixed(0)}% of {cores} cores
      </div>
    </div>
  )
}

interface TempBadgeProps {
  name: string
  temp: number
}

function TempBadge({ name, temp }: TempBadgeProps) {
  const color =
    temp > 80 ? 'bg-error/20 text-error border-error' :
    temp > 60 ? 'bg-warning/20 text-warning border-warning' :
    'bg-success/20 text-success border-success'

  return (
    <div className={`px-3 py-2 rounded-magnetic border ${color}`}>
      <span className="text-surface-300 text-sm">{name}:</span>{' '}
      <span className="font-semibold">{temp.toFixed(0)}°C</span>
    </div>
  )
}
