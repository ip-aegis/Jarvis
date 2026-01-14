import { useState, useEffect } from 'react'
import {
  Home as HomeIcon,
  Thermometer,
  Bell,
  Camera,
  Tv,
  Speaker,
  Droplets,
  RefreshCw,
  AlertCircle,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Plus,
  Minus,
  Settings,
  Check,
  Wifi,
  WifiOff,
  Volume2,
  VolumeX,
  Power,
  Zap,
  ChevronUp,
  ChevronDown,
  X,
  Video,
  Film,
} from 'lucide-react'
import ChatPanel from '../components/chat/ChatPanel'
import { api } from '../services/api'
import type {
  HomeDevice,
  HomeEvent,
  HomePlatformStatus,
  ThermostatState,
  MediaPlayerState,
  ApplianceState,
} from '../types'

type DeviceTypeFilter = 'all' | 'doorbell' | 'camera' | 'chime' | 'thermostat' | 'washer' | 'dishwasher' | 'apple_tv' | 'homepod'

interface ActionFeedback {
  message: string
  type: 'success' | 'error'
  deviceId?: number
}

interface MediaItem {
  id: string
  url: string
  created_at: string
  type: string
}

interface MediaViewer {
  deviceName: string
  mediaUrl?: string
  recordings?: MediaItem[]
}

interface LiveSnapshot {
  deviceId: number
  deviceName: string
  filename: string
  timestamp: string
}

export default function Home() {
  const [sessionId] = useState(() => `home-${Date.now()}`)
  const [devices, setDevices] = useState<HomeDevice[]>([])
  const [events, setEvents] = useState<HomeEvent[]>([])
  const [platforms, setPlatforms] = useState<HomePlatformStatus[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<DeviceTypeFilter>('all')
  const [actionFeedback, setActionFeedback] = useState<ActionFeedback | null>(null)
  const [actionLoading, setActionLoading] = useState<number | null>(null)
  const [mediaViewer, setMediaViewer] = useState<MediaViewer | null>(null)
  const [recordingsLoading, setRecordingsLoading] = useState<number | null>(null)
  const [liveSnapshots, setLiveSnapshots] = useState<Map<number, LiveSnapshot>>(new Map())
  const [snapshotLoading, setSnapshotLoading] = useState<number | null>(null)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const fetchData = async () => {
    try {
      setLoading(true)
      const [devicesData, eventsData, platformsData] = await Promise.all([
        api.listHomeDevices(),
        api.listHomeEvents({ limit: 10, unacknowledged_only: true }),
        api.listHomePlatforms(),
      ])
      setDevices(devicesData.devices)
      setEvents(eventsData.events)
      setPlatforms(platformsData)
    } catch (err) {
      console.error('Failed to fetch home data:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleDeviceAction = async (deviceId: number, action: string, params: Record<string, unknown> = {}) => {
    setActionLoading(deviceId)
    setActionFeedback(null)
    try {
      const result = await api.executeHomeDeviceAction(deviceId, { action, params })
      // Refresh device state
      const device = await api.getHomeDevice(deviceId, true)
      setDevices((prev) => prev.map((d) => (d.id === deviceId ? device : d)))

      if (result.success) {
        // Check if media was returned
        if (result.snapshot_url) {
          setMediaViewer({
            deviceName: device.name,
            mediaUrl: result.snapshot_url,
          })
        } else if (result.recordings && result.recordings.length > 0) {
          setMediaViewer({
            deviceName: device.name,
            recordings: result.recordings,
          })
        } else {
          setActionFeedback({ message: `${action} successful`, type: 'success', deviceId })
        }
      } else {
        setActionFeedback({ message: result.error || `${action} failed`, type: 'error', deviceId })
      }
    } catch (err) {
      console.error('Failed to execute action:', err)
      setActionFeedback({ message: `Failed to ${action}`, type: 'error', deviceId })
    } finally {
      setActionLoading(null)
      // Auto-dismiss feedback after 3 seconds
      setTimeout(() => setActionFeedback(null), 3000)
    }
  }

  const handleGetRecordings = async (deviceId: number, deviceName: string) => {
    setRecordingsLoading(deviceId)
    try {
      const result = await api.executeHomeDeviceAction(deviceId, {
        action: 'get_recordings',
        params: { limit: 10 },
      })
      if (result.success && result.recordings) {
        setMediaViewer({
          deviceName,
          recordings: result.recordings,
        })
      } else {
        setActionFeedback({
          message: result.error || 'No recordings found',
          type: 'error',
          deviceId,
        })
        setTimeout(() => setActionFeedback(null), 3000)
      }
    } catch (err) {
      console.error('Failed to get recordings:', err)
      setActionFeedback({ message: 'Failed to get recordings', type: 'error', deviceId })
      setTimeout(() => setActionFeedback(null), 3000)
    } finally {
      setRecordingsLoading(null)
    }
  }

  const handleGetLiveSnapshot = async (deviceId: number, deviceName: string) => {
    setSnapshotLoading(deviceId)
    try {
      const result = await api.executeHomeDeviceAction(deviceId, {
        action: 'get_live_snapshot',
        params: {},
      })
      if (result.success && result.filename) {
        const snapshot: LiveSnapshot = {
          deviceId,
          deviceName: result.device_name || deviceName,
          filename: result.filename,
          timestamp: result.timestamp || new Date().toISOString(),
        }
        setLiveSnapshots((prev) => {
          const newMap = new Map(prev)
          newMap.set(deviceId, snapshot)
          return newMap
        })
        setActionFeedback({
          message: `Snapshot captured from ${deviceName}`,
          type: 'success',
          deviceId,
        })
        setTimeout(() => setActionFeedback(null), 3000)
      } else {
        setActionFeedback({
          message: result.error || 'Failed to get snapshot',
          type: 'error',
          deviceId,
        })
        setTimeout(() => setActionFeedback(null), 3000)
      }
    } catch (err) {
      console.error('Failed to get live snapshot:', err)
      setActionFeedback({ message: 'Failed to get snapshot', type: 'error', deviceId })
      setTimeout(() => setActionFeedback(null), 3000)
    } finally {
      setSnapshotLoading(null)
    }
  }

  const handleMediaAction = async (deviceId: number, action: string) => {
    await handleDeviceAction(deviceId, action)
  }

  const handleThermostatAdjust = async (deviceId: number, delta: number) => {
    const device = devices.find(d => d.id === deviceId)
    if (!device) return
    const currentTemp = (device.state as ThermostatState)?.target_temperature || 70
    const newTemp = currentTemp + delta
    await handleDeviceAction(deviceId, 'set_temperature', { temperature: newTemp })
  }

  const handleVolumeChange = async (deviceId: number, direction: 'up' | 'down') => {
    await handleDeviceAction(deviceId, direction === 'up' ? 'volume_up' : 'volume_down')
  }

  const handleAcknowledgeEvent = async (eventId: string) => {
    try {
      await api.acknowledgeHomeEvent(eventId)
      setEvents((prev) => prev.filter((e) => e.event_id !== eventId))
    } catch (err) {
      console.error('Failed to acknowledge event:', err)
    }
  }

  const onlineCount = devices.filter((d) => d.status === 'online').length
  const offlineCount = devices.filter((d) => d.status === 'offline').length
  const connectedPlatforms = platforms.filter((p) => p.connected).length

  // Group devices by type
  const thermostat = devices.find((d) => d.device_type === 'thermostat')
  const doorbells = devices.filter((d) => d.device_type === 'doorbell')
  const cameras = devices.filter((d) => d.device_type === 'camera')
  const chimes = devices.filter((d) => d.device_type === 'chime')
  const appliances = devices.filter((d) => ['washer', 'dishwasher'].includes(d.device_type))
  const mediaDevices = devices.filter((d) => ['apple_tv', 'homepod'].includes(d.device_type))

  const getDeviceIcon = (type: string) => {
    switch (type) {
      case 'doorbell':
        return Bell
      case 'camera':
        return Camera
      case 'chime':
        return Volume2
      case 'thermostat':
        return Thermometer
      case 'washer':
      case 'dishwasher':
        return Droplets
      case 'apple_tv':
        return Tv
      case 'homepod':
        return Speaker
      default:
        return HomeIcon
    }
  }

  return (
    <div className="h-full flex gap-6">
      {/* Main content area */}
      <div className="flex-1 space-y-6 overflow-auto">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Home</h1>
            <p className="text-surface-300 mt-1">Smart home control center</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchData}
              className="magnetic-button-secondary flex items-center gap-2"
              title="Refresh devices"
            >
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Status cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <span className="text-surface-400 text-sm">Devices</span>
              <HomeIcon className="w-4 h-4 text-primary" />
            </div>
            <div className="text-2xl font-semibold text-white mt-1">{devices.length}</div>
          </div>
          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <span className="text-surface-400 text-sm">Online</span>
              <Wifi className="w-4 h-4 text-success" />
            </div>
            <div className="text-2xl font-semibold text-success mt-1">{onlineCount}</div>
          </div>
          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <span className="text-surface-400 text-sm">Offline</span>
              <WifiOff className="w-4 h-4 text-error" />
            </div>
            <div className="text-2xl font-semibold text-error mt-1">{offlineCount}</div>
          </div>
          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <span className="text-surface-400 text-sm">Platforms</span>
              <Settings className="w-4 h-4 text-primary" />
            </div>
            <div className="text-2xl font-semibold text-white mt-1">{connectedPlatforms}/{platforms.length}</div>
          </div>
        </div>

        {/* Action feedback toast */}
        {actionFeedback && (
          <div className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-magnetic shadow-lg flex items-center gap-2 transition-all ${
            actionFeedback.type === 'success' ? 'bg-success text-white' : 'bg-error text-white'
          }`}>
            {actionFeedback.type === 'success' ? (
              <Check className="w-4 h-4" />
            ) : (
              <AlertCircle className="w-4 h-4" />
            )}
            <span className="text-sm">{actionFeedback.message}</span>
          </div>
        )}

        {/* Filter tabs */}
        <div className="flex gap-2 flex-wrap">
          {(['all', 'doorbell', 'camera', 'chime', 'thermostat', 'washer', 'apple_tv', 'homepod'] as DeviceTypeFilter[]).map((type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-3 py-1.5 rounded-full text-sm capitalize transition-colors ${
                filter === type
                  ? 'bg-primary text-white'
                  : 'bg-surface-600 text-surface-300 hover:bg-surface-500'
              }`}
            >
              {type === 'all' ? 'All Devices' : type.replace('_', ' ')}
            </button>
          ))}
        </div>

        {/* Quick status - Thermostat */}
        {thermostat && (
          <div className="magnetic-card">
            <div className="flex items-center gap-3 mb-4">
              <Thermometer className="w-5 h-5 text-primary" />
              <span className="text-white font-medium">{thermostat.name}</span>
              <span className={`ml-auto px-2 py-0.5 rounded text-xs ${
                thermostat.status === 'online' ? 'bg-success/20 text-success' : 'bg-error/20 text-error'
              }`}>
                {thermostat.status}
              </span>
            </div>
            <div className="flex items-center gap-6">
              {/* Current temperature */}
              <div className="text-center">
                <div className="text-surface-400 text-xs mb-1">Current</div>
                <div>
                  <span className="text-3xl font-semibold text-white">
                    {(thermostat.state as ThermostatState)?.current_temperature ?? '--'}
                  </span>
                  <span className="text-surface-400 ml-1">°F</span>
                </div>
              </div>

              {/* Target temperature with controls */}
              <div className="text-center">
                <div className="text-surface-400 text-xs mb-1">Target</div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleThermostatAdjust(thermostat.id, -1)}
                    className="p-1.5 bg-surface-600 rounded-full text-white hover:bg-surface-500 transition-colors"
                    title="Decrease temperature"
                  >
                    <ChevronDown className="w-4 h-4" />
                  </button>
                  <span className="text-2xl font-semibold text-primary w-12 text-center">
                    {(thermostat.state as ThermostatState)?.target_temperature ?? '--'}
                  </span>
                  <button
                    onClick={() => handleThermostatAdjust(thermostat.id, 1)}
                    className="p-1.5 bg-surface-600 rounded-full text-white hover:bg-surface-500 transition-colors"
                    title="Increase temperature"
                  >
                    <ChevronUp className="w-4 h-4" />
                  </button>
                </div>
              </div>

              {/* Mode */}
              <div className="text-center">
                <div className="text-surface-400 text-xs mb-1">Mode</div>
                <div className="flex gap-1">
                  {['heat', 'cool', 'auto', 'off'].map((mode) => (
                    <button
                      key={mode}
                      onClick={() => handleDeviceAction(thermostat.id, 'set_mode', { mode })}
                      className={`px-2 py-1 rounded text-xs capitalize transition-colors ${
                        (thermostat.state as ThermostatState)?.mode === mode
                          ? 'bg-primary text-white'
                          : 'bg-surface-600 text-surface-300 hover:bg-surface-500'
                      }`}
                    >
                      {mode}
                    </button>
                  ))}
                </div>
              </div>

              {/* Humidity */}
              {(thermostat.state as ThermostatState)?.humidity && (
                <div className="text-center">
                  <div className="text-surface-400 text-xs mb-1">Humidity</div>
                  <span className="text-lg text-white">
                    {(thermostat.state as ThermostatState)?.humidity}%
                  </span>
                </div>
              )}

              {/* HVAC State */}
              {(thermostat.state as ThermostatState)?.hvac_state && (
                <div className="text-center ml-auto">
                  <div className="text-surface-400 text-xs mb-1">Status</div>
                  <span className={`text-sm capitalize ${
                    (thermostat.state as ThermostatState)?.hvac_state === 'heating' ? 'text-warning' :
                    (thermostat.state as ThermostatState)?.hvac_state === 'cooling' ? 'text-info' :
                    'text-surface-400'
                  }`}>
                    {(thermostat.state as ThermostatState)?.hvac_state}
                  </span>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Doorbells & Cameras */}
        {(doorbells.length > 0 || cameras.length > 0) && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <Bell className="w-5 h-5 text-warning" />
              Security
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {[...doorbells, ...cameras].map((device) => {
                const Icon = getDeviceIcon(device.device_type)
                const state = device.state as Record<string, unknown> | undefined
                const batteryLevel = state?.battery_level as number | undefined
                const volume = state?.volume as number | undefined
                const isLoading = actionLoading === device.id
                return (
                  <div
                    key={device.id}
                    className={`p-4 bg-surface-600 rounded-magnetic transition-opacity ${isLoading ? 'opacity-70' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-primary" />
                        <span className="text-white font-medium">{device.name}</span>
                      </div>
                      <span className={`w-2 h-2 rounded-full ${
                        device.status === 'online' ? 'bg-success' : 'bg-error'
                      }`} />
                    </div>

                    {/* Device info */}
                    <div className="text-sm text-surface-400 space-y-1 mb-3">
                      {batteryLevel !== undefined && (
                        <div className="flex items-center gap-2">
                          <Zap className="w-3 h-3" />
                          <span>Battery: {batteryLevel}%</span>
                          <div className="flex-1 h-1.5 bg-surface-700 rounded-full overflow-hidden">
                            <div
                              className={`h-full transition-all ${
                                batteryLevel > 50 ? 'bg-success' :
                                batteryLevel > 20 ? 'bg-warning' : 'bg-error'
                              }`}
                              style={{ width: `${batteryLevel}%` }}
                            />
                          </div>
                        </div>
                      )}
                      {device.model && (
                        <div className="text-xs text-surface-500">{device.model}</div>
                      )}
                    </div>

                    {/* Live Snapshot Display */}
                    {liveSnapshots.has(device.id) && (
                      <div className="mb-3 relative">
                        <img
                          src={api.getSnapshotUrl(liveSnapshots.get(device.id)!.filename)}
                          alt={`Live snapshot from ${device.name}`}
                          className="w-full rounded-lg bg-black"
                        />
                        <div className="absolute bottom-2 left-2 flex items-center gap-1 bg-black/70 px-2 py-1 rounded text-xs text-white">
                          <div className="w-2 h-2 bg-success rounded-full animate-pulse" />
                          Live - {new Date(liveSnapshots.get(device.id)!.timestamp).toLocaleTimeString()}
                        </div>
                      </div>
                    )}

                    {/* Controls */}
                    <div className="flex flex-wrap items-center gap-2">
                      {/* Live Snapshot button */}
                      <button
                        onClick={() => handleGetLiveSnapshot(device.id, device.name)}
                        disabled={snapshotLoading === device.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-success/20 text-success rounded text-sm hover:bg-success/30 transition-colors disabled:opacity-50"
                        title="Capture live snapshot"
                      >
                        {snapshotLoading === device.id ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Camera className="w-3.5 h-3.5" />
                        )}
                        Live
                      </button>

                      {/* View recordings button */}
                      <button
                        onClick={() => handleGetRecordings(device.id, device.name)}
                        disabled={recordingsLoading === device.id}
                        className="flex items-center gap-1.5 px-3 py-1.5 bg-primary/20 text-primary rounded text-sm hover:bg-primary/30 transition-colors disabled:opacity-50"
                        title="View all recordings"
                      >
                        {recordingsLoading === device.id ? (
                          <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <Film className="w-3.5 h-3.5" />
                        )}
                        Recordings
                      </button>

                      {/* Volume control for doorbells */}
                      {device.device_type === 'doorbell' && volume !== undefined && (
                        <div className="flex items-center gap-1 ml-auto">
                          <button
                            onClick={() => handleDeviceAction(device.id, 'set_volume', { volume: Math.max(0, volume - 1) })}
                            disabled={isLoading}
                            className="p-1 bg-surface-500 rounded text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                            title="Volume down"
                          >
                            <VolumeX className="w-3.5 h-3.5" />
                          </button>
                          <span className="text-xs text-surface-400 w-6 text-center">{volume}</span>
                          <button
                            onClick={() => handleDeviceAction(device.id, 'set_volume', { volume: Math.min(10, volume + 1) })}
                            disabled={isLoading}
                            className="p-1 bg-surface-500 rounded text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                            title="Volume up"
                          >
                            <Volume2 className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Chimes */}
        {chimes.length > 0 && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <Volume2 className="w-5 h-5 text-primary" />
              Chimes
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {chimes.map((device) => {
                const state = device.state as Record<string, unknown> | undefined
                const volume = state?.volume as number | undefined
                const isLoading = actionLoading === device.id
                return (
                  <div
                    key={device.id}
                    className={`p-4 bg-surface-600 rounded-magnetic transition-opacity ${isLoading ? 'opacity-70' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Volume2 className="w-4 h-4 text-primary" />
                        <span className="text-white font-medium">{device.name}</span>
                      </div>
                      <span className={`w-2 h-2 rounded-full ${
                        device.status === 'online' ? 'bg-success' : 'bg-error'
                      }`} />
                    </div>

                    {/* Model info */}
                    {device.model && (
                      <div className="text-xs text-surface-500 mb-3">{device.model}</div>
                    )}

                    {/* Volume control */}
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-surface-400">Volume</span>
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleDeviceAction(device.id, 'set_volume', { volume: Math.max(0, (volume || 5) - 1) })}
                          disabled={isLoading}
                          className="p-1.5 bg-surface-500 rounded text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                          title="Volume down"
                        >
                          <Minus className="w-3.5 h-3.5" />
                        </button>
                        <span className="text-white font-medium w-8 text-center">{volume ?? '--'}</span>
                        <button
                          onClick={() => handleDeviceAction(device.id, 'set_volume', { volume: Math.min(10, (volume || 5) + 1) })}
                          disabled={isLoading}
                          className="p-1.5 bg-surface-500 rounded text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                          title="Volume up"
                        >
                          <Plus className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    </div>

                    {/* Loading indicator */}
                    {isLoading && (
                      <div className="mt-2 flex items-center justify-center">
                        <RefreshCw className="w-4 h-4 text-primary animate-spin" />
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Appliances */}
        {appliances.length > 0 && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <Droplets className="w-5 h-5 text-primary" />
              Appliances
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {appliances.map((device) => {
                const state = device.state as ApplianceState | undefined
                return (
                  <div
                    key={device.id}
                    className="p-4 bg-surface-600 rounded-magnetic"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <div className="flex items-center gap-2">
                        <Droplets className="w-4 h-4 text-primary" />
                        <span className="text-white font-medium">{device.name}</span>
                      </div>
                      <span className={`w-2 h-2 rounded-full ${
                        device.status === 'online' ? 'bg-success' : 'bg-error'
                      }`} />
                    </div>
                    <div className="text-white">
                      {state?.cycle_state || 'Idle'}
                    </div>
                    {state?.remaining_time && (
                      <div className="text-sm text-surface-400 mt-1">
                        {state.remaining_time} remaining
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Media devices */}
        {mediaDevices.length > 0 && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <Tv className="w-5 h-5 text-primary" />
              Media
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {mediaDevices.map((device) => {
                const state = device.state as MediaPlayerState | undefined
                const isPlaying = state?.playing
                const Icon = device.device_type === 'apple_tv' ? Tv : Speaker
                const isLoading = actionLoading === device.id
                return (
                  <div
                    key={device.id}
                    className={`p-4 bg-surface-600 rounded-magnetic transition-opacity ${isLoading ? 'opacity-70' : ''}`}
                  >
                    <div className="flex items-center justify-between mb-3">
                      <div className="flex items-center gap-2">
                        <Icon className="w-4 h-4 text-primary" />
                        <span className="text-white font-medium">{device.name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {state?.power === false && (
                          <span className="text-xs text-surface-400">Off</span>
                        )}
                        <span className={`w-2 h-2 rounded-full ${
                          device.status === 'online' ? 'bg-success' : 'bg-error'
                        }`} />
                      </div>
                    </div>

                    {/* Now playing info */}
                    {state?.title ? (
                      <div className="mb-3 p-2 bg-surface-700 rounded">
                        <div className="text-white truncate font-medium">{state.title}</div>
                        {state.artist && (
                          <div className="text-sm text-surface-400 truncate">
                            {state.artist}
                            {state.album && ` — ${state.album}`}
                          </div>
                        )}
                        {state.media_type && (
                          <div className="text-xs text-surface-500 mt-1 capitalize">
                            {state.media_type}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="mb-3 p-2 bg-surface-700 rounded text-surface-400 text-sm">
                        {state?.idle ? 'Idle' : 'Nothing playing'}
                      </div>
                    )}

                    {/* Playback controls */}
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleMediaAction(device.id, 'previous')}
                          disabled={isLoading}
                          className="p-2 bg-surface-500 rounded-full text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                          title="Previous"
                        >
                          <SkipBack className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleMediaAction(device.id, isPlaying ? 'pause' : 'play')}
                          disabled={isLoading}
                          className="p-2.5 bg-primary rounded-full text-white hover:bg-primary/80 transition-colors disabled:opacity-50"
                          title={isPlaying ? 'Pause' : 'Play'}
                        >
                          {isLoading ? (
                            <RefreshCw className="w-5 h-5 animate-spin" />
                          ) : isPlaying ? (
                            <Pause className="w-5 h-5" />
                          ) : (
                            <Play className="w-5 h-5" />
                          )}
                        </button>
                        <button
                          onClick={() => handleMediaAction(device.id, 'next')}
                          disabled={isLoading}
                          className="p-2 bg-surface-500 rounded-full text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                          title="Next"
                        >
                          <SkipForward className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Volume controls */}
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => handleVolumeChange(device.id, 'down')}
                          disabled={isLoading}
                          className="p-1.5 bg-surface-500 rounded text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                          title="Volume down"
                        >
                          <VolumeX className="w-4 h-4" />
                        </button>
                        {state?.volume !== undefined && (
                          <span className="text-xs text-surface-400 w-8 text-center">
                            {Math.round(state.volume)}%
                          </span>
                        )}
                        <button
                          onClick={() => handleVolumeChange(device.id, 'up')}
                          disabled={isLoading}
                          className="p-1.5 bg-surface-500 rounded text-white hover:bg-surface-400 transition-colors disabled:opacity-50"
                          title="Volume up"
                        >
                          <Volume2 className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Power button for Apple TV */}
                      {device.device_type === 'apple_tv' && (
                        <button
                          onClick={() => handleMediaAction(device.id, state?.power ? 'turn_off' : 'turn_on')}
                          disabled={isLoading}
                          className={`p-1.5 rounded transition-colors disabled:opacity-50 ${
                            state?.power
                              ? 'bg-success/20 text-success hover:bg-success/30'
                              : 'bg-surface-500 text-surface-300 hover:bg-surface-400'
                          }`}
                          title={state?.power ? 'Turn off' : 'Turn on'}
                        >
                          <Power className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* Recent events */}
        {events.length > 0 && (
          <div className="magnetic-card">
            <h2 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-warning" />
              Recent Events
              <span className="ml-auto text-sm text-surface-400">{events.length} unacknowledged</span>
            </h2>
            <div className="space-y-3">
              {events.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between p-3 bg-surface-600 rounded-magnetic"
                >
                  <div className="flex-1">
                    <div className="text-white font-medium">{event.title}</div>
                    {event.message && (
                      <div className="text-sm text-surface-400">{event.message}</div>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-sm text-surface-400">
                      {new Date(event.occurred_at).toLocaleTimeString()}
                    </div>
                    {event.media_url && (
                      <a
                        href={api.getMediaProxyUrl(event.media_url)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary text-sm hover:underline"
                      >
                        View
                      </a>
                    )}
                    <button
                      onClick={() => handleAcknowledgeEvent(event.event_id)}
                      className="p-1.5 bg-surface-500 rounded-full text-white hover:bg-success transition-colors"
                      title="Acknowledge"
                    >
                      <Check className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {devices.length === 0 && !loading && (
          <div className="magnetic-card text-center py-12">
            <HomeIcon className="w-16 h-16 text-surface-500 mx-auto mb-4" />
            <h2 className="text-xl font-medium text-white mb-2">No devices connected</h2>
            <p className="text-surface-400">
              Configure smart home platform credentials in the backend environment to connect devices.
            </p>
          </div>
        )}

        {/* Media viewer modal */}
        {mediaViewer && (
          <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
            <div className="magnetic-card w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
              {/* Header */}
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Video className="w-5 h-5 text-primary" />
                  <h2 className="text-xl font-medium text-white">{mediaViewer.deviceName}</h2>
                </div>
                <button
                  onClick={() => setMediaViewer(null)}
                  className="p-2 bg-surface-600 rounded-full text-white hover:bg-surface-500 transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              {/* Single video/image */}
              {mediaViewer.mediaUrl && (
                <div className="flex-1 flex items-center justify-center bg-black rounded-magnetic overflow-hidden">
                  <video
                    src={api.getMediaProxyUrl(mediaViewer.mediaUrl)}
                    controls
                    autoPlay
                    className="max-w-full max-h-[70vh] rounded"
                  >
                    Your browser does not support video playback.
                  </video>
                </div>
              )}

              {/* Multiple recordings */}
              {mediaViewer.recordings && mediaViewer.recordings.length > 0 && (
                <div className="flex-1 overflow-auto">
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {mediaViewer.recordings.map((recording) => (
                      <div key={recording.id} className="bg-surface-600 rounded-magnetic overflow-hidden">
                        <video
                          src={api.getMediaProxyUrl(recording.url)}
                          controls
                          className="w-full aspect-video bg-black"
                        >
                          Your browser does not support video playback.
                        </video>
                        <div className="p-2 flex items-center justify-between">
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            recording.type === 'ding' ? 'bg-warning/20 text-warning' :
                            recording.type === 'motion' ? 'bg-info/20 text-info' :
                            'bg-surface-500 text-surface-300'
                          }`}>
                            {recording.type === 'ding' ? 'Doorbell' : recording.type === 'motion' ? 'Motion' : recording.type}
                          </span>
                          <span className="text-xs text-surface-400">
                            {new Date(recording.created_at).toLocaleString()}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* No recordings message */}
              {mediaViewer.recordings && mediaViewer.recordings.length === 0 && (
                <div className="flex-1 flex items-center justify-center text-surface-400">
                  No recordings available
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Chat Panel */}
      <div className="w-96 flex flex-col">
        <h2 className="text-lg font-medium text-white mb-3">Home Assistant</h2>
        <div className="flex-1 min-h-0">
          <ChatPanel
            sessionId={sessionId}
            context="home"
            placeholder="Control devices, check status, or ask about your home..."
          />
        </div>
      </div>
    </div>
  )
}
