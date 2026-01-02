import { useState, useEffect } from 'react'
import { Server, Activity, FolderGit2, AlertTriangle, Clock, Folder, Bell } from 'lucide-react'
import api from '../api/client'

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

export default function Dashboard() {
  const [stats, setStats] = useState<DashboardStats>({
    servers: 0,
    online: 0,
    projects: 0,
    alerts: 0,
  })
  const [activities, setActivities] = useState<ActivityItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const fetchData = async () => {
      try {
        const [statsRes, activityRes] = await Promise.all([
          api.get('/api/dashboard/stats'),
          api.get('/api/dashboard/activity'),
        ])
        setStats(statsRes.data)
        setActivities(activityRes.data.activities || [])
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
    </div>
  )
}
