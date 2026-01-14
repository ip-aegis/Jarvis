import { useState, useEffect, useMemo } from 'react'
import {
  BarChart3,
  TrendingUp,
  DollarSign,
  Zap,
  Hash,
  Clock,
  Download,
  RefreshCw,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from 'recharts'
import { api } from '../services/api'

// Types
interface FeatureUsage {
  feature: string
  request_count: number
  total_tokens: number
  cost_cents: number
}

interface ModelUsage {
  model: string
  request_count: number
  total_tokens: number
  cost_cents: number
}

interface UsageSummary {
  period_hours: number
  request_count: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  total_cost_cents: number
  total_cost_dollars: number
  by_feature: FeatureUsage[]
  by_model: ModelUsage[]
}

interface HourlyUsage {
  timestamp: string | null
  request_count: number
  total_tokens: number
  cost_cents: number
}

interface DailyUsage {
  date: string | null
  request_count: number
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  cost_cents: number
}

interface MonthlyUsage {
  year: number | null
  month: number | null
  month_name: string | null
  year_month: string | null
  request_count: number
  total_tokens: number
  prompt_tokens: number
  completion_tokens: number
  cost_cents: number
}

interface DetailedUsage {
  feature: string
  function_name: string | null
  model: string | null
  request_count: number
  prompt_tokens: number
  completion_tokens: number
  total_tokens: number
  cost_cents: number
  avg_tokens_per_request: number
}

interface UsageTrends {
  period_hours: number
  current_period: {
    start: string
    end: string
    request_count: number
    total_tokens: number
    cost_cents: number
    cost_dollars: number
  }
  previous_period: {
    start: string
    end: string
    request_count: number
    total_tokens: number
    cost_cents: number
    cost_dollars: number
  }
  percent_change: {
    request_count: number
    total_tokens: number
    cost: number
  }
}

type TabType = 'overview' | 'feature' | 'model' | 'history'
type TimeRange = 24 | 168 | 720

// Chart colors
const COLORS = ['#00bceb', '#6366f1', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899', '#14b8a6']

export default function Usage() {
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [timeRange, setTimeRange] = useState<TimeRange>(168) // Default 7 days
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  // Data state
  const [summary, setSummary] = useState<UsageSummary | null>(null)
  const [trends, setTrends] = useState<UsageTrends | null>(null)
  const [hourlyHistory, setHourlyHistory] = useState<HourlyUsage[]>([])
  const [dailyHistory, setDailyHistory] = useState<DailyUsage[]>([])
  const [monthlyHistory, setMonthlyHistory] = useState<MonthlyUsage[]>([])
  const [detailedUsage, setDetailedUsage] = useState<DetailedUsage[]>([])

  // Fetch all data
  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [summaryData, trendsData, historyData, monthlyData, detailedData] = await Promise.all([
        api.getUsageSummary(timeRange),
        api.getUsageTrends(timeRange),
        timeRange <= 168
          ? api.getUsageHistory(timeRange)
          : api.getUsageDailyHistory(Math.ceil(timeRange / 24)),
        api.getUsageMonthlyHistory(12),
        api.getUsageByFeature(timeRange),
      ])
      setSummary(summaryData)
      setTrends(trendsData)
      if (timeRange <= 168) {
        setHourlyHistory(historyData as HourlyUsage[])
        setDailyHistory([])
      } else {
        setDailyHistory(historyData as DailyUsage[])
        setHourlyHistory([])
      }
      setMonthlyHistory(monthlyData)
      setDetailedUsage(detailedData)
    } catch (err) {
      console.error('Failed to fetch usage data:', err)
      setError('Failed to load usage data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
    const interval = setInterval(fetchData, 60000) // Refresh every minute
    return () => clearInterval(interval)
  }, [timeRange])

  // Format cost in dollars
  const formatCost = (cents: number) => {
    if (cents >= 100) {
      return `$${(cents / 100).toFixed(2)}`
    }
    return `$${(cents / 100).toFixed(4)}`
  }

  // Format large numbers
  const formatNumber = (num: number) => {
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
    if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
    return num.toLocaleString()
  }

  // Format timestamp for charts
  const formatTimestamp = (timestamp: string | null) => {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    if (timeRange <= 24) {
      return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    }
    return date.toLocaleDateString([], { month: 'short', day: 'numeric' })
  }

  // Prepare chart data
  const chartData = useMemo(() => {
    if (timeRange <= 168 && hourlyHistory.length > 0) {
      return hourlyHistory.map(h => ({
        time: formatTimestamp(h.timestamp),
        tokens: h.total_tokens,
        cost: h.cost_cents / 100,
        requests: h.request_count,
      }))
    }
    if (dailyHistory.length > 0) {
      return dailyHistory.map(d => ({
        time: d.date ? new Date(d.date).toLocaleDateString([], { month: 'short', day: 'numeric' }) : '',
        tokens: d.total_tokens,
        cost: d.cost_cents / 100,
        requests: d.request_count,
      }))
    }
    return []
  }, [hourlyHistory, dailyHistory, timeRange])

  // Feature chart data
  const featureChartData = useMemo(() => {
    if (!summary) return []
    return summary.by_feature
      .sort((a, b) => b.cost_cents - a.cost_cents)
      .slice(0, 6)
      .map(f => ({
        name: f.feature.charAt(0).toUpperCase() + f.feature.slice(1),
        tokens: f.total_tokens,
        cost: f.cost_cents,
        requests: f.request_count,
      }))
  }, [summary])

  // Model chart data
  const modelChartData = useMemo(() => {
    if (!summary) return []
    return summary.by_model
      .sort((a, b) => b.cost_cents - a.cost_cents)
      .map(m => ({
        name: m.model.replace('gpt-', '').replace('-', ' '),
        value: m.cost_cents,
        tokens: m.total_tokens,
        requests: m.request_count,
      }))
  }, [summary])

  // Export to CSV
  const exportToCSV = () => {
    if (detailedUsage.length === 0) return

    const headers = ['Feature', 'Function', 'Model', 'Requests', 'Prompt Tokens', 'Completion Tokens', 'Total Tokens', 'Cost ($)', 'Avg Tokens/Request']
    const rows = detailedUsage.map(d => [
      d.feature,
      d.function_name || '',
      d.model || '',
      d.request_count,
      d.prompt_tokens,
      d.completion_tokens,
      d.total_tokens,
      (d.cost_cents / 100).toFixed(4),
      d.avg_tokens_per_request,
    ])

    const csv = [headers.join(','), ...rows.map(r => r.join(','))].join('\n')
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `llm-usage-${new Date().toISOString().split('T')[0]}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  // Render change indicator
  const ChangeIndicator = ({ value, inverse = false }: { value: number; inverse?: boolean }) => {
    const isPositive = inverse ? value < 0 : value > 0
    const isNegative = inverse ? value > 0 : value < 0
    const color = isPositive ? 'text-success' : isNegative ? 'text-error' : 'text-surface-400'
    const Icon = value > 0 ? ArrowUpRight : value < 0 ? ArrowDownRight : null

    return (
      <div className={`flex items-center text-sm ${color}`}>
        {Icon && <Icon className="w-4 h-4" />}
        <span>{Math.abs(value).toFixed(1)}%</span>
      </div>
    )
  }

  const tabs = [
    { id: 'overview' as const, name: 'Overview', icon: BarChart3 },
    { id: 'feature' as const, name: 'By Feature', icon: Zap },
    { id: 'model' as const, name: 'By Model', icon: Hash },
    { id: 'history' as const, name: 'History', icon: Clock },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">LLM Usage Analytics</h1>
          <p className="text-surface-300 mt-1">Token usage, costs, and trends</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Time range selector */}
          <div className="flex bg-surface-600 rounded-magnetic p-1">
            {[
              { value: 24 as TimeRange, label: '24h' },
              { value: 168 as TimeRange, label: '7d' },
              { value: 720 as TimeRange, label: '30d' },
            ].map(({ value, label }) => (
              <button
                key={value}
                onClick={() => setTimeRange(value)}
                className={`px-3 py-1.5 rounded-magnetic text-sm font-medium transition-colors ${
                  timeRange === value
                    ? 'bg-primary text-white'
                    : 'text-surface-300 hover:text-white'
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <button
            onClick={fetchData}
            className="p-2 rounded-magnetic bg-surface-600 text-surface-300 hover:text-white transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-5 h-5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-magnetic bg-error/10 border border-error/30 text-error">
          {error}
        </div>
      )}

      {/* Summary Cards */}
      {summary && trends && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-surface-400 text-sm">Total Cost</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {formatCost(summary.total_cost_cents)}
                </p>
                <ChangeIndicator value={trends.percent_change.cost} inverse />
              </div>
              <div className="p-3 rounded-magnetic bg-success/20 text-success">
                <DollarSign className="w-6 h-6" />
              </div>
            </div>
          </div>

          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-surface-400 text-sm">Total Tokens</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {formatNumber(summary.total_tokens)}
                </p>
                <ChangeIndicator value={trends.percent_change.total_tokens} />
              </div>
              <div className="p-3 rounded-magnetic bg-primary/20 text-primary">
                <Zap className="w-6 h-6" />
              </div>
            </div>
          </div>

          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-surface-400 text-sm">Requests</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {formatNumber(summary.request_count)}
                </p>
                <ChangeIndicator value={trends.percent_change.request_count} />
              </div>
              <div className="p-3 rounded-magnetic bg-warning/20 text-warning">
                <Hash className="w-6 h-6" />
              </div>
            </div>
          </div>

          <div className="magnetic-card">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-surface-400 text-sm">Avg Tokens/Request</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {summary.request_count > 0
                    ? Math.round(summary.total_tokens / summary.request_count).toLocaleString()
                    : '0'}
                </p>
                <p className="text-surface-500 text-sm">per request</p>
              </div>
              <div className="p-3 rounded-magnetic bg-info/20 text-info">
                <TrendingUp className="w-6 h-6" />
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-surface-600 pb-2">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-magnetic font-medium transition-colors ${
              activeTab === tab.id
                ? 'bg-surface-600 text-white'
                : 'text-surface-400 hover:text-white hover:bg-surface-700'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.name}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      <div className="mt-4">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Cost Over Time */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Cost Over Time</h3>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `$${v.toFixed(2)}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [`$${value.toFixed(4)}`, 'Cost']}
                    />
                    <Area type="monotone" dataKey="cost" stroke="#10b981" fill="url(#costGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-surface-400">
                  No data available
                </div>
              )}
            </div>

            {/* Token Usage Over Time */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Token Usage Over Time</h3>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="tokenGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00bceb" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00bceb" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => formatNumber(v)} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [formatNumber(value), 'Tokens']}
                    />
                    <Area type="monotone" dataKey="tokens" stroke="#00bceb" fill="url(#tokenGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-surface-400">
                  No data available
                </div>
              )}
            </div>

            {/* Top Features by Cost */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Cost by Feature</h3>
              {featureChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={featureChartData} layout="vertical">
                    <XAxis type="number" stroke="#6b7280" fontSize={12} tickFormatter={v => `$${(v/100).toFixed(2)}`} />
                    <YAxis type="category" dataKey="name" stroke="#6b7280" fontSize={12} width={80} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [`$${(value/100).toFixed(4)}`, 'Cost']}
                    />
                    <Bar dataKey="cost" fill="#00bceb" radius={[0, 4, 4, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-surface-400">
                  No data available
                </div>
              )}
            </div>

            {/* Model Distribution */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Cost by Model</h3>
              {modelChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={250}>
                  <PieChart>
                    <Pie
                      data={modelChartData}
                      cx="50%"
                      cy="50%"
                      innerRadius={60}
                      outerRadius={90}
                      paddingAngle={2}
                      dataKey="value"
                    >
                      {modelChartData.map((_, index) => (
                        <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                      ))}
                    </Pie>
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      itemStyle={{ color: '#fff' }}
                      formatter={(value: number) => [`$${(value/100).toFixed(4)}`, 'Cost']}
                    />
                    <Legend
                      formatter={(value) => <span className="text-surface-300">{value}</span>}
                    />
                  </PieChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-surface-400">
                  No data available
                </div>
              )}
            </div>
          </div>
        )}

        {/* By Feature Tab */}
        {activeTab === 'feature' && (
          <div className="magnetic-card">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-medium text-white">Usage by Feature & Function</h3>
              <button
                onClick={exportToCSV}
                className="flex items-center gap-2 px-3 py-1.5 rounded-magnetic bg-surface-600 text-surface-300 hover:text-white transition-colors text-sm"
              >
                <Download className="w-4 h-4" />
                Export CSV
              </button>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-surface-600">
                    <th className="text-left text-surface-400 font-medium py-3 px-4">Feature</th>
                    <th className="text-left text-surface-400 font-medium py-3 px-4">Function</th>
                    <th className="text-left text-surface-400 font-medium py-3 px-4">Model</th>
                    <th className="text-right text-surface-400 font-medium py-3 px-4">Requests</th>
                    <th className="text-right text-surface-400 font-medium py-3 px-4">Tokens</th>
                    <th className="text-right text-surface-400 font-medium py-3 px-4">Cost</th>
                    <th className="text-right text-surface-400 font-medium py-3 px-4">Avg/Req</th>
                  </tr>
                </thead>
                <tbody>
                  {detailedUsage.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="text-center text-surface-400 py-8">
                        No usage data for this period
                      </td>
                    </tr>
                  ) : (
                    detailedUsage.map((row, i) => (
                      <tr key={i} className="border-b border-surface-700 hover:bg-surface-700/50">
                        <td className="py-3 px-4 text-white capitalize">{row.feature}</td>
                        <td className="py-3 px-4 text-surface-300">{row.function_name || '-'}</td>
                        <td className="py-3 px-4 text-surface-300 text-sm">{row.model || '-'}</td>
                        <td className="py-3 px-4 text-right text-white">{row.request_count.toLocaleString()}</td>
                        <td className="py-3 px-4 text-right text-white">{formatNumber(row.total_tokens)}</td>
                        <td className="py-3 px-4 text-right text-success">{formatCost(row.cost_cents)}</td>
                        <td className="py-3 px-4 text-right text-surface-300">{row.avg_tokens_per_request.toLocaleString()}</td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* By Model Tab */}
        {activeTab === 'model' && summary && (
          <div className="space-y-6">
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Model Comparison</h3>
              {summary.by_model.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={summary.by_model.map(m => ({
                    name: m.model.replace('gpt-', '').replace('-', ' '),
                    tokens: m.total_tokens,
                    cost: m.cost_cents,
                    requests: m.request_count,
                  }))}>
                    <XAxis dataKey="name" stroke="#6b7280" fontSize={12} />
                    <YAxis yAxisId="left" stroke="#6b7280" fontSize={12} tickFormatter={v => formatNumber(v)} />
                    <YAxis yAxisId="right" orientation="right" stroke="#6b7280" fontSize={12} tickFormatter={v => `$${(v/100).toFixed(2)}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number, name: string) => {
                        if (name === 'cost') return [`$${(value/100).toFixed(4)}`, 'Cost']
                        return [formatNumber(value), name === 'tokens' ? 'Tokens' : 'Requests']
                      }}
                    />
                    <Legend />
                    <Bar yAxisId="left" dataKey="tokens" name="Tokens" fill="#00bceb" />
                    <Bar yAxisId="right" dataKey="cost" name="Cost" fill="#10b981" />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-surface-400">
                  No model data available
                </div>
              )}
            </div>

            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Model Details</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-surface-400 font-medium py-3 px-4">Model</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Requests</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Total Tokens</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Cost</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Cost/1K Tokens</th>
                    </tr>
                  </thead>
                  <tbody>
                    {summary.by_model.length === 0 ? (
                      <tr>
                        <td colSpan={5} className="text-center text-surface-400 py-8">
                          No model data for this period
                        </td>
                      </tr>
                    ) : (
                      summary.by_model.map((row, i) => (
                        <tr key={i} className="border-b border-surface-700 hover:bg-surface-700/50">
                          <td className="py-3 px-4 text-white">{row.model}</td>
                          <td className="py-3 px-4 text-right text-white">{row.request_count.toLocaleString()}</td>
                          <td className="py-3 px-4 text-right text-white">{formatNumber(row.total_tokens)}</td>
                          <td className="py-3 px-4 text-right text-success">{formatCost(row.cost_cents)}</td>
                          <td className="py-3 px-4 text-right text-surface-300">
                            {row.total_tokens > 0
                              ? `$${((row.cost_cents / row.total_tokens) * 1000 / 100).toFixed(4)}`
                              : '-'}
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* History Tab */}
        {activeTab === 'history' && (
          <div className="space-y-6">
            <div className="magnetic-card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-medium text-white">
                  {timeRange <= 168 ? 'Hourly Usage' : 'Daily Usage'}
                </h3>
                <button
                  onClick={exportToCSV}
                  className="flex items-center gap-2 px-3 py-1.5 rounded-magnetic bg-surface-600 text-surface-300 hover:text-white transition-colors text-sm"
                >
                  <Download className="w-4 h-4" />
                  Export CSV
                </button>
              </div>
              {chartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={400}>
                  <AreaChart data={chartData}>
                    <defs>
                      <linearGradient id="historyTokenGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#00bceb" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#00bceb" stopOpacity={0} />
                      </linearGradient>
                      <linearGradient id="historyCostGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="time" stroke="#6b7280" fontSize={12} />
                    <YAxis yAxisId="left" stroke="#6b7280" fontSize={12} tickFormatter={v => formatNumber(v)} />
                    <YAxis yAxisId="right" orientation="right" stroke="#6b7280" fontSize={12} tickFormatter={v => `$${v.toFixed(2)}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number, name: string) => {
                        if (name === 'Cost') return [`$${value.toFixed(4)}`, name]
                        return [formatNumber(value), name]
                      }}
                    />
                    <Legend />
                    <Area yAxisId="left" type="monotone" dataKey="tokens" name="Tokens" stroke="#00bceb" fill="url(#historyTokenGradient)" />
                    <Area yAxisId="right" type="monotone" dataKey="cost" name="Cost" stroke="#10b981" fill="url(#historyCostGradient)" />
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[400px] flex items-center justify-center text-surface-400">
                  No historical data available
                </div>
              )}
            </div>

            {/* Detailed history table */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Detailed History</h3>
              <div className="overflow-x-auto max-h-96 overflow-y-auto">
                <table className="w-full">
                  <thead className="sticky top-0 bg-surface-700">
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-surface-400 font-medium py-3 px-4">
                        {timeRange <= 168 ? 'Time' : 'Date'}
                      </th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Requests</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Tokens</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {chartData.length === 0 ? (
                      <tr>
                        <td colSpan={4} className="text-center text-surface-400 py-8">
                          No data available
                        </td>
                      </tr>
                    ) : (
                      [...chartData].reverse().map((row, i) => (
                        <tr key={i} className="border-b border-surface-700 hover:bg-surface-700/50">
                          <td className="py-3 px-4 text-white">{row.time}</td>
                          <td className="py-3 px-4 text-right text-white">{row.requests.toLocaleString()}</td>
                          <td className="py-3 px-4 text-right text-white">{formatNumber(row.tokens)}</td>
                          <td className="py-3 px-4 text-right text-success">${row.cost.toFixed(4)}</td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Monthly History */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Monthly Cost History</h3>
              {monthlyHistory.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={monthlyHistory.map(m => ({
                    month: m.month_name ? `${m.month_name.slice(0, 3)} ${m.year}` : m.year_month,
                    cost: m.cost_cents / 100,
                    tokens: m.total_tokens,
                    requests: m.request_count,
                  }))}>
                    <XAxis dataKey="month" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `$${v.toFixed(2)}`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      itemStyle={{ color: '#fff' }}
                      formatter={(value: number, name: string) => {
                        if (name === 'Cost') return [`$${value.toFixed(2)}`, name]
                        return [formatNumber(value), name]
                      }}
                    />
                    <Legend />
                    <Bar dataKey="cost" name="Cost" fill="#10b981" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-surface-400">
                  No monthly data available
                </div>
              )}
            </div>

            {/* Monthly Details Table */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Monthly Breakdown</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-surface-400 font-medium py-3 px-4">Month</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Requests</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Tokens</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Prompt</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Completion</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {monthlyHistory.length === 0 ? (
                      <tr>
                        <td colSpan={6} className="text-center text-surface-400 py-8">
                          No monthly data available
                        </td>
                      </tr>
                    ) : (
                      [...monthlyHistory].reverse().map((row, i) => (
                        <tr key={i} className="border-b border-surface-700 hover:bg-surface-700/50">
                          <td className="py-3 px-4 text-white font-medium">
                            {row.month_name} {row.year}
                          </td>
                          <td className="py-3 px-4 text-right text-white">{row.request_count.toLocaleString()}</td>
                          <td className="py-3 px-4 text-right text-white">{formatNumber(row.total_tokens)}</td>
                          <td className="py-3 px-4 text-right text-surface-300">{formatNumber(row.prompt_tokens)}</td>
                          <td className="py-3 px-4 text-right text-surface-300">{formatNumber(row.completion_tokens)}</td>
                          <td className="py-3 px-4 text-right text-success">{formatCost(row.cost_cents)}</td>
                        </tr>
                      ))
                    )}
                    {/* Monthly Total Row */}
                    {monthlyHistory.length > 0 && (
                      <tr className="border-t-2 border-surface-500 bg-surface-700/30">
                        <td className="py-3 px-4 text-white font-bold">Total</td>
                        <td className="py-3 px-4 text-right text-white font-bold">
                          {monthlyHistory.reduce((sum, m) => sum + m.request_count, 0).toLocaleString()}
                        </td>
                        <td className="py-3 px-4 text-right text-white font-bold">
                          {formatNumber(monthlyHistory.reduce((sum, m) => sum + m.total_tokens, 0))}
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300 font-bold">
                          {formatNumber(monthlyHistory.reduce((sum, m) => sum + m.prompt_tokens, 0))}
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300 font-bold">
                          {formatNumber(monthlyHistory.reduce((sum, m) => sum + m.completion_tokens, 0))}
                        </td>
                        <td className="py-3 px-4 text-right text-success font-bold">
                          {formatCost(monthlyHistory.reduce((sum, m) => sum + m.cost_cents, 0))}
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
