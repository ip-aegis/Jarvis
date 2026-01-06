import { useState, useEffect } from 'react'
import {
  History,
  Clock,
  CheckCircle,
  XCircle,
  AlertTriangle,
  RefreshCw,
  Filter,
  RotateCcw,
  Play,
  Pause,
  Trash2,
  Calendar,
} from 'lucide-react'
import ChatPanel from '../components/chat/ChatPanel'
import { api } from '../services/api'
import type { ActionAudit, PendingConfirmation, ScheduledAction } from '../types'

type TabType = 'audit' | 'pending' | 'scheduled'
type StatusFilter = 'all' | 'completed' | 'failed' | 'pending' | 'cancelled'
type TypeFilter = 'all' | 'read' | 'write' | 'destructive'

export default function Actions() {
  const [sessionId] = useState(() => `actions-${Date.now()}`)
  const [activeTab, setActiveTab] = useState<TabType>('audit')
  const [auditLog, setAuditLog] = useState<ActionAudit[]>([])
  const [pending, setPending] = useState<PendingConfirmation[]>([])
  const [scheduled, setScheduled] = useState<ScheduledAction[]>([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all')
  const [typeFilter, setTypeFilter] = useState<TypeFilter>('all')

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchPending, 10000)
    return () => clearInterval(interval)
  }, [])

  useEffect(() => {
    if (activeTab === 'audit') {
      fetchAuditLog()
    }
  }, [statusFilter, typeFilter])

  const fetchData = async () => {
    setLoading(true)
    await Promise.all([fetchAuditLog(), fetchPending(), fetchScheduled()])
    setLoading(false)
  }

  const fetchAuditLog = async () => {
    try {
      const params: any = { limit: 100 }
      if (statusFilter !== 'all') params.status = statusFilter
      if (typeFilter !== 'all') params.action_type = typeFilter
      const data = await api.getAuditLog(params)
      setAuditLog(data)
    } catch (err) {
      console.error('Failed to fetch audit log:', err)
    }
  }

  const fetchPending = async () => {
    try {
      const data = await api.getPendingConfirmations()
      setPending(data)
    } catch (err) {
      console.error('Failed to fetch pending confirmations:', err)
    }
  }

  const fetchScheduled = async () => {
    try {
      const data = await api.getScheduledActions()
      setScheduled(data)
    } catch (err) {
      console.error('Failed to fetch scheduled actions:', err)
    }
  }

  const handleConfirm = async (actionId: string) => {
    try {
      const result = await api.confirmAction(actionId)
      if (result.success) {
        fetchPending()
        fetchAuditLog()
      }
    } catch (err) {
      console.error('Failed to confirm action:', err)
    }
  }

  const handleCancel = async (actionId: string) => {
    try {
      await api.cancelAction(actionId)
      fetchPending()
      fetchAuditLog()
    } catch (err) {
      console.error('Failed to cancel action:', err)
    }
  }

  const handleRollback = async (actionId: string) => {
    if (!confirm('Are you sure you want to rollback this action?')) return
    try {
      const result = await api.rollbackAction(actionId)
      if (result.success) {
        fetchAuditLog()
      }
    } catch (err) {
      console.error('Failed to rollback action:', err)
    }
  }

  const handlePauseScheduled = async (jobId: string, isPaused: boolean) => {
    try {
      if (isPaused) {
        await api.resumeScheduledAction(jobId)
      } else {
        await api.pauseScheduledAction(jobId)
      }
      fetchScheduled()
    } catch (err) {
      console.error('Failed to toggle scheduled action:', err)
    }
  }

  const handleDeleteScheduled = async (jobId: string) => {
    if (!confirm('Are you sure you want to delete this scheduled action?')) return
    try {
      await api.deleteScheduledAction(jobId)
      fetchScheduled()
    } catch (err) {
      console.error('Failed to delete scheduled action:', err)
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed':
        return <CheckCircle className="w-4 h-4 text-success" />
      case 'failed':
        return <XCircle className="w-4 h-4 text-error" />
      case 'pending':
      case 'awaiting_confirmation':
        return <Clock className="w-4 h-4 text-warning" />
      case 'cancelled':
      case 'expired':
        return <XCircle className="w-4 h-4 text-surface-400" />
      default:
        return <AlertTriangle className="w-4 h-4 text-surface-400" />
    }
  }

  const getTypeColor = (type: string) => {
    switch (type) {
      case 'read':
        return 'bg-primary/20 text-primary'
      case 'write':
        return 'bg-warning/20 text-warning'
      case 'destructive':
        return 'bg-error/20 text-error'
      default:
        return 'bg-surface-500 text-surface-300'
    }
  }

  const formatDate = (dateStr: string | undefined | null) => {
    if (!dateStr) return '--'
    return new Date(dateStr).toLocaleString()
  }

  return (
    <div className="h-full flex gap-6">
      {/* Main area */}
      <div className="flex-1 space-y-6 overflow-auto">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-white">Actions</h1>
            <p className="text-surface-300 mt-1">Audit log, pending confirmations, and scheduled actions</p>
          </div>
          <button
            onClick={fetchData}
            className="magnetic-button-secondary flex items-center gap-2"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 border-b border-surface-600">
          <button
            onClick={() => setActiveTab('audit')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'audit'
                ? 'border-primary text-primary'
                : 'border-transparent text-surface-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <History className="w-4 h-4" />
              Audit Log
            </div>
          </button>
          <button
            onClick={() => setActiveTab('pending')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'pending'
                ? 'border-primary text-primary'
                : 'border-transparent text-surface-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4" />
              Pending
              {pending.length > 0 && (
                <span className="px-1.5 py-0.5 bg-warning/20 text-warning text-xs rounded-full">
                  {pending.length}
                </span>
              )}
            </div>
          </button>
          <button
            onClick={() => setActiveTab('scheduled')}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === 'scheduled'
                ? 'border-primary text-primary'
                : 'border-transparent text-surface-400 hover:text-white'
            }`}
          >
            <div className="flex items-center gap-2">
              <Calendar className="w-4 h-4" />
              Scheduled
              {scheduled.filter((s) => s.enabled).length > 0 && (
                <span className="px-1.5 py-0.5 bg-success/20 text-success text-xs rounded-full">
                  {scheduled.filter((s) => s.enabled).length}
                </span>
              )}
            </div>
          </button>
        </div>

        {/* Audit Log Tab */}
        {activeTab === 'audit' && (
          <div className="space-y-4">
            {/* Filters */}
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Filter className="w-4 h-4 text-surface-400" />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
                  className="bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-1.5 text-sm text-white focus:border-primary focus:outline-none"
                >
                  <option value="all">All Status</option>
                  <option value="completed">Completed</option>
                  <option value="failed">Failed</option>
                  <option value="pending">Pending</option>
                  <option value="cancelled">Cancelled</option>
                </select>
              </div>
              <select
                value={typeFilter}
                onChange={(e) => setTypeFilter(e.target.value as TypeFilter)}
                className="bg-surface-600 border border-surface-500 rounded-magnetic px-3 py-1.5 text-sm text-white focus:border-primary focus:outline-none"
              >
                <option value="all">All Types</option>
                <option value="read">Read</option>
                <option value="write">Write</option>
                <option value="destructive">Destructive</option>
              </select>
            </div>

            {/* Audit Table */}
            <div className="magnetic-card overflow-hidden">
              {loading ? (
                <div className="p-4 text-surface-300">Loading...</div>
              ) : auditLog.length === 0 ? (
                <div className="p-4 text-surface-300">No actions found</div>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-surface-600">
                        <th className="text-left text-sm font-medium text-surface-400 p-3">Status</th>
                        <th className="text-left text-sm font-medium text-surface-400 p-3">Action</th>
                        <th className="text-left text-sm font-medium text-surface-400 p-3">Type</th>
                        <th className="text-left text-sm font-medium text-surface-400 p-3">Target</th>
                        <th className="text-left text-sm font-medium text-surface-400 p-3">Initiated</th>
                        <th className="text-left text-sm font-medium text-surface-400 p-3">Actions</th>
                      </tr>
                    </thead>
                    <tbody>
                      {auditLog.map((action) => (
                        <tr key={action.action_id} className="border-b border-surface-700 hover:bg-surface-600/50">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              {getStatusIcon(action.status)}
                              <span className="text-sm text-surface-300 capitalize">{action.status}</span>
                            </div>
                          </td>
                          <td className="p-3">
                            <div className="text-white text-sm font-medium">{action.action_name}</div>
                            {action.natural_language_input && (
                              <div className="text-xs text-surface-400 mt-0.5 truncate max-w-xs">
                                "{action.natural_language_input}"
                              </div>
                            )}
                          </td>
                          <td className="p-3">
                            <span className={`text-xs px-2 py-0.5 rounded-full ${getTypeColor(action.action_type)}`}>
                              {action.action_type}
                            </span>
                          </td>
                          <td className="p-3">
                            {action.target_type && (
                              <span className="text-sm text-surface-300">
                                {action.target_type}: {action.target_name || '--'}
                              </span>
                            )}
                          </td>
                          <td className="p-3 text-sm text-surface-400">
                            {formatDate(action.initiated_at)}
                          </td>
                          <td className="p-3">
                            {action.rollback_available && !action.rollback_executed && action.status === 'completed' && (
                              <button
                                onClick={() => handleRollback(action.action_id)}
                                className="p-1.5 rounded hover:bg-warning/20 text-surface-400 hover:text-warning"
                                title="Rollback"
                              >
                                <RotateCcw className="w-4 h-4" />
                              </button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Pending Confirmations Tab */}
        {activeTab === 'pending' && (
          <div className="space-y-4">
            {pending.length === 0 ? (
              <div className="magnetic-card text-surface-300 text-center py-8">
                No pending confirmations
              </div>
            ) : (
              pending.map((confirmation) => (
                <div key={confirmation.action_id} className="magnetic-card border border-warning/30">
                  <div className="flex items-start justify-between">
                    <div>
                      <div className="flex items-center gap-2 mb-2">
                        <AlertTriangle className="w-5 h-5 text-warning" />
                        <span className="font-medium text-white">Confirmation Required</span>
                      </div>
                      <p className="text-surface-300 mb-3">{confirmation.confirmation_prompt}</p>
                      {confirmation.risk_summary && (
                        <p className="text-sm text-error mb-3">{confirmation.risk_summary}</p>
                      )}
                      {confirmation.affected_resources && confirmation.affected_resources.length > 0 && (
                        <div className="mb-3">
                          <span className="text-sm text-surface-400">Affected resources:</span>
                          <ul className="mt-1 text-sm text-surface-300">
                            {confirmation.affected_resources.map((resource, i) => (
                              <li key={i} className="flex items-center gap-1">
                                <span className="w-1 h-1 bg-surface-400 rounded-full" />
                                {resource}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <div className="text-xs text-surface-400">
                        Expires: {formatDate(confirmation.expires_at)}
                      </div>
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleCancel(confirmation.action_id)}
                        className="px-4 py-2 bg-surface-600 hover:bg-surface-500 text-surface-300 rounded-magnetic transition-colors"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={() => handleConfirm(confirmation.action_id)}
                        className="px-4 py-2 bg-warning hover:bg-warning/80 text-black font-medium rounded-magnetic transition-colors"
                      >
                        Confirm
                      </button>
                    </div>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {/* Scheduled Actions Tab */}
        {activeTab === 'scheduled' && (
          <div className="space-y-4">
            {scheduled.length === 0 ? (
              <div className="magnetic-card text-surface-300 text-center py-8">
                No scheduled actions. Use the chat to create scheduled or conditional actions.
              </div>
            ) : (
              <div className="magnetic-card overflow-hidden">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Status</th>
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Name</th>
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Action</th>
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Schedule</th>
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Next Run</th>
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Runs</th>
                      <th className="text-left text-sm font-medium text-surface-400 p-3">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {scheduled.map((action) => (
                      <tr key={action.id} className="border-b border-surface-700 hover:bg-surface-600/50">
                        <td className="p-3">
                          <span
                            className={`text-xs px-2 py-0.5 rounded-full ${
                              action.enabled
                                ? 'bg-success/20 text-success'
                                : 'bg-surface-500 text-surface-400'
                            }`}
                          >
                            {action.enabled ? 'Active' : 'Paused'}
                          </span>
                        </td>
                        <td className="p-3 text-white text-sm">{action.name || '--'}</td>
                        <td className="p-3 text-surface-300 text-sm">{action.action_name}</td>
                        <td className="p-3 text-surface-300 text-sm capitalize">
                          {action.schedule_type}
                          {action.condition_expression && (
                            <div className="text-xs text-primary mt-0.5">
                              if: {action.condition_expression}
                            </div>
                          )}
                        </td>
                        <td className="p-3 text-surface-400 text-sm">
                          {action.next_run ? formatDate(action.next_run) : '--'}
                        </td>
                        <td className="p-3 text-surface-400 text-sm">
                          {action.run_count}
                          {action.error_count > 0 && (
                            <span className="text-error ml-1">({action.error_count} errors)</span>
                          )}
                        </td>
                        <td className="p-3">
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => handlePauseScheduled(action.job_id, !action.enabled)}
                              className="p-1.5 rounded hover:bg-surface-500 text-surface-400 hover:text-white"
                              title={action.enabled ? 'Pause' : 'Resume'}
                            >
                              {action.enabled ? (
                                <Pause className="w-4 h-4" />
                              ) : (
                                <Play className="w-4 h-4" />
                              )}
                            </button>
                            <button
                              onClick={() => handleDeleteScheduled(action.job_id)}
                              className="p-1.5 rounded hover:bg-error/20 text-surface-400 hover:text-error"
                              title="Delete"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Chat Panel */}
      <div className="w-96 flex flex-col">
        <h2 className="text-lg font-medium text-white mb-3">Actions Assistant</h2>
        <div className="flex-1 min-h-0">
          <ChatPanel
            sessionId={sessionId}
            context="actions"
            placeholder="Schedule actions, check status, or ask about the audit log..."
          />
        </div>
      </div>
    </div>
  )
}
