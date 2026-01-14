import { useState, useEffect, useRef, useCallback } from 'react'
import {
  Shield,
  ShieldCheck,
  ShieldOff,
  Activity,
  List,
  Search,
  Plus,
  Trash2,
  RefreshCw,
  AlertTriangle,
  Ban,
  Check,
  Clock,
  Users,
  Globe,
  Filter,
  Settings,
  TrendingUp,
  XCircle,
  ShieldAlert,
  Eye,
  CheckCircle,
  AlertOctagon,
  Zap,
  Wifi,
  WifiOff,
  Download,
  Upload,
  Link,
  Calendar,
} from 'lucide-react'
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'
import ChatPanel from '../components/chat/ChatPanel'
import { api } from '../services/api'
import type {
  DnsStatus,
  DnsStats,
  DnsBlocklist,
  DnsCustomRule,
  DnsClient,
  DnsQueryLogEntry,
  DnsSecurityAlert,
  DnsDomainReputation,
  DnsRewrite,
} from '../types'

type TabType = 'dashboard' | 'security' | 'querylog' | 'blocklists' | 'rules' | 'rewrites' | 'clients' | 'chat'

export default function DNS() {
  const [sessionId] = useState(() => `dns-${Date.now()}`)
  const [activeTab, setActiveTab] = useState<TabType>('dashboard')
  const [status, setStatus] = useState<DnsStatus | null>(null)
  const [stats, setStats] = useState<DnsStats | null>(null)
  const [blocklists, setBlocklists] = useState<DnsBlocklist[]>([])
  const [rules, setRules] = useState<DnsCustomRule[]>([])
  const [clients, setClients] = useState<DnsClient[]>([])
  const [queryLog, setQueryLog] = useState<DnsQueryLogEntry[]>([])
  const [error, setError] = useState<string | null>(null)

  // Dashboard state
  const [timeRange, setTimeRange] = useState<24 | 168 | 720>(24) // hours: 24h, 7d, 30d

  // Security analytics state
  const [alerts, setAlerts] = useState<DnsSecurityAlert[]>([])
  const [alertsTotal, setAlertsTotal] = useState(0)
  const [alertFilter, setAlertFilter] = useState<'all' | 'open' | 'acknowledged' | 'resolved'>('open')
  const [severityFilter, setSeverityFilter] = useState<'all' | 'low' | 'medium' | 'high' | 'critical'>('all')
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)
  const [selectedAlert, setSelectedAlert] = useState<DnsSecurityAlert | null>(null)
  const [domainLookup, setDomainLookup] = useState('')
  const [domainReputation, setDomainReputation] = useState<DnsDomainReputation | null>(null)
  const [lookupLoading, setLookupLoading] = useState(false)

  // Form states
  const [newBlockDomain, setNewBlockDomain] = useState('')
  const [queryLogSearch, setQueryLogSearch] = useState('')
  const [queryLogFilter, setQueryLogFilter] = useState<'all' | 'allowed' | 'blocked'>('all')
  const [queryLogClientFilter, setQueryLogClientFilter] = useState('')

  // Blocklist form states
  const [showAddBlocklist, setShowAddBlocklist] = useState(false)
  const [newBlocklistName, setNewBlocklistName] = useState('')
  const [newBlocklistUrl, setNewBlocklistUrl] = useState('')
  const [newBlocklistCategory, setNewBlocklistCategory] = useState('')
  const [blocklistUpdating, setBlocklistUpdating] = useState<number | null>(null)

  // Allow domain form state
  const [newAllowDomain, setNewAllowDomain] = useState('')
  const [ruleSearchFilter, setRuleSearchFilter] = useState('')

  // Bulk import state
  const [showBulkImport, setShowBulkImport] = useState(false)
  const [bulkImportText, setBulkImportText] = useState('')
  const [bulkImportType, setBulkImportType] = useState<'block' | 'allow'>('block')
  const [bulkImportLoading, setBulkImportLoading] = useState(false)
  const [bulkImportResult, setBulkImportResult] = useState<{ message: string; added: number; skipped: number; failed: number } | null>(null)

  // Client modal state
  const [selectedClient, setSelectedClient] = useState<DnsClient | null>(null)
  const [clientUpdateLoading, setClientUpdateLoading] = useState(false)
  const [editClientName, setEditClientName] = useState('')

  // DNS Rewrites (Custom DNS Entries) state
  const [rewrites, setRewrites] = useState<DnsRewrite[]>([])
  const [newRewriteDomain, setNewRewriteDomain] = useState('')
  const [newRewriteAnswer, setNewRewriteAnswer] = useState('')
  const [newRewriteComment, setNewRewriteComment] = useState('')
  const [rewriteLoading, setRewriteLoading] = useState(false)
  const [rewriteError, setRewriteError] = useState<string | null>(null)

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchStats, 30000)
    return () => clearInterval(interval)
  }, [])

  // Refetch stats when time range changes
  useEffect(() => {
    fetchStats()
  }, [timeRange])

  const fetchData = async () => {
    setError(null)
    try {
      const [statusRes, statsRes] = await Promise.all([
        api.getDnsStatus(),
        api.getDnsStats(timeRange),
      ])
      setStatus(statusRes)
      setStats(statsRes)
    } catch (err) {
      console.error('Failed to fetch DNS data:', err)
      setError('Failed to connect to DNS service. Make sure AdGuard Home is running.')
    }
  }

  const fetchStats = async () => {
    try {
      const statsRes = await api.getDnsStats(timeRange)
      setStats(statsRes)
    } catch (err) {
      console.error('Failed to fetch DNS stats:', err)
    }
  }

  const fetchBlocklists = async () => {
    try {
      const data = await api.getDnsBlocklists()
      setBlocklists(data.blocklists)
    } catch (err) {
      console.error('Failed to fetch blocklists:', err)
    }
  }

  const fetchRules = async () => {
    try {
      const data = await api.getDnsCustomRules()
      setRules(data.rules)
    } catch (err) {
      console.error('Failed to fetch rules:', err)
    }
  }

  const fetchClients = async () => {
    try {
      const data = await api.getDnsClients()
      setClients(data.clients)
    } catch (err) {
      console.error('Failed to fetch clients:', err)
    }
  }

  const fetchQueryLog = async () => {
    try {
      const statusFilter = queryLogFilter === 'all' ? undefined : queryLogFilter
      const clientFilter = queryLogClientFilter || undefined
      const data = await api.getDnsQueryLog(100, queryLogSearch || undefined, statusFilter, clientFilter)
      setQueryLog(data.entries)
    } catch (err) {
      console.error('Failed to fetch query log:', err)
    }
  }

  const fetchRewrites = async () => {
    try {
      const data = await api.getDnsRewrites()
      setRewrites(data.rewrites)
    } catch (err) {
      console.error('Failed to fetch DNS rewrites:', err)
    }
  }

  const fetchAlerts = useCallback(async () => {
    try {
      const statusParam = alertFilter === 'all' ? undefined : alertFilter
      const severityParam = severityFilter === 'all' ? undefined : severityFilter
      const data = await api.getDnsAlerts({
        status: statusParam,
        severity: severityParam,
        limit: 50,
      })
      setAlerts(data.alerts)
      setAlertsTotal(data.total)
    } catch (err) {
      console.error('Failed to fetch alerts:', err)
    }
  }, [alertFilter, severityFilter])

  const connectAlertsWebSocket = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return

    const handleAlert = (alert: DnsSecurityAlert) => {
      setAlerts(prev => {
        const exists = prev.some(a => a.alert_id === alert.alert_id)
        if (exists) return prev
        return [alert, ...prev].slice(0, 50)
      })
      setAlertsTotal(prev => prev + 1)
    }

    const handleError = () => {
      setWsConnected(false)
    }

    wsRef.current = api.connectDnsAlerts(handleAlert, handleError)
    wsRef.current.onopen = () => setWsConnected(true)
    wsRef.current.onclose = () => setWsConnected(false)
  }, [])

  const disconnectAlertsWebSocket = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
      setWsConnected(false)
    }
  }, [])

  const handleAcknowledgeAlert = async (alertId: string) => {
    try {
      await api.acknowledgeDnsAlert(alertId)
      fetchAlerts()
      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(null)
      }
    } catch (err) {
      console.error('Failed to acknowledge alert:', err)
    }
  }

  const handleResolveAlert = async (alertId: string) => {
    try {
      await api.resolveDnsAlert(alertId)
      fetchAlerts()
      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(null)
      }
    } catch (err) {
      console.error('Failed to resolve alert:', err)
    }
  }

  const handleFalsePositive = async (alertId: string) => {
    try {
      await api.markDnsFalsePositive(alertId)
      fetchAlerts()
      if (selectedAlert?.alert_id === alertId) {
        setSelectedAlert(null)
      }
    } catch (err) {
      console.error('Failed to mark as false positive:', err)
    }
  }

  const handleDomainLookup = async () => {
    if (!domainLookup.trim()) return
    setLookupLoading(true)
    try {
      const reputation = await api.getDomainReputation(domainLookup.trim())
      setDomainReputation(reputation)
    } catch (err) {
      console.error('Failed to lookup domain:', err)
    } finally {
      setLookupLoading(false)
    }
  }

  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return 'bg-red-500/20 text-red-400 border-red-500'
      case 'high': return 'bg-orange-500/20 text-orange-400 border-orange-500'
      case 'medium': return 'bg-yellow-500/20 text-yellow-400 border-yellow-500'
      case 'low': return 'bg-blue-500/20 text-blue-400 border-blue-500'
      default: return 'bg-gray-500/20 text-gray-400 border-gray-500'
    }
  }

  const getAlertTypeIcon = (type: string) => {
    switch (type) {
      case 'dga': return <Zap size={16} />
      case 'tunneling': return <Activity size={16} />
      case 'fast_flux': return <RefreshCw size={16} />
      case 'behavioral': return <AlertTriangle size={16} />
      default: return <ShieldAlert size={16} />
    }
  }

  useEffect(() => {
    if (activeTab === 'blocklists') fetchBlocklists()
    if (activeTab === 'rules') fetchRules()
    if (activeTab === 'rewrites') fetchRewrites()
    if (activeTab === 'clients') fetchClients()
    if (activeTab === 'querylog') {
      fetchQueryLog()
      fetchClients() // Populate client filter dropdown
    }
    if (activeTab === 'security') {
      fetchAlerts()
      connectAlertsWebSocket()
    } else {
      disconnectAlertsWebSocket()
    }
  }, [activeTab, fetchAlerts, connectAlertsWebSocket, disconnectAlertsWebSocket])

  useEffect(() => {
    if (activeTab === 'querylog') fetchQueryLog()
  }, [queryLogSearch, queryLogFilter, queryLogClientFilter])

  useEffect(() => {
    if (activeTab === 'security') fetchAlerts()
  }, [alertFilter, severityFilter, activeTab, fetchAlerts])

  // Cleanup WebSocket on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close()
      }
    }
  }, [])

  const handleBlockDomain = async () => {
    if (!newBlockDomain.trim()) return
    try {
      await api.blockDomain(newBlockDomain.trim())
      setNewBlockDomain('')
      fetchRules()
    } catch (err) {
      console.error('Failed to block domain:', err)
    }
  }

  const handleRemoveRule = async (ruleId: number) => {
    if (!confirm('Remove this rule?')) return
    try {
      await api.removeDnsCustomRule(ruleId)
      fetchRules()
    } catch (err) {
      console.error('Failed to remove rule:', err)
    }
  }

  const handleSetupDefaults = async () => {
    try {
      await api.setupDefaultBlocklists()
      fetchBlocklists()
    } catch (err) {
      console.error('Failed to setup default blocklists:', err)
    }
  }

  const handleToggleBlocklist = async (blocklistId: number, enabled: boolean) => {
    setBlocklistUpdating(blocklistId)
    try {
      await api.updateDnsBlocklist(blocklistId, { enabled })
      fetchBlocklists()
    } catch (err) {
      console.error('Failed to toggle blocklist:', err)
    } finally {
      setBlocklistUpdating(null)
    }
  }

  const handleForceUpdateBlocklist = async (blocklistId: number) => {
    setBlocklistUpdating(blocklistId)
    try {
      await api.forceUpdateBlocklist(blocklistId)
      fetchBlocklists()
    } catch (err) {
      console.error('Failed to update blocklist:', err)
    } finally {
      setBlocklistUpdating(null)
    }
  }

  const handleAddBlocklist = async () => {
    if (!newBlocklistName.trim() || !newBlocklistUrl.trim()) return
    try {
      await api.addDnsBlocklist({
        name: newBlocklistName.trim(),
        url: newBlocklistUrl.trim(),
        category: newBlocklistCategory.trim() || undefined,
      })
      setNewBlocklistName('')
      setNewBlocklistUrl('')
      setNewBlocklistCategory('')
      setShowAddBlocklist(false)
      fetchBlocklists()
    } catch (err) {
      console.error('Failed to add blocklist:', err)
    }
  }

  const handleAllowDomain = async () => {
    if (!newAllowDomain.trim()) return
    try {
      await api.allowDomain(newAllowDomain.trim())
      setNewAllowDomain('')
      fetchRules()
    } catch (err) {
      console.error('Failed to allow domain:', err)
    }
  }

  const handleBlockFromAlert = async (domain: string, alertId: string) => {
    try {
      await api.blockDomain(domain, `Blocked from security alert ${alertId}`)
      await handleResolveAlert(alertId)
      fetchRules()
    } catch (err) {
      console.error('Failed to block domain from alert:', err)
    }
  }

  const handleAllowFromReputation = async (domain: string) => {
    try {
      await api.allowDomain(domain, 'Allowed from reputation lookup')
      setDomainReputation(null)
      setDomainLookup('')
      fetchRules()
    } catch (err) {
      console.error('Failed to allow domain:', err)
    }
  }

  const handleBlockFromReputation = async (domain: string) => {
    try {
      await api.blockDomain(domain, 'Blocked from reputation lookup')
      setDomainReputation(null)
      setDomainLookup('')
      fetchRules()
    } catch (err) {
      console.error('Failed to block domain:', err)
    }
  }

  const handleBulkImport = async () => {
    const domains = bulkImportText
      .split('\n')
      .map(line => line.trim())
      .filter(line => line && !line.startsWith('#'))

    if (domains.length === 0) return

    setBulkImportLoading(true)
    setBulkImportResult(null)
    try {
      const result = await api.bulkImportRules(domains, bulkImportType)
      setBulkImportResult({
        message: result.message,
        added: result.added.length,
        skipped: result.skipped.length,
        failed: result.failed.length,
      })
      if (result.added.length > 0) {
        fetchRules()
        setBulkImportText('')
      }
    } catch (err) {
      console.error('Failed to bulk import rules:', err)
      setBulkImportResult({
        message: 'Import failed',
        added: 0,
        skipped: 0,
        failed: domains.length,
      })
    } finally {
      setBulkImportLoading(false)
    }
  }

  const handleExportRules = () => {
    const blockRules = rules.filter(r => r.rule_type === 'block').map(r => r.domain)
    const allowRules = rules.filter(r => r.rule_type === 'allow').map(r => `@@${r.domain}`)

    const content = [
      '# DNS Rules Export',
      `# Generated: ${new Date().toISOString()}`,
      '',
      '# Block Rules',
      ...blockRules,
      '',
      '# Allow Rules (whitelist)',
      ...allowRules,
    ].join('\n')

    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dns-rules-${new Date().toISOString().split('T')[0]}.txt`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  const handleExportQueryLog = () => {
    if (queryLog.length === 0) return

    const headers = ['Timestamp', 'Client IP', 'Domain', 'Status', 'Block Reason', 'Response Time (ms)', 'Cached']
    const rows = queryLog.map(entry => [
      new Date(entry.timestamp).toISOString(),
      entry.client_ip,
      entry.domain,
      entry.status,
      (entry as unknown as { block_reason?: string }).block_reason || '',
      String(entry.response_time_ms ?? 0),
      entry.cached ? 'Yes' : 'No',
    ])

    const csv = [headers.join(','), ...rows.map(row => row.map(cell => `"${cell}"`).join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `dns-query-log-${new Date().toISOString().split('T')[0]}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  // DNS Rewrite handlers
  const handleAddRewrite = async () => {
    if (!newRewriteDomain.trim() || !newRewriteAnswer.trim()) return

    setRewriteLoading(true)
    setRewriteError(null)
    try {
      await api.addDnsRewrite(
        newRewriteDomain.trim(),
        newRewriteAnswer.trim(),
        newRewriteComment.trim() || undefined
      )
      setNewRewriteDomain('')
      setNewRewriteAnswer('')
      setNewRewriteComment('')
      fetchRewrites()
    } catch (err) {
      console.error('Failed to add DNS rewrite:', err)
      setRewriteError(err instanceof Error ? err.message : 'Failed to add DNS rewrite')
    } finally {
      setRewriteLoading(false)
    }
  }

  const handleRemoveRewrite = async (rewriteId: number) => {
    if (!confirm('Remove this DNS entry?')) return
    try {
      await api.removeDnsRewrite(rewriteId)
      fetchRewrites()
    } catch (err) {
      console.error('Failed to remove DNS rewrite:', err)
    }
  }

  const openClientModal = (client: DnsClient) => {
    setSelectedClient(client)
    setEditClientName(client.name || '')
  }

  const closeClientModal = () => {
    setSelectedClient(null)
    setEditClientName('')
  }

  const handleUpdateClient = async (update: {
    name?: string
    filtering_enabled?: boolean
    safe_browsing?: boolean
    parental_control?: boolean
  }) => {
    if (!selectedClient) return

    setClientUpdateLoading(true)
    try {
      const result = await api.updateDnsClient(selectedClient.id, update)
      // Update local state
      setClients(prev => prev.map(c =>
        c.id === selectedClient.id ? { ...c, ...result.client } : c
      ))
      setSelectedClient(prev => prev ? { ...prev, ...result.client } : null)
    } catch (err) {
      console.error('Failed to update client:', err)
    } finally {
      setClientUpdateLoading(false)
    }
  }

  const handleSaveClientName = async () => {
    if (!selectedClient || editClientName === (selectedClient.name || '')) return
    await handleUpdateClient({ name: editClientName || undefined })
  }

  const formatNumber = (n: number | undefined | null): string => {
    if (n == null) return '0'
    if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`
    if (n >= 1000) return `${(n / 1000).toFixed(1)}K`
    return n.toString()
  }

  const tabs: { id: TabType; label: string; icon: React.ReactNode }[] = [
    { id: 'dashboard', label: 'Dashboard', icon: <Activity size={16} /> },
    { id: 'security', label: 'Security', icon: <ShieldAlert size={16} /> },
    { id: 'querylog', label: 'Query Log', icon: <List size={16} /> },
    { id: 'blocklists', label: 'Blocklists', icon: <Shield size={16} /> },
    { id: 'rules', label: 'Rules', icon: <Filter size={16} /> },
    { id: 'rewrites', label: 'DNS Entries', icon: <Link size={16} /> },
    { id: 'clients', label: 'Clients', icon: <Users size={16} /> },
    { id: 'chat', label: 'Chat', icon: <Globe size={16} /> },
  ]

  return (
    <div className="flex h-full">
      {/* Main Content */}
      <div className="flex-1 p-6 overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div className="flex items-center gap-3">
            <Shield className="text-magnetic-primary" size={28} />
            <div>
              <h1 className="text-2xl font-semibold text-white">DNS Security</h1>
              <p className="text-sm text-gray-400">
                Ad blocking, privacy protection, and threat prevention
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {status && (
              <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm ${
                status.running ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
              }`}>
                {status.running ? <ShieldCheck size={16} /> : <ShieldOff size={16} />}
                {status.running ? 'Protected' : 'Offline'}
              </div>
            )}
            <button
              onClick={fetchData}
              className="magnetic-button-secondary flex items-center gap-2"
            >
              <RefreshCw size={16} />
              Refresh
            </button>
          </div>
        </div>

        {/* Error State */}
        {error && (
          <div className="magnetic-card p-4 mb-6 border-l-4 border-yellow-500 bg-yellow-500/10">
            <div className="flex items-center gap-2 text-yellow-400">
              <AlertTriangle size={20} />
              <span>{error}</span>
            </div>
          </div>
        )}

        {/* Tabs */}
        <div className="flex gap-1 mb-6 border-b border-gray-700">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-2 text-sm transition-colors ${
                activeTab === tab.id
                  ? 'text-magnetic-primary border-b-2 border-magnetic-primary'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>

        {/* Tab Content */}
        {activeTab === 'dashboard' && (
          <div className="space-y-6">
            {/* Time Range Picker */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar size={16} className="text-gray-400" />
                <span className="text-gray-400 text-sm">Time Range:</span>
                <div className="flex rounded-lg overflow-hidden border border-gray-700">
                  <button
                    onClick={() => setTimeRange(24)}
                    className={`px-3 py-1.5 text-sm transition-colors ${
                      timeRange === 24
                        ? 'bg-magnetic-primary text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    24h
                  </button>
                  <button
                    onClick={() => setTimeRange(168)}
                    className={`px-3 py-1.5 text-sm transition-colors border-l border-gray-700 ${
                      timeRange === 168
                        ? 'bg-magnetic-primary text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    7d
                  </button>
                  <button
                    onClick={() => setTimeRange(720)}
                    className={`px-3 py-1.5 text-sm transition-colors border-l border-gray-700 ${
                      timeRange === 720
                        ? 'bg-magnetic-primary text-white'
                        : 'bg-gray-800 text-gray-400 hover:text-white'
                    }`}
                  >
                    30d
                  </button>
                </div>
              </div>
            </div>

            {/* Stats Grid */}
            {stats && (
              <div className="grid grid-cols-5 gap-4">
                <div className="magnetic-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Total Queries</span>
                    <Activity className="text-magnetic-primary" size={20} />
                  </div>
                  <div className="text-2xl font-semibold text-white mt-2">
                    {formatNumber(stats.total_queries)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {timeRange === 24 ? 'Last 24 hours' : timeRange === 168 ? 'Last 7 days' : 'Last 30 days'}
                  </div>
                </div>
                <div className="magnetic-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Blocked</span>
                    <Ban className="text-red-400" size={20} />
                  </div>
                  <div className="text-2xl font-semibold text-red-400 mt-2">
                    {formatNumber(stats.blocked_queries)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {(stats.blocked_percentage ?? 0).toFixed(1)}% of total
                  </div>
                </div>
                <div className="magnetic-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Cached</span>
                    <TrendingUp className="text-green-400" size={20} />
                  </div>
                  <div className="text-2xl font-semibold text-green-400 mt-2">
                    {formatNumber(stats.cached_queries)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Cache hits</div>
                </div>
                <div className="magnetic-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Cache Rate</span>
                    <TrendingUp className="text-purple-400" size={20} />
                  </div>
                  <div className="text-2xl font-semibold text-purple-400 mt-2">
                    {stats.total_queries > 0
                      ? ((stats.cached_queries / stats.total_queries) * 100).toFixed(1)
                      : 0}%
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Cache efficiency</div>
                </div>
                <div className="magnetic-card p-4">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400 text-sm">Avg Response</span>
                    <Clock className="text-yellow-400" size={20} />
                  </div>
                  <div className="text-2xl font-semibold text-yellow-400 mt-2">
                    {(stats.avg_response_time ?? 0).toFixed(0)}ms
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Response time</div>
                </div>
              </div>
            )}

            {/* Query History Chart */}
            {stats?.queries_over_time && stats.queries_over_time.length > 0 && (
              <div className="magnetic-card p-4">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Activity size={18} />
                  Query History
                </h3>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <AreaChart
                      data={stats.queries_over_time.map((q, i) => ({
                        time: i,
                        queries: typeof q === 'object' ? (q as { count: number }).count : q,
                        blocked: stats.blocked_over_time?.[i]
                          ? (typeof stats.blocked_over_time[i] === 'object'
                            ? (stats.blocked_over_time[i] as { count: number }).count
                            : stats.blocked_over_time[i])
                          : 0,
                      }))}
                      margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
                    >
                      <defs>
                        <linearGradient id="colorQueries" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#00bceb" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#00bceb" stopOpacity={0}/>
                        </linearGradient>
                        <linearGradient id="colorBlocked" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#ef4444" stopOpacity={0.3}/>
                          <stop offset="95%" stopColor="#ef4444" stopOpacity={0}/>
                        </linearGradient>
                      </defs>
                      <XAxis
                        dataKey="time"
                        stroke="#6b7280"
                        tick={{ fill: '#9ca3af', fontSize: 12 }}
                        tickFormatter={(val) => {
                          if (timeRange === 24) return `${val}h`;
                          if (timeRange === 168) return `${Math.floor(val / 24)}d`;
                          return `${Math.floor(val / 24)}d`;
                        }}
                      />
                      <YAxis stroke="#6b7280" tick={{ fill: '#9ca3af', fontSize: 12 }} />
                      <Tooltip
                        contentStyle={{
                          backgroundColor: '#1f2937',
                          border: '1px solid #374151',
                          borderRadius: '8px',
                          color: '#fff',
                        }}
                        labelFormatter={(val) => {
                          if (timeRange === 24) return `Hour ${val}`;
                          return `Day ${Math.floor(val / 24) + 1}`;
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="queries"
                        stroke="#00bceb"
                        fillOpacity={1}
                        fill="url(#colorQueries)"
                        name="Total Queries"
                      />
                      <Area
                        type="monotone"
                        dataKey="blocked"
                        stroke="#ef4444"
                        fillOpacity={1}
                        fill="url(#colorBlocked)"
                        name="Blocked"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Top Domains */}
            <div className="grid grid-cols-2 gap-4">
              <div className="magnetic-card p-4">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Globe size={18} />
                  Top Queried Domains
                </h3>
                <div className="space-y-2">
                  {stats?.top_domains.slice(0, 5).map((d, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-gray-300 truncate flex-1">{d.domain}</span>
                      <span className="text-gray-500 ml-2">{formatNumber(d.count)}</span>
                    </div>
                  ))}
                  {(!stats?.top_domains || stats.top_domains.length === 0) && (
                    <p className="text-gray-500 text-sm">No data available</p>
                  )}
                </div>
              </div>
              <div className="magnetic-card p-4">
                <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                  <Ban size={18} className="text-red-400" />
                  Top Blocked Domains
                </h3>
                <div className="space-y-2">
                  {stats?.top_blocked.slice(0, 5).map((d, i) => (
                    <div key={i} className="flex items-center justify-between text-sm">
                      <span className="text-red-300 truncate flex-1">{d.domain}</span>
                      <span className="text-gray-500 ml-2">{formatNumber(d.count)}</span>
                    </div>
                  ))}
                  {(!stats?.top_blocked || stats.top_blocked.length === 0) && (
                    <p className="text-gray-500 text-sm">No blocked domains</p>
                  )}
                </div>
              </div>
            </div>

            {/* Quick Block */}
            <div className="magnetic-card p-4">
              <h3 className="text-white font-medium mb-4 flex items-center gap-2">
                <Shield size={18} />
                Quick Block Domain
              </h3>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={newBlockDomain}
                  onChange={(e) => setNewBlockDomain(e.target.value)}
                  placeholder="Enter domain to block (e.g., ads.example.com)"
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  onKeyDown={(e) => e.key === 'Enter' && handleBlockDomain()}
                />
                <button
                  onClick={handleBlockDomain}
                  className="magnetic-button-primary flex items-center gap-2"
                  disabled={!newBlockDomain.trim()}
                >
                  <Ban size={16} />
                  Block
                </button>
              </div>
            </div>
          </div>
        )}

        {activeTab === 'security' && (
          <div className="space-y-6">
            {/* Header with WebSocket Status */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h3 className="text-white font-medium">Security Alerts</h3>
                <div className={`flex items-center gap-2 px-2 py-1 rounded text-xs ${
                  wsConnected ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'
                }`}>
                  {wsConnected ? <Wifi size={12} /> : <WifiOff size={12} />}
                  {wsConnected ? 'Live' : 'Disconnected'}
                </div>
              </div>
              <div className="flex items-center gap-2">
                <select
                  value={alertFilter}
                  onChange={(e) => setAlertFilter(e.target.value as 'all' | 'open' | 'acknowledged' | 'resolved')}
                  className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                >
                  <option value="all">All Status</option>
                  <option value="open">Open</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="resolved">Resolved</option>
                </select>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value as 'all' | 'low' | 'medium' | 'high' | 'critical')}
                  className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                >
                  <option value="all">All Severity</option>
                  <option value="critical">Critical</option>
                  <option value="high">High</option>
                  <option value="medium">Medium</option>
                  <option value="low">Low</option>
                </select>
                <button onClick={fetchAlerts} className="magnetic-button-secondary p-2">
                  <RefreshCw size={16} />
                </button>
              </div>
            </div>

            {/* Alert Stats */}
            <div className="grid grid-cols-4 gap-4">
              <div className="magnetic-card p-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Total Alerts</span>
                  <ShieldAlert className="text-magnetic-primary" size={20} />
                </div>
                <div className="text-2xl font-semibold text-white mt-2">{alertsTotal}</div>
              </div>
              <div className="magnetic-card p-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Critical</span>
                  <AlertOctagon className="text-red-400" size={20} />
                </div>
                <div className="text-2xl font-semibold text-red-400 mt-2">
                  {alerts.filter(a => a.severity === 'critical').length}
                </div>
              </div>
              <div className="magnetic-card p-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">High</span>
                  <AlertTriangle className="text-orange-400" size={20} />
                </div>
                <div className="text-2xl font-semibold text-orange-400 mt-2">
                  {alerts.filter(a => a.severity === 'high').length}
                </div>
              </div>
              <div className="magnetic-card p-4">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400 text-sm">Open</span>
                  <Eye className="text-yellow-400" size={20} />
                </div>
                <div className="text-2xl font-semibold text-yellow-400 mt-2">
                  {alerts.filter(a => a.status === 'open').length}
                </div>
              </div>
            </div>

            {/* Domain Reputation Lookup */}
            <div className="magnetic-card p-4">
              <h4 className="text-white font-medium mb-3 flex items-center gap-2">
                <Search size={16} />
                Domain Reputation Lookup
              </h4>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={domainLookup}
                  onChange={(e) => setDomainLookup(e.target.value)}
                  placeholder="Enter domain to check reputation..."
                  className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  onKeyDown={(e) => e.key === 'Enter' && handleDomainLookup()}
                />
                <button
                  onClick={handleDomainLookup}
                  className="magnetic-button-primary flex items-center gap-2"
                  disabled={!domainLookup.trim() || lookupLoading}
                >
                  {lookupLoading ? <RefreshCw size={16} className="animate-spin" /> : <Search size={16} />}
                  Check
                </button>
              </div>
              {domainReputation && (
                <div className="mt-4 p-4 bg-gray-800/50 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-white font-medium">{domainReputation.domain}</span>
                    <div className={`px-3 py-1 rounded-full text-sm ${
                      domainReputation.reputation_score >= 70 ? 'bg-green-500/20 text-green-400' :
                      domainReputation.reputation_score >= 40 ? 'bg-yellow-500/20 text-yellow-400' :
                      'bg-red-500/20 text-red-400'
                    }`}>
                      Score: {domainReputation.reputation_score.toFixed(0)}/100
                    </div>
                  </div>
                  <div className="grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <span className="text-gray-400">Entropy:</span>
                      <span className="text-white ml-2">{domainReputation.entropy_score.toFixed(2)}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">Category:</span>
                      <span className="text-white ml-2">{domainReputation.category || 'Unknown'}</span>
                    </div>
                    <div>
                      <span className="text-gray-400">First Seen:</span>
                      <span className="text-white ml-2">
                        {domainReputation.first_seen ? new Date(domainReputation.first_seen).toLocaleDateString() : 'Unknown'}
                      </span>
                    </div>
                  </div>
                  {domainReputation.threat_indicators && Object.keys(domainReputation.threat_indicators).length > 0 && (
                    <div className="mt-3 pt-3 border-t border-gray-700">
                      <span className="text-gray-400 text-sm">Threat Indicators:</span>
                      <div className="flex flex-wrap gap-2 mt-2">
                        {Object.entries(domainReputation.threat_indicators).map(([key, value]) => (
                          <span key={key} className="px-2 py-1 bg-red-500/20 text-red-400 text-xs rounded">
                            {key}: {typeof value === 'number' ? value.toFixed(2) : String(value)}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                  {/* Quick Actions */}
                  <div className="mt-3 pt-3 border-t border-gray-700 flex gap-2">
                    {domainReputation.reputation_score >= 70 ? (
                      <button
                        onClick={() => handleAllowFromReputation(domainReputation.domain)}
                        className="flex-1 px-3 py-2 bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors text-sm flex items-center justify-center gap-2"
                      >
                        <Check size={14} />
                        Allow Domain
                      </button>
                    ) : (
                      <button
                        onClick={() => handleBlockFromReputation(domainReputation.domain)}
                        className="flex-1 px-3 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors text-sm flex items-center justify-center gap-2"
                      >
                        <Ban size={14} />
                        Block Domain
                      </button>
                    )}
                    <button
                      onClick={() => {
                        setDomainReputation(null)
                        setDomainLookup('')
                      }}
                      className="px-3 py-2 bg-gray-600/20 text-gray-400 rounded hover:bg-gray-600/30 transition-colors text-sm"
                    >
                      Clear
                    </button>
                  </div>
                </div>
              )}
            </div>

            {/* Alerts List */}
            <div className="grid grid-cols-3 gap-4">
              <div className="col-span-2 space-y-2">
                {alerts.map((alert) => (
                  <div
                    key={alert.alert_id}
                    onClick={() => setSelectedAlert(alert)}
                    className={`magnetic-card p-4 cursor-pointer border-l-4 transition-all hover:bg-gray-800/50 ${
                      getSeverityColor(alert.severity)
                    } ${selectedAlert?.alert_id === alert.alert_id ? 'ring-1 ring-magnetic-primary' : ''}`}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        {getAlertTypeIcon(alert.alert_type)}
                        <div>
                          <div className="text-white font-medium">{alert.title}</div>
                          <div className="text-gray-400 text-sm mt-1">{alert.domain}</div>
                        </div>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className={`px-2 py-0.5 rounded text-xs ${getSeverityColor(alert.severity)}`}>
                          {alert.severity}
                        </span>
                        <span className="text-gray-500 text-xs">
                          {alert.timestamp ? new Date(alert.timestamp).toLocaleString() : ''}
                        </span>
                      </div>
                    </div>
                    <div className="flex items-center justify-between mt-3 pt-3 border-t border-gray-700/50">
                      <div className="flex items-center gap-4 text-sm text-gray-400">
                        <span>Client: {alert.client_ip}</span>
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          alert.status === 'open' ? 'bg-yellow-500/20 text-yellow-400' :
                          alert.status === 'acknowledged' ? 'bg-blue-500/20 text-blue-400' :
                          'bg-green-500/20 text-green-400'
                        }`}>
                          {alert.status}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        {alert.status === 'open' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleAcknowledgeAlert(alert.alert_id); }}
                            className="p-1 text-gray-400 hover:text-blue-400 transition-colors"
                            title="Acknowledge"
                          >
                            <Eye size={16} />
                          </button>
                        )}
                        {alert.status !== 'resolved' && (
                          <button
                            onClick={(e) => { e.stopPropagation(); handleResolveAlert(alert.alert_id); }}
                            className="p-1 text-gray-400 hover:text-green-400 transition-colors"
                            title="Resolve"
                          >
                            <CheckCircle size={16} />
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
                {alerts.length === 0 && (
                  <div className="magnetic-card p-8 text-center text-gray-500">
                    <ShieldCheck size={48} className="mx-auto mb-4 opacity-50" />
                    <p>No security alerts found</p>
                    <p className="text-sm mt-2">Your network is looking healthy!</p>
                  </div>
                )}
              </div>

              {/* Alert Detail Panel */}
              <div className="magnetic-card p-4">
                {selectedAlert ? (
                  <div className="space-y-4">
                    <div className="flex items-center justify-between">
                      <h4 className="text-white font-medium">Alert Details</h4>
                      <button
                        onClick={() => setSelectedAlert(null)}
                        className="text-gray-400 hover:text-white"
                      >
                        <XCircle size={16} />
                      </button>
                    </div>
                    <div className="space-y-3">
                      <div>
                        <span className="text-gray-400 text-sm">Title</span>
                        <p className="text-white">{selectedAlert.title}</p>
                      </div>
                      <div>
                        <span className="text-gray-400 text-sm">Description</span>
                        <p className="text-gray-300 text-sm">{selectedAlert.description}</p>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div>
                          <span className="text-gray-400 text-sm">Type</span>
                          <p className="text-white capitalize">{selectedAlert.alert_type}</p>
                        </div>
                        <div>
                          <span className="text-gray-400 text-sm">Severity</span>
                          <p className={`capitalize ${
                            selectedAlert.severity === 'critical' ? 'text-red-400' :
                            selectedAlert.severity === 'high' ? 'text-orange-400' :
                            selectedAlert.severity === 'medium' ? 'text-yellow-400' :
                            'text-blue-400'
                          }`}>{selectedAlert.severity}</p>
                        </div>
                      </div>
                      <div>
                        <span className="text-gray-400 text-sm">Domain</span>
                        <p className="text-white font-mono text-sm">{selectedAlert.domain}</p>
                      </div>
                      <div>
                        <span className="text-gray-400 text-sm">Client IP</span>
                        <p className="text-white font-mono text-sm">{selectedAlert.client_ip}</p>
                      </div>
                      {selectedAlert.llm_analysis && (
                        <div>
                          <span className="text-gray-400 text-sm">AI Analysis</span>
                          <p className="text-gray-300 text-sm mt-1">{selectedAlert.llm_analysis}</p>
                        </div>
                      )}
                      {selectedAlert.remediation && (
                        <div>
                          <span className="text-gray-400 text-sm">Remediation</span>
                          <p className="text-gray-300 text-sm mt-1">{selectedAlert.remediation}</p>
                        </div>
                      )}
                    </div>
                    {/* Quick Actions */}
                    {selectedAlert.domain && (
                      <div className="border-t border-gray-700 pt-4 mt-4">
                        <h4 className="text-white font-medium text-sm mb-3">Quick Actions</h4>
                        <div className="flex gap-2">
                          <button
                            onClick={() => handleBlockFromAlert(selectedAlert.domain!, selectedAlert.alert_id)}
                            className="flex-1 px-3 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors text-sm flex items-center justify-center gap-2"
                          >
                            <Ban size={14} />
                            Block Domain
                          </button>
                          <button
                            onClick={() => {
                              setDomainLookup(selectedAlert.domain!)
                              handleDomainLookup()
                            }}
                            className="flex-1 px-3 py-2 bg-blue-500/20 text-blue-400 rounded hover:bg-blue-500/30 transition-colors text-sm flex items-center justify-center gap-2"
                          >
                            <Search size={14} />
                            Check Reputation
                          </button>
                        </div>
                      </div>
                    )}

                    <div className="flex gap-2 pt-4 border-t border-gray-700">
                      {selectedAlert.status === 'open' && (
                        <button
                          onClick={() => handleAcknowledgeAlert(selectedAlert.alert_id)}
                          className="flex-1 magnetic-button-secondary text-sm"
                        >
                          Acknowledge
                        </button>
                      )}
                      {selectedAlert.status !== 'resolved' && (
                        <button
                          onClick={() => handleResolveAlert(selectedAlert.alert_id)}
                          className="flex-1 magnetic-button-primary text-sm"
                        >
                          Resolve
                        </button>
                      )}
                      <button
                        onClick={() => handleFalsePositive(selectedAlert.alert_id)}
                        className="magnetic-button-secondary text-sm px-3"
                        title="Mark as false positive"
                      >
                        False +
                      </button>
                    </div>
                  </div>
                ) : (
                  <div className="h-full flex items-center justify-center text-gray-500">
                    <p>Select an alert to view details</p>
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === 'querylog' && (
          <div className="space-y-4">
            {/* Search and Filter */}
            <div className="flex gap-4 items-center">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                <input
                  type="text"
                  value={queryLogSearch}
                  onChange={(e) => setQueryLogSearch(e.target.value)}
                  placeholder="Search domains..."
                  className="w-full bg-gray-800 border border-gray-700 rounded pl-10 pr-4 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                />
              </div>
              <select
                value={queryLogFilter}
                onChange={(e) => setQueryLogFilter(e.target.value as 'all' | 'allowed' | 'blocked')}
                className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
              >
                <option value="all">All Status</option>
                <option value="allowed">Allowed</option>
                <option value="blocked">Blocked</option>
              </select>
              <select
                value={queryLogClientFilter}
                onChange={(e) => setQueryLogClientFilter(e.target.value)}
                className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
              >
                <option value="">All Clients</option>
                {clients.map(client => (
                  <option key={client.id} value={client.ip_addresses?.[0] || client.client_id}>
                    {client.name || client.ip_addresses?.[0] || client.client_id}
                  </option>
                ))}
              </select>
              <button onClick={fetchQueryLog} className="magnetic-button-secondary p-2">
                <RefreshCw size={16} />
              </button>
              <button
                onClick={handleExportQueryLog}
                className="magnetic-button-secondary flex items-center gap-2"
                disabled={queryLog.length === 0}
              >
                <Download size={16} />
                Export CSV
              </button>
            </div>

            {/* Query Log Table */}
            <div className="magnetic-card overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-800/50">
                  <tr>
                    <th className="text-left p-3 text-gray-400 font-medium">Time</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Client</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Domain</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Status</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Block Reason</th>
                    <th className="text-left p-3 text-gray-400 font-medium">Response</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-800">
                  {queryLog.map((entry, i) => (
                    <tr key={i} className="hover:bg-gray-800/30">
                      <td className="p-3 text-gray-400 text-xs">
                        {new Date(entry.timestamp).toLocaleTimeString()}
                      </td>
                      <td className="p-3 text-gray-300">{entry.client_ip}</td>
                      <td className="p-3 text-white truncate max-w-xs">{entry.domain}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 rounded text-xs ${
                          entry.status === 'blocked'
                            ? 'bg-red-500/20 text-red-400'
                            : 'bg-green-500/20 text-green-400'
                        }`}>
                          {entry.status}
                        </span>
                      </td>
                      <td className="p-3 text-gray-400 text-xs truncate max-w-xs" title={(entry as unknown as { block_reason?: string }).block_reason || ''}>
                        {(entry as unknown as { block_reason?: string }).block_reason || '-'}
                      </td>
                      <td className="p-3 text-gray-400 text-xs">
                        {(entry.response_time_ms ?? 0).toFixed(0)}ms
                        {entry.cached && <span className="ml-2 text-yellow-400">(cached)</span>}
                      </td>
                    </tr>
                  ))}
                  {queryLog.length === 0 && (
                    <tr>
                      <td colSpan={6} className="p-6 text-center text-gray-500">
                        No query logs found
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
            <div className="text-xs text-gray-500">
              Showing {queryLog.length} entries
            </div>
          </div>
        )}

        {activeTab === 'blocklists' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-white font-medium">Active Blocklists</h3>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowAddBlocklist(!showAddBlocklist)}
                  className="magnetic-button-secondary flex items-center gap-2"
                >
                  <Link size={16} />
                  Add URL
                </button>
                <button onClick={handleSetupDefaults} className="magnetic-button-primary flex items-center gap-2">
                  <Plus size={16} />
                  Setup Defaults
                </button>
              </div>
            </div>

            {/* Add Blocklist Form */}
            {showAddBlocklist && (
              <div className="magnetic-card p-4 space-y-3">
                <h4 className="text-white font-medium">Add Custom Blocklist</h4>
                <div className="grid grid-cols-3 gap-3">
                  <input
                    type="text"
                    value={newBlocklistName}
                    onChange={(e) => setNewBlocklistName(e.target.value)}
                    placeholder="Name (e.g., My Blocklist)"
                    className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                  <input
                    type="text"
                    value={newBlocklistUrl}
                    onChange={(e) => setNewBlocklistUrl(e.target.value)}
                    placeholder="URL (https://...)"
                    className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                  <input
                    type="text"
                    value={newBlocklistCategory}
                    onChange={(e) => setNewBlocklistCategory(e.target.value)}
                    placeholder="Category (optional)"
                    className="bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                </div>
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => setShowAddBlocklist(false)}
                    className="magnetic-button-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleAddBlocklist}
                    className="magnetic-button-primary"
                    disabled={!newBlocklistName.trim() || !newBlocklistUrl.trim()}
                  >
                    Add Blocklist
                  </button>
                </div>
              </div>
            )}

            <div className="grid gap-3">
              {blocklists.map((bl) => (
                <div key={bl.id} className={`magnetic-card p-4 ${!bl.enabled ? 'opacity-60' : ''}`}>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4 flex-1">
                      {/* Toggle Switch */}
                      <button
                        onClick={() => handleToggleBlocklist(bl.id, !bl.enabled)}
                        disabled={blocklistUpdating === bl.id}
                        className={`relative w-12 h-6 rounded-full transition-colors ${
                          bl.enabled ? 'bg-green-500' : 'bg-gray-600'
                        } ${blocklistUpdating === bl.id ? 'opacity-50' : ''}`}
                      >
                        <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                          bl.enabled ? 'left-7' : 'left-1'
                        }`} />
                      </button>

                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{bl.name}</span>
                          {bl.category && (
                            <span className="px-2 py-0.5 bg-magnetic-primary/20 text-magnetic-primary text-xs rounded">
                              {bl.category}
                            </span>
                          )}
                        </div>
                        <div className="text-sm text-gray-400 mt-1 flex items-center gap-3">
                          <span>{formatNumber(bl.rules_count)} rules</span>
                          {bl.last_updated && (
                            <span>Updated {new Date(bl.last_updated).toLocaleDateString()}</span>
                          )}
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => handleForceUpdateBlocklist(bl.id)}
                        disabled={blocklistUpdating === bl.id}
                        className="p-2 text-gray-400 hover:text-magnetic-primary transition-colors"
                        title="Force update"
                      >
                        {blocklistUpdating === bl.id ? (
                          <RefreshCw size={16} className="animate-spin" />
                        ) : (
                          <Download size={16} />
                        )}
                      </button>
                      <button
                        onClick={() => api.removeDnsBlocklist(bl.id).then(fetchBlocklists)}
                        className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                        title="Remove"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                </div>
              ))}
              {blocklists.length === 0 && (
                <div className="magnetic-card p-6 text-center text-gray-500">
                  No blocklists configured. Click "Setup Defaults" to add recommended blocklists.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'rules' && (
          <div className="space-y-4">
            {/* Add Rules Forms */}
            <div className="grid grid-cols-2 gap-4">
              {/* Block Domain */}
              <div className="magnetic-card p-4">
                <h4 className="text-white font-medium mb-3 flex items-center gap-2">
                  <Ban size={16} className="text-red-400" />
                  Block Domain
                </h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newBlockDomain}
                    onChange={(e) => setNewBlockDomain(e.target.value)}
                    placeholder="domain.com"
                    className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-red-400"
                    onKeyDown={(e) => e.key === 'Enter' && handleBlockDomain()}
                  />
                  <button
                    onClick={handleBlockDomain}
                    className="px-4 py-2 bg-red-500/20 text-red-400 rounded hover:bg-red-500/30 transition-colors"
                    disabled={!newBlockDomain.trim()}
                  >
                    Block
                  </button>
                </div>
              </div>

              {/* Allow Domain */}
              <div className="magnetic-card p-4">
                <h4 className="text-white font-medium mb-3 flex items-center gap-2">
                  <Check size={16} className="text-green-400" />
                  Allow Domain (Whitelist)
                </h4>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={newAllowDomain}
                    onChange={(e) => setNewAllowDomain(e.target.value)}
                    placeholder="domain.com"
                    className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-green-400"
                    onKeyDown={(e) => e.key === 'Enter' && handleAllowDomain()}
                  />
                  <button
                    onClick={handleAllowDomain}
                    className="px-4 py-2 bg-green-500/20 text-green-400 rounded hover:bg-green-500/30 transition-colors"
                    disabled={!newAllowDomain.trim()}
                  >
                    Allow
                  </button>
                </div>
              </div>
            </div>

            {/* Search Filter and Actions */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <h3 className="text-white font-medium">Custom Rules</h3>
                <div className="relative max-w-xs">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-500" size={16} />
                  <input
                    type="text"
                    value={ruleSearchFilter}
                    onChange={(e) => setRuleSearchFilter(e.target.value)}
                    placeholder="Filter rules..."
                    className="w-full bg-gray-800 border border-gray-700 rounded pl-10 pr-4 py-1.5 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                </div>
                <span className="text-gray-500 text-sm">
                  {rules.filter(r => r.rule_type === 'block').length} blocked, {rules.filter(r => r.rule_type === 'allow').length} allowed
                </span>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setShowBulkImport(!showBulkImport)}
                  className="magnetic-button-secondary flex items-center gap-2"
                >
                  <Upload size={16} />
                  Import
                </button>
                <button
                  onClick={handleExportRules}
                  className="magnetic-button-secondary flex items-center gap-2"
                  disabled={rules.length === 0}
                >
                  <Download size={16} />
                  Export
                </button>
              </div>
            </div>

            {/* Bulk Import Form */}
            {showBulkImport && (
              <div className="magnetic-card p-4 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-white font-medium flex items-center gap-2">
                    <Upload size={16} />
                    Bulk Import Rules
                  </h4>
                  <select
                    value={bulkImportType}
                    onChange={(e) => setBulkImportType(e.target.value as 'block' | 'allow')}
                    className="bg-gray-800 border border-gray-700 rounded px-3 py-1.5 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  >
                    <option value="block">Block Rules</option>
                    <option value="allow">Allow Rules (Whitelist)</option>
                  </select>
                </div>
                <textarea
                  value={bulkImportText}
                  onChange={(e) => setBulkImportText(e.target.value)}
                  placeholder="Enter one domain per line. Lines starting with # are ignored."
                  className="w-full h-32 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm font-mono focus:outline-none focus:border-magnetic-primary resize-none"
                />
                {bulkImportResult && (
                  <div className={`p-3 rounded text-sm ${
                    bulkImportResult.failed > 0 ? 'bg-yellow-500/20 text-yellow-400' : 'bg-green-500/20 text-green-400'
                  }`}>
                    {bulkImportResult.message}
                    <div className="flex gap-4 mt-1 text-xs">
                      <span>Added: {bulkImportResult.added}</span>
                      <span>Skipped: {bulkImportResult.skipped}</span>
                      <span>Failed: {bulkImportResult.failed}</span>
                    </div>
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <button
                    onClick={() => {
                      setShowBulkImport(false)
                      setBulkImportText('')
                      setBulkImportResult(null)
                    }}
                    className="magnetic-button-secondary"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleBulkImport}
                    className="magnetic-button-primary flex items-center gap-2"
                    disabled={!bulkImportText.trim() || bulkImportLoading}
                  >
                    {bulkImportLoading ? (
                      <RefreshCw size={16} className="animate-spin" />
                    ) : (
                      <Upload size={16} />
                    )}
                    Import {bulkImportText.split('\n').filter(l => l.trim() && !l.startsWith('#')).length} Domains
                  </button>
                </div>
              </div>
            )}

            {/* Rules List */}
            <div className="grid gap-2">
              {rules
                .filter(rule => !ruleSearchFilter || rule.domain.toLowerCase().includes(ruleSearchFilter.toLowerCase()))
                .map((rule) => (
                <div key={rule.id} className="magnetic-card p-3 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {rule.rule_type === 'block' ? (
                      <XCircle className="text-red-400" size={18} />
                    ) : (
                      <Check className="text-green-400" size={18} />
                    )}
                    <span className="text-white font-mono text-sm">{rule.domain}</span>
                    <span className={`px-2 py-0.5 text-xs rounded ${
                      rule.rule_type === 'block'
                        ? 'bg-red-500/20 text-red-400'
                        : 'bg-green-500/20 text-green-400'
                    }`}>
                      {rule.rule_type}
                    </span>
                    {rule.comment && (
                      <span className="text-gray-500 text-sm">- {rule.comment}</span>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemoveRule(rule.id)}
                    className="text-gray-500 hover:text-red-400 transition-colors"
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              ))}
              {rules.length === 0 && (
                <div className="magnetic-card p-6 text-center text-gray-500">
                  No custom rules. Use the forms above to add block or allow rules.
                </div>
              )}
              {rules.length > 0 && rules.filter(rule => !ruleSearchFilter || rule.domain.toLowerCase().includes(ruleSearchFilter.toLowerCase())).length === 0 && (
                <div className="magnetic-card p-6 text-center text-gray-500">
                  No rules match your filter.
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'rewrites' && (
          <div className="space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-white font-medium">Custom DNS Entries</h3>
                <p className="text-gray-400 text-sm mt-1">
                  Create custom DNS records so devices on your network can resolve names to specific IPs
                </p>
              </div>
              <span className="text-gray-500 text-sm">{rewrites.length} entries</span>
            </div>

            {/* Add New DNS Entry Form */}
            <div className="magnetic-card p-4">
              <h4 className="text-white font-medium mb-3 flex items-center gap-2">
                <Plus size={16} className="text-magnetic-primary" />
                Add DNS Entry
              </h4>
              <p className="text-gray-400 text-sm mb-4">
                Example: Add "jarvis" pointing to "10.10.20.235" so anyone querying "jarvis" gets that IP
              </p>
              <div className="grid grid-cols-3 gap-3">
                <div>
                  <label className="text-gray-400 text-xs block mb-1">Domain Name</label>
                  <input
                    type="text"
                    value={newRewriteDomain}
                    onChange={(e) => setNewRewriteDomain(e.target.value)}
                    placeholder="jarvis"
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                </div>
                <div>
                  <label className="text-gray-400 text-xs block mb-1">IP Address / Target</label>
                  <input
                    type="text"
                    value={newRewriteAnswer}
                    onChange={(e) => setNewRewriteAnswer(e.target.value)}
                    placeholder="10.10.20.235"
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                </div>
                <div>
                  <label className="text-gray-400 text-xs block mb-1">Comment (optional)</label>
                  <input
                    type="text"
                    value={newRewriteComment}
                    onChange={(e) => setNewRewriteComment(e.target.value)}
                    placeholder="Jarvis web app"
                    className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                  />
                </div>
              </div>
              {rewriteError && (
                <div className="mt-3 p-2 bg-red-500/20 text-red-400 rounded text-sm">
                  {rewriteError}
                </div>
              )}
              <div className="flex justify-end mt-4">
                <button
                  onClick={handleAddRewrite}
                  className="magnetic-button-primary flex items-center gap-2"
                  disabled={!newRewriteDomain.trim() || !newRewriteAnswer.trim() || rewriteLoading}
                >
                  {rewriteLoading ? (
                    <RefreshCw size={16} className="animate-spin" />
                  ) : (
                    <Plus size={16} />
                  )}
                  Add DNS Entry
                </button>
              </div>
            </div>

            {/* DNS Entries List */}
            <div className="grid gap-2">
              {rewrites.map((rewrite) => (
                <div key={rewrite.id} className="magnetic-card p-4 flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <Link className="text-magnetic-primary" size={20} />
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-mono">{rewrite.domain}</span>
                        <span className="text-gray-500">→</span>
                        <span className="text-magnetic-primary font-mono">{rewrite.answer}</span>
                      </div>
                      {rewrite.comment && (
                        <div className="text-gray-500 text-sm mt-1">{rewrite.comment}</div>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {rewrite.created_at && (
                      <span className="text-gray-500 text-xs">
                        {new Date(rewrite.created_at).toLocaleDateString()}
                      </span>
                    )}
                    <button
                      onClick={() => handleRemoveRewrite(rewrite.id)}
                      className="p-2 text-gray-400 hover:text-red-400 transition-colors"
                      title="Remove"
                    >
                      <Trash2 size={16} />
                    </button>
                  </div>
                </div>
              ))}
              {rewrites.length === 0 && (
                <div className="magnetic-card p-8 text-center text-gray-500">
                  <Link size={48} className="mx-auto mb-4 opacity-50" />
                  <p>No custom DNS entries yet</p>
                  <p className="text-sm mt-2">
                    Add an entry above to create a custom DNS record (e.g., "jarvis" → "10.10.20.235")
                  </p>
                </div>
              )}
            </div>
          </div>
        )}

        {activeTab === 'clients' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-white font-medium">Known Clients</h3>
              <span className="text-gray-500 text-sm">{clients.length} clients</span>
            </div>
            <div className="grid gap-2">
              {clients.map((client) => (
                <div
                  key={client.id}
                  className="magnetic-card p-4 flex items-center justify-between cursor-pointer hover:bg-gray-800/50 transition-colors"
                  onClick={() => openClientModal(client)}
                >
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-white font-medium">
                        {client.name || client.client_id}
                      </span>
                      {!client.filtering_enabled && (
                        <span className="px-2 py-0.5 bg-yellow-500/20 text-yellow-400 text-xs rounded">
                          Filtering Off
                        </span>
                      )}
                      {client.safe_browsing && (
                        <span className="px-2 py-0.5 bg-blue-500/20 text-blue-400 text-xs rounded">
                          Safe Browsing
                        </span>
                      )}
                      {client.parental_control && (
                        <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
                          Parental
                        </span>
                      )}
                    </div>
                    <div className="text-sm text-gray-400 mt-1 flex items-center gap-3">
                      <span>{client.ip_addresses?.[0] || client.client_id}</span>
                      <span>{(client.queries_count ?? 0).toLocaleString()} queries</span>
                      <span className="text-red-400">{(client.blocked_count ?? 0).toLocaleString()} blocked</span>
                      {client.last_seen && (
                        <span>Last: {new Date(client.last_seen).toLocaleDateString()}</span>
                      )}
                    </div>
                  </div>
                  <Settings className="text-gray-500 hover:text-magnetic-primary transition-colors" size={18} />
                </div>
              ))}
              {clients.length === 0 && (
                <div className="magnetic-card p-6 text-center text-gray-500">
                  No clients discovered yet. Clients will appear after making DNS queries.
                </div>
              )}
            </div>

            {/* Client Settings Modal */}
            {selectedClient && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={closeClientModal}>
                <div className="magnetic-card w-full max-w-md p-6 m-4" onClick={e => e.stopPropagation()}>
                  <div className="flex items-center justify-between mb-6">
                    <h3 className="text-white font-medium text-lg">Client Settings</h3>
                    <button onClick={closeClientModal} className="text-gray-400 hover:text-white">
                      <XCircle size={20} />
                    </button>
                  </div>

                  {/* Client Info */}
                  <div className="space-y-4">
                    <div>
                      <label className="text-gray-400 text-sm block mb-1">Client ID</label>
                      <div className="text-white font-mono text-sm">{selectedClient.client_id}</div>
                    </div>

                    <div>
                      <label className="text-gray-400 text-sm block mb-1">IP Addresses</label>
                      <div className="text-white text-sm">{selectedClient.ip_addresses?.join(', ') || 'Unknown'}</div>
                    </div>

                    {selectedClient.mac_address && (
                      <div>
                        <label className="text-gray-400 text-sm block mb-1">MAC Address</label>
                        <div className="text-white font-mono text-sm">{selectedClient.mac_address}</div>
                      </div>
                    )}

                    {/* Editable Name */}
                    <div>
                      <label className="text-gray-400 text-sm block mb-1">Display Name</label>
                      <div className="flex gap-2">
                        <input
                          type="text"
                          value={editClientName}
                          onChange={(e) => setEditClientName(e.target.value)}
                          placeholder="Enter a friendly name..."
                          className="flex-1 bg-gray-800 border border-gray-700 rounded px-3 py-2 text-white text-sm focus:outline-none focus:border-magnetic-primary"
                        />
                        <button
                          onClick={handleSaveClientName}
                          disabled={clientUpdateLoading || editClientName === (selectedClient.name || '')}
                          className="magnetic-button-primary px-3"
                        >
                          Save
                        </button>
                      </div>
                    </div>

                    {/* Toggles */}
                    <div className="border-t border-gray-700 pt-4 mt-4 space-y-3">
                      <h4 className="text-white font-medium text-sm">Protection Settings</h4>

                      {/* Filtering Toggle */}
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-white text-sm">DNS Filtering</span>
                          <p className="text-gray-500 text-xs">Block ads and trackers</p>
                        </div>
                        <button
                          onClick={() => handleUpdateClient({ filtering_enabled: !selectedClient.filtering_enabled })}
                          disabled={clientUpdateLoading}
                          className={`relative w-12 h-6 rounded-full transition-colors ${
                            selectedClient.filtering_enabled ? 'bg-green-500' : 'bg-gray-600'
                          } ${clientUpdateLoading ? 'opacity-50' : ''}`}
                        >
                          <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                            selectedClient.filtering_enabled ? 'left-7' : 'left-1'
                          }`} />
                        </button>
                      </div>

                      {/* Safe Browsing Toggle */}
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-white text-sm">Safe Browsing</span>
                          <p className="text-gray-500 text-xs">Block malicious websites</p>
                        </div>
                        <button
                          onClick={() => handleUpdateClient({ safe_browsing: !selectedClient.safe_browsing })}
                          disabled={clientUpdateLoading}
                          className={`relative w-12 h-6 rounded-full transition-colors ${
                            selectedClient.safe_browsing ? 'bg-green-500' : 'bg-gray-600'
                          } ${clientUpdateLoading ? 'opacity-50' : ''}`}
                        >
                          <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                            selectedClient.safe_browsing ? 'left-7' : 'left-1'
                          }`} />
                        </button>
                      </div>

                      {/* Parental Control Toggle */}
                      <div className="flex items-center justify-between">
                        <div>
                          <span className="text-white text-sm">Parental Control</span>
                          <p className="text-gray-500 text-xs">Block adult content</p>
                        </div>
                        <button
                          onClick={() => handleUpdateClient({ parental_control: !selectedClient.parental_control })}
                          disabled={clientUpdateLoading}
                          className={`relative w-12 h-6 rounded-full transition-colors ${
                            selectedClient.parental_control ? 'bg-green-500' : 'bg-gray-600'
                          } ${clientUpdateLoading ? 'opacity-50' : ''}`}
                        >
                          <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${
                            selectedClient.parental_control ? 'left-7' : 'left-1'
                          }`} />
                        </button>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="border-t border-gray-700 pt-4 mt-4">
                      <h4 className="text-white font-medium text-sm mb-3">Statistics</h4>
                      <div className="grid grid-cols-2 gap-4 text-sm">
                        <div>
                          <span className="text-gray-400">Total Queries</span>
                          <div className="text-white font-medium">{(selectedClient.queries_count ?? 0).toLocaleString()}</div>
                        </div>
                        <div>
                          <span className="text-gray-400">Blocked</span>
                          <div className="text-red-400 font-medium">{(selectedClient.blocked_count ?? 0).toLocaleString()}</div>
                        </div>
                        <div>
                          <span className="text-gray-400">Block Rate</span>
                          <div className="text-yellow-400 font-medium">
                            {selectedClient.queries_count > 0
                              ? ((selectedClient.blocked_count / selectedClient.queries_count) * 100).toFixed(1)
                              : 0}%
                          </div>
                        </div>
                        <div>
                          <span className="text-gray-400">Last Seen</span>
                          <div className="text-white">
                            {selectedClient.last_seen
                              ? new Date(selectedClient.last_seen).toLocaleString()
                              : 'Never'}
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="flex justify-end mt-6">
                    <button onClick={closeClientModal} className="magnetic-button-secondary">
                      Close
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'chat' && (
          <div className="magnetic-card p-4 h-[600px]">
            <ChatPanel
              sessionId={sessionId}
              context="dns"
              placeholder="Ask about DNS stats, block domains, investigate queries..."
            />
          </div>
        )}
      </div>
    </div>
  )
}
