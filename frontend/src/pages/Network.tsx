import { useState, useEffect } from 'react'
import {
  Network as NetworkIcon,
  Router,
  Wifi,
  WifiOff,
  Server,
  Activity,
  Cpu,
  Thermometer,
  ArrowUpDown,
  Plus,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Settings,
  Trash2,
} from 'lucide-react'
import ChatPanel from '../components/chat/ChatPanel'
import { api } from '../services/api'
import type { NetworkDevice, NetworkPort, NetworkDeviceMetrics } from '../types'

type DeviceTypeFilter = 'all' | 'switch' | 'router' | 'firewall' | 'access_point'

export default function Network() {
  const [sessionId] = useState(() => `network-${Date.now()}`)
  const [devices, setDevices] = useState<NetworkDevice[]>([])
  const [metrics, setMetrics] = useState<Record<number, NetworkDeviceMetrics>>({})
  const [selectedDevice, setSelectedDevice] = useState<NetworkDevice | null>(null)
  const [ports, setPorts] = useState<NetworkPort[]>([])
  const [loading, setLoading] = useState(true)
  const [portsLoading, setPortsLoading] = useState(false)
  const [filter, setFilter] = useState<DeviceTypeFilter>('all')
  const [showOnboarding, setShowOnboarding] = useState(false)
  const [expandedDevice, setExpandedDevice] = useState<number | null>(null)

  useEffect(() => {
    fetchDevices()
    const interval = setInterval(fetchMetrics, 30000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (selectedDevice) {
      fetchPorts(selectedDevice.id)
    }
  }, [selectedDevice])

  const fetchDevices = async () => {
    try {
      setLoading(true)
      const data = await api.listNetworkDevices()
      setDevices(data)
      await fetchMetrics()
    } catch (err) {
      console.error('Failed to fetch network devices:', err)
    } finally {
      setLoading(false)
    }
  }

  const fetchMetrics = async () => {
    try {
      const data = await api.getNetworkMetrics()
      const metricsMap: Record<number, NetworkDeviceMetrics> = {}
      data.forEach((m) => {
        metricsMap[m.device_id] = m
      })
      setMetrics(metricsMap)
    } catch (err) {
      console.error('Failed to fetch network metrics:', err)
    }
  }

  const fetchPorts = async (deviceId: number) => {
    try {
      setPortsLoading(true)
      const data = await api.getDevicePorts(deviceId)
      setPorts(data)
    } catch (err) {
      console.error('Failed to fetch ports:', err)
      setPorts([])
    } finally {
      setPortsLoading(false)
    }
  }

  const handleDeleteDevice = async (deviceId: number) => {
    if (!confirm('Are you sure you want to remove this device?')) return
    try {
      await api.deleteNetworkDevice(deviceId)
      setDevices((prev) => prev.filter((d) => d.id !== deviceId))
      if (selectedDevice?.id === deviceId) {
        setSelectedDevice(null)
        setPorts([])
      }
    } catch (err) {
      console.error('Failed to delete device:', err)
    }
  }

  const filteredDevices = filter === 'all'
    ? devices
    : devices.filter((d) => d.device_type === filter)

  const onlineCount = devices.filter((d) => d.status === 'online').length
  const offlineCount = devices.filter((d) => d.status === 'offline').length

  const getDeviceIcon = (type: string) => {
    switch (type) {
      case 'switch':
        return NetworkIcon
      case 'router':
      case 'firewall':
        return Router
      case 'access_point':
        return Wifi
      default:
        return Server
    }
  }

  return (
    <div className="h-full flex gap-6">
      {/* Main network area */}
      <div className="flex-1 space-y-6 overflow-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Network</h1>
            <p className="text-surface-300 mt-1">Network device monitoring and management</p>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={fetchDevices}
              className="magnetic-button-secondary flex items-center gap-2"
              title="Refresh devices"
            >
              <RefreshCw className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowOnboarding(true)}
              className="magnetic-button-primary flex items-center gap-2"
            >
              <Plus className="w-4 h-4" />
              Add Device
            </button>
          </div>
        </div>

        {/* Status Overview */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <StatusCard
            icon={NetworkIcon}
            label="Total Devices"
            value={devices.length.toString()}
            color="text-primary"
          />
          <StatusCard
            icon={Wifi}
            label="Online"
            value={onlineCount.toString()}
            color="text-success"
          />
          <StatusCard
            icon={WifiOff}
            label="Offline"
            value={offlineCount.toString()}
            color="text-error"
          />
          <StatusCard
            icon={Activity}
            label="Switches"
            value={devices.filter((d) => d.device_type === 'switch').length.toString()}
            color="text-warning"
          />
        </div>

        {/* Filter Tabs */}
        <div className="flex gap-2">
          {(['all', 'switch', 'router', 'firewall', 'access_point'] as DeviceTypeFilter[]).map((type) => (
            <button
              key={type}
              onClick={() => setFilter(type)}
              className={`px-4 py-2 rounded-magnetic text-sm font-medium transition-colors ${
                filter === type
                  ? 'bg-primary text-white'
                  : 'bg-surface-600 text-surface-300 hover:bg-surface-500'
              }`}
            >
              {type === 'all' ? 'All' : type.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </button>
          ))}
        </div>

        {/* Device List */}
        <div className="magnetic-card">
          <h2 className="text-lg font-medium text-white mb-4">Network Devices</h2>
          {loading ? (
            <div className="text-surface-300 text-sm">Loading devices...</div>
          ) : filteredDevices.length === 0 ? (
            <div className="text-surface-300 text-sm">
              No network devices found. Add a device to get started.
            </div>
          ) : (
            <div className="space-y-2">
              {filteredDevices.map((device) => {
                const deviceMetrics = metrics[device.id]
                const Icon = getDeviceIcon(device.device_type)
                const isExpanded = expandedDevice === device.id

                return (
                  <div key={device.id} className="bg-surface-600 rounded-magnetic overflow-hidden">
                    <div
                      onClick={() => {
                        setExpandedDevice(isExpanded ? null : device.id)
                        setSelectedDevice(device)
                      }}
                      className={`p-4 cursor-pointer transition-colors hover:bg-surface-500 ${
                        selectedDevice?.id === device.id ? 'border-l-2 border-primary' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {isExpanded ? (
                            <ChevronDown className="w-4 h-4 text-surface-400" />
                          ) : (
                            <ChevronRight className="w-4 h-4 text-surface-400" />
                          )}
                          <div
                            className={`p-2 rounded-lg ${
                              device.status === 'online' ? 'bg-success/20' : 'bg-error/20'
                            }`}
                          >
                            <Icon
                              className={`w-5 h-5 ${
                                device.status === 'online' ? 'text-success' : 'text-error'
                              }`}
                            />
                          </div>
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="font-medium text-white">{device.name}</span>
                              <span
                                className={`text-xs px-2 py-0.5 rounded-full ${
                                  device.status === 'online'
                                    ? 'bg-success/20 text-success'
                                    : 'bg-error/20 text-error'
                                }`}
                              >
                                {device.status}
                              </span>
                            </div>
                            <div className="text-sm text-surface-400 flex items-center gap-2">
                              <span>{device.ip_address}</span>
                              {device.vendor && (
                                <>
                                  <span>•</span>
                                  <span>{device.vendor}</span>
                                </>
                              )}
                              {device.model && (
                                <>
                                  <span>•</span>
                                  <span>{device.model}</span>
                                </>
                              )}
                            </div>
                          </div>
                        </div>
                        <div className="flex items-center gap-6">
                          {deviceMetrics && (
                            <div className="flex items-center gap-4 text-sm">
                              {deviceMetrics.cpu_usage !== undefined && (
                                <div className="flex items-center gap-1">
                                  <Cpu className="w-4 h-4 text-primary" />
                                  <span className="text-surface-300">
                                    {deviceMetrics.cpu_usage?.toFixed(1) || '--'}%
                                  </span>
                                </div>
                              )}
                              {deviceMetrics.temperature !== undefined && (
                                <div className="flex items-center gap-1">
                                  <Thermometer className="w-4 h-4 text-warning" />
                                  <span className="text-surface-300">
                                    {deviceMetrics.temperature?.toFixed(0) || '--'}°C
                                  </span>
                                </div>
                              )}
                              {(deviceMetrics.rx_rate_mbps !== undefined || deviceMetrics.tx_rate_mbps !== undefined) && (
                                <div className="flex items-center gap-1">
                                  <ArrowUpDown className="w-4 h-4 text-success" />
                                  <span className="text-surface-300">
                                    {deviceMetrics.rx_rate_mbps?.toFixed(1) || '0'}/{deviceMetrics.tx_rate_mbps?.toFixed(1) || '0'} Mbps
                                  </span>
                                </div>
                              )}
                            </div>
                          )}
                          <div className="flex items-center gap-2">
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                // TODO: Open device settings
                              }}
                              className="p-1.5 rounded hover:bg-surface-500 text-surface-400 hover:text-white"
                            >
                              <Settings className="w-4 h-4" />
                            </button>
                            <button
                              onClick={(e) => {
                                e.stopPropagation()
                                handleDeleteDevice(device.id)
                              }}
                              className="p-1.5 rounded hover:bg-error/20 text-surface-400 hover:text-error"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Expanded Port Grid */}
                    {isExpanded && device.device_type === 'switch' && (
                      <div className="border-t border-surface-500 p-4 bg-surface-700">
                        <h3 className="text-sm font-medium text-white mb-3">
                          Switch Ports {device.port_count && `(${device.port_count})`}
                        </h3>
                        {portsLoading ? (
                          <div className="text-surface-400 text-sm">Loading ports...</div>
                        ) : ports.length === 0 ? (
                          <div className="text-surface-400 text-sm">No port information available</div>
                        ) : (
                          <PortGrid ports={ports} />
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      </div>

      {/* Chat Panel */}
      <div className="w-96 flex flex-col">
        <h2 className="text-lg font-medium text-white mb-3">Network Assistant</h2>
        <div className="flex-1 min-h-0">
          <ChatPanel
            sessionId={sessionId}
            context="network"
            placeholder="Ask about network devices, ports, or traffic..."
          />
        </div>
      </div>

      {/* Onboarding Modal */}
      {showOnboarding && (
        <NetworkOnboardingModal
          onClose={() => setShowOnboarding(false)}
          onSuccess={() => {
            setShowOnboarding(false)
            fetchDevices()
          }}
        />
      )}
    </div>
  )
}

interface StatusCardProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string
  color: string
}

function StatusCard({ icon: Icon, label, value, color }: StatusCardProps) {
  return (
    <div className="magnetic-card">
      <div className="flex items-center gap-3">
        <Icon className={`w-5 h-5 ${color}`} />
        <span className="text-surface-300 text-sm">{label}</span>
      </div>
      <div className="mt-2">
        <span className="text-2xl font-semibold text-white">{value}</span>
      </div>
    </div>
  )
}

interface PortGridProps {
  ports: NetworkPort[]
}

function PortGrid({ ports }: PortGridProps) {
  // Group ports into rows of 12
  const portsPerRow = 12
  const rows: NetworkPort[][] = []
  for (let i = 0; i < ports.length; i += portsPerRow) {
    rows.push(ports.slice(i, i + portsPerRow))
  }

  return (
    <div className="space-y-2">
      {rows.map((row, rowIndex) => (
        <div key={rowIndex} className="flex gap-1">
          {row.map((port) => (
            <div
              key={port.id}
              className={`w-8 h-8 rounded flex items-center justify-center text-xs font-medium cursor-pointer transition-colors ${
                port.link_status === 'up'
                  ? 'bg-success/30 text-success hover:bg-success/40'
                  : port.enabled
                  ? 'bg-surface-500 text-surface-400 hover:bg-surface-400'
                  : 'bg-error/20 text-error hover:bg-error/30'
              }`}
              title={`Port ${port.port_number}: ${port.link_status} - VLAN ${port.vlan_id || 'N/A'}${
                port.poe_enabled ? ` - PoE ${port.poe_power?.toFixed(1) || 0}W` : ''
              }`}
            >
              {port.port_number}
            </div>
          ))}
        </div>
      ))}
      <div className="flex items-center gap-4 mt-3 text-xs text-surface-400">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-success/30" />
          <span>Link Up</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-surface-500" />
          <span>Link Down</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-error/20" />
          <span>Disabled</span>
        </div>
      </div>
    </div>
  )
}

interface NetworkOnboardingModalProps {
  onClose: () => void
  onSuccess: () => void
}

function NetworkOnboardingModal({ onClose, onSuccess }: NetworkOnboardingModalProps) {
  const [step, setStep] = useState(1)
  const [formData, setFormData] = useState({
    name: '',
    ip_address: '',
    device_type: 'switch' as 'switch' | 'router' | 'firewall' | 'access_point',
    connection_type: 'snmp' as 'snmp' | 'rest_api' | 'unifi' | 'ssh',
    snmp_version: '2c' as '2c' | '3',
    snmp_community: 'public',
    snmp_username: '',
    snmp_auth_protocol: 'SHA' as 'MD5' | 'SHA',
    snmp_auth_password: '',
    snmp_priv_protocol: 'AES' as 'DES' | 'AES',
    snmp_priv_password: '',
    location: '',
    description: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async () => {
    setLoading(true)
    setError(null)

    try {
      const payload: any = {
        name: formData.name,
        ip_address: formData.ip_address,
        device_type: formData.device_type,
        connection_type: formData.connection_type,
        location: formData.location || undefined,
        description: formData.description || undefined,
      }

      if (formData.connection_type === 'snmp') {
        payload.snmp_config = {
          version: formData.snmp_version,
          ...(formData.snmp_version === '2c'
            ? { community: formData.snmp_community }
            : {
                username: formData.snmp_username,
                auth_protocol: formData.snmp_auth_protocol,
                auth_password: formData.snmp_auth_password,
                priv_protocol: formData.snmp_priv_protocol,
                priv_password: formData.snmp_priv_password,
              }),
        }
      }

      await api.onboardNetworkDevice(payload)
      onSuccess()
    } catch (err: any) {
      setError(err.message || 'Failed to onboard device')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-surface-700 rounded-magnetic w-full max-w-lg p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Add Network Device</h2>

        {step === 1 && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-surface-300 mb-1">Device Name</label>
              <input
                type="text"
                value={formData.name}
                onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                placeholder="e.g., Core Switch 1"
              />
            </div>
            <div>
              <label className="block text-sm text-surface-300 mb-1">IP Address</label>
              <input
                type="text"
                value={formData.ip_address}
                onChange={(e) => setFormData({ ...formData, ip_address: e.target.value })}
                className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                placeholder="e.g., 10.10.20.1"
              />
            </div>
            <div>
              <label className="block text-sm text-surface-300 mb-1">Device Type</label>
              <select
                value={formData.device_type}
                onChange={(e) => setFormData({ ...formData, device_type: e.target.value as any })}
                className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
              >
                <option value="switch">Switch</option>
                <option value="router">Router</option>
                <option value="firewall">Firewall</option>
                <option value="access_point">Access Point</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-surface-300 mb-1">Connection Type</label>
              <select
                value={formData.connection_type}
                onChange={(e) => setFormData({ ...formData, connection_type: e.target.value as any })}
                className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
              >
                <option value="snmp">SNMP</option>
                <option value="ssh">SSH</option>
                <option value="rest_api">REST API</option>
                <option value="unifi">UniFi Controller</option>
              </select>
            </div>
          </div>
        )}

        {step === 2 && formData.connection_type === 'snmp' && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-surface-300 mb-1">SNMP Version</label>
              <select
                value={formData.snmp_version}
                onChange={(e) => setFormData({ ...formData, snmp_version: e.target.value as any })}
                className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
              >
                <option value="2c">v2c</option>
                <option value="3">v3</option>
              </select>
            </div>

            {formData.snmp_version === '2c' ? (
              <div>
                <label className="block text-sm text-surface-300 mb-1">Community String</label>
                <input
                  type="text"
                  value={formData.snmp_community}
                  onChange={(e) => setFormData({ ...formData, snmp_community: e.target.value })}
                  className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                  placeholder="e.g., public"
                />
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-sm text-surface-300 mb-1">Username</label>
                  <input
                    type="text"
                    value={formData.snmp_username}
                    onChange={(e) => setFormData({ ...formData, snmp_username: e.target.value })}
                    className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-surface-300 mb-1">Auth Protocol</label>
                    <select
                      value={formData.snmp_auth_protocol}
                      onChange={(e) => setFormData({ ...formData, snmp_auth_protocol: e.target.value as any })}
                      className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                    >
                      <option value="MD5">MD5</option>
                      <option value="SHA">SHA</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-surface-300 mb-1">Auth Password</label>
                    <input
                      type="password"
                      value={formData.snmp_auth_password}
                      onChange={(e) => setFormData({ ...formData, snmp_auth_password: e.target.value })}
                      className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                    />
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-surface-300 mb-1">Privacy Protocol</label>
                    <select
                      value={formData.snmp_priv_protocol}
                      onChange={(e) => setFormData({ ...formData, snmp_priv_protocol: e.target.value as any })}
                      className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                    >
                      <option value="DES">DES</option>
                      <option value="AES">AES</option>
                    </select>
                  </div>
                  <div>
                    <label className="block text-sm text-surface-300 mb-1">Privacy Password</label>
                    <input
                      type="password"
                      value={formData.snmp_priv_password}
                      onChange={(e) => setFormData({ ...formData, snmp_priv_password: e.target.value })}
                      className="w-full bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-2 text-white focus:border-primary focus:outline-none"
                    />
                  </div>
                </div>
              </>
            )}
          </div>
        )}

        {step === 2 && formData.connection_type !== 'snmp' && (
          <div className="text-surface-300 text-sm">
            {formData.connection_type === 'ssh' && 'SSH connection configuration will be added in a future update.'}
            {formData.connection_type === 'rest_api' && 'REST API configuration will be added in a future update.'}
            {formData.connection_type === 'unifi' && 'UniFi Controller integration will be added in a future update.'}
          </div>
        )}

        {error && (
          <div className="mt-4 p-3 bg-error/20 border border-error rounded-magnetic text-error text-sm">
            {error}
          </div>
        )}

        <div className="flex justify-between mt-6">
          <button
            onClick={step === 1 ? onClose : () => setStep(1)}
            className="px-4 py-2 text-surface-300 hover:text-white transition-colors"
          >
            {step === 1 ? 'Cancel' : 'Back'}
          </button>
          <button
            onClick={step === 1 ? () => setStep(2) : handleSubmit}
            disabled={loading || !formData.name || !formData.ip_address}
            className="magnetic-button-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? 'Adding...' : step === 1 ? 'Next' : 'Add Device'}
          </button>
        </div>
      </div>
    </div>
  )
}
