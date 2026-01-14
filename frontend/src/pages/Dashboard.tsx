import { useState, useEffect } from 'react'
import { Server, Activity, FolderGit2, AlertTriangle, Clock, Folder, Bell, Zap, DollarSign } from 'lucide-react'
import { api } from '../services/api'

interface DashboardStats {
  servers: number
  online: number
  projects: number
  alerts: number
}

interface ActivityItem {
  type: string
  message: string
  timestamp: string | null
  icon: string
}

interface UsageFeature {
  feature: string
  request_count: number
  total_tokens: number
  cost_cents: number
}

interface UsageSummary {
  period_hours: number
  request_count: number
  total_tokens: number
  total_cost_cents: number
  total_cost_dollars: number
  by_feature: UsageFeature[]
}

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    servers: 0,
    online: 0,
    projects: 0,
    alerts: 0,
  })
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [usage, setUsage] = useState<UsageSummary | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsData, activityData, usageData] = await Promise.all([
          api.getDashboardStats(),
          api.getDashboardActivity(),
          api.getUsageSummary(24),
        ])
        setStats(statsData)
        setActivities(activityData.activities || [])
        setUsage(usageData)
      } catch (error) {
        console.error('Failed to fetch dashboard data:', error)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    // Refresh every 30 seconds
    const interval = setInterval(fetchData, 30000)
    return () => clearInterval(interval)
  }, [])

  const statCards = [
    { name: 'Servers', value: stats.servers, icon: Server, color: 'text-primary' },
    { name: 'Online', value: stats.online, icon: Activity, color: 'text-success' },
    { name: 'Projects', value: stats.projects, icon: FolderGit2, color: 'text-warning' },
    { name: 'Alerts', value: stats.alerts, icon: AlertTriangle, color: stats.alerts > 0 ? 'text-error' : 'text-surface-400' },
  ]

  const getActivityIcon = (iconType: string) => {
    switch (iconType) {
      case 'server':
        return <Server className="w-4 h-4" />
      case 'folder':
        return <Folder className="w-4 h-4" />
      case 'alert':
        return <Bell className="w-4 h-4 text-error" />
      default:
        return <Clock className="w-4 h-4" />
    }
  }

  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    const now = new Date()
    const diffMs = now.getTime() - date.getTime()
    const diffMins = Math.floor(diffMs / 60000)
    const diffHours = Math.floor(diffMs / 3600000)
    const diffDays = Math.floor(diffMs / 86400000)

    if (diffMins < 1) return 'Just now'
    if (diffMins < 60) return `${diffMins}m ago`
    if (diffHours < 24) return `${diffHours}h ago`
    return `${diffDays}d ago`
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-white">Dashboard</h1>
        <p className="text-surface-300 mt-1">Lab monitoring overview</p>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => (
          <div key={stat.name} className="magnetic-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-surface-300 text-sm">{stat.name}</p>
                <p className="text-3xl font-semibold text-white mt-1">
                  {loading ? '-' : stat.value}
                </p>
              </div>
              <div className={`p-3 rounded-magnetic bg-surface-600 ${stat.color}`}>
                <stat.icon className="w-6 h-6" />
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Quick Actions */}
      <div className="magnetic-card">
        <h2 className="text-lg font-medium text-white mb-4">Quick Actions</h2>
        <div className="flex gap-3">
          <a href="/servers" className="magnetic-button-primary">
            Add Server
          </a>
          <a href="/chat" className="magnetic-button-secondary">
            Open Chat
          </a>
        </div>
      </div>

      {/* Recent Activity and LLM Usage */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Activity */}
        <div className="magnetic-card">
          <h2 className="text-lg font-medium text-white mb-4">Recent Activity</h2>
          {loading ? (
            <div className="text-surface-300 text-sm">Loading...</div>
          ) : activities.length === 0 ? (
            <div className="text-surface-300 text-sm">
              No recent activity. Add a server to get started.
            </div>
          ) : (
            <div className="space-y-3">
              {activities.map((activity, index) => (
                <div key={index} className="flex items-center gap-3 text-sm">
                  <div className="p-2 rounded-magnetic bg-surface-600 text-surface-300">
                    {getActivityIcon(activity.icon)}
                  </div>
                  <div className="flex-1">
                    <p className="text-white">{activity.message}</p>
                  </div>
                  <div className="text-surface-400 text-xs">
                    {formatTimestamp(activity.timestamp)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* LLM Usage Widget */}
        <div className="magnetic-card">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium text-white">LLM Usage (24h)</h2>
            <div className="p-2 rounded-magnetic bg-surface-600 text-primary">
              <Zap className="w-5 h-5" />
            </div>
          </div>
          {loading ? (
            <div className="text-surface-300 text-sm">Loading...</div>
          ) : !usage ? (
            <div className="text-surface-300 text-sm">No usage data available</div>
          ) : (
            <div className="space-y-4">
              {/* Cost Summary */}
              <div className="flex items-center justify-between p-3 rounded-magnetic bg-surface-600">
                <div className="flex items-center gap-2">
                  <DollarSign className="w-4 h-4 text-success" />
                  <span className="text-surface-300">Total Cost</span>
                </div>
                <span className="text-xl font-semibold text-white">
                  ${usage.total_cost_dollars.toFixed(4)}
                </span>
              </div>

              {/* Token Stats */}
              <div className="grid grid-cols-2 gap-3">
                <div className="p-3 rounded-magnetic bg-surface-600">
                  <p className="text-surface-400 text-xs">Requests</p>
                  <p className="text-lg font-semibold text-white">{usage.request_count.toLocaleString()}</p>
                </div>
                <div className="p-3 rounded-magnetic bg-surface-600">
                  <p className="text-surface-400 text-xs">Tokens</p>
                  <p className="text-lg font-semibold text-white">{usage.total_tokens.toLocaleString()}</p>
                </div>
              </div>

              {/* Feature Breakdown */}
              {usage.by_feature.length > 0 && (
                <div className="space-y-2">
                  <p className="text-surface-400 text-xs uppercase tracking-wide">By Feature</p>
                  {usage.by_feature.map((f) => (
                    <div key={f.feature} className="flex items-center justify-between text-sm">
                      <span className="text-surface-300 capitalize">{f.feature}</span>
                      <span className="text-white">{f.total_tokens.toLocaleString()} tokens</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
