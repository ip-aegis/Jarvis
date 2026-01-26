import { useState, useEffect, useMemo } from 'react'
import {
  Footprints,
  Heart,
  Flame,
  MapPin,
  Activity,
  TrendingUp,
  TrendingDown,
  Scale,
  Utensils,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  Settings,
  X,
  Loader2,
  Clock,
  Database,
  Wifi,
  WifiOff,
  Timer,
  Wind,
  Zap,
  Sparkles,
  AlertTriangle,
  Star,
  ThumbsUp,
  Lightbulb,
  Moon,
  Dumbbell,
} from 'lucide-react'
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from 'recharts'
import { api } from '../services/api'

// Types
interface SummaryCard {
  title: string
  value: string
  unit?: string
  change?: number
  change_direction?: 'up' | 'down' | 'neutral'
  icon?: string
}

interface HealthSummary {
  date: string
  period: string
  cards: SummaryCard[]
  steps?: number
  steps_goal: number
  active_calories?: number
  exercise_minutes?: number
  stand_hours?: number
  distance_km?: number
  resting_heart_rate?: number
  avg_heart_rate?: number
  sleep_hours?: number
  weight_kg?: number
  // Vitals
  blood_oxygen_avg?: number
  vo2_max?: number
  respiratory_rate?: number
  hrv_avg?: number
}

interface StepsDataPoint {
  date: string
  steps: number
  distance_meters?: number
  flights_climbed?: number
}

interface StepsHistory {
  period: string
  data: StepsDataPoint[]
  total_steps: number
  avg_daily_steps: number
  best_day?: StepsDataPoint
  goal_met_days: number
  steps_goal: number
}

interface HeartRateSummary {
  date: string
  resting_hr?: number
  avg_hr?: number
  max_hr?: number
  min_hr?: number
  hrv_avg?: number
}

interface HeartRateHistory {
  period: string
  daily_summary: HeartRateSummary[]
  current_resting_hr?: number
  avg_resting_hr?: number
}

interface BodyMeasurement {
  timestamp: string
  weight_kg?: number
  body_fat_percentage?: number
  bmi?: number
}

interface BodyHistory {
  period: string
  measurements: BodyMeasurement[]
  current_weight_kg?: number
  weight_change_kg?: number
  weight_trend?: 'gaining' | 'losing' | 'stable'
  current_bmi?: number
  current_body_fat?: number
}

interface UploadSummary {
  upload_id: string
  status: 'processing' | 'completed' | 'failed'
  source: string
  started_at: string
  completed_at?: string
  records_processed: number
  records_inserted: number
  records_duplicate: number
  data_start_date?: string
  data_end_date?: string
  error_message?: string
}

interface SyncStatus {
  last_sync?: string
  total_metrics: number
  total_workouts: number
  total_sleep_records: number
  total_body_measurements: number
  data_range_start?: string
  data_range_end?: string
  uploads_pending: number
  uploads_processing: number
  uploads_failed: number
  active_uploads: UploadSummary[]
  recent_uploads: UploadSummary[]
}

interface SyncEvent {
  event: 'sync_started' | 'sync_completed' | 'sync_failed' | 'status' | 'heartbeat'
  upload_id?: string
  timestamp: string
  records_processed?: number
  records_inserted?: number
  records_duplicate?: number
  error?: string
}

interface TrendComparison {
  metric: string
  current_value: number
  previous_value: number
  change_absolute: number
  change_percentage: number
  trend: 'improving' | 'declining' | 'stable'
}

interface HealthTrends {
  period: string
  comparison_period: string
  trends: TrendComparison[]
}

interface NutritionDay {
  date: string
  calories?: number
  protein_grams?: number
  carbs_grams?: number
  fat_grams?: number
  water_ml?: number
}

interface NutritionHistory {
  period: string
  data: NutritionDay[]
  avg_daily_calories?: number
  avg_daily_protein?: number
  calorie_goal?: number
}

interface MicronutrientData {
  vitamin_a_mcg?: number
  vitamin_c_mg?: number
  vitamin_d_mcg?: number
  vitamin_e_mg?: number
  vitamin_k_mcg?: number
  vitamin_b6_mg?: number
  vitamin_b12_mcg?: number
  thiamin_mg?: number
  riboflavin_mg?: number
  niacin_mg?: number
  folate_mcg?: number
  pantothenic_acid_mg?: number
  biotin_mcg?: number
  calcium_mg?: number
  iron_mg?: number
  magnesium_mg?: number
  phosphorus_mg?: number
  potassium_mg?: number
  sodium_mg?: number
  zinc_mg?: number
  copper_mg?: number
  manganese_mg?: number
  selenium_mcg?: number
  chromium_mcg?: number
  molybdenum_mcg?: number
  iodine_mcg?: number
  cholesterol_mg?: number
  saturated_fat_grams?: number
  monounsaturated_fat_grams?: number
  polyunsaturated_fat_grams?: number
  caffeine_mg?: number
}

interface DetailedNutritionHistory {
  period: string
  data: Array<NutritionDay & { micronutrients: MicronutrientData }>
  daily_values: Record<string, number>
  avg_daily_micronutrients: MicronutrientData
}

interface VitalsDataPoint {
  date: string
  blood_oxygen_avg?: number
  blood_oxygen_min?: number
  respiratory_rate?: number
  vo2_max?: number
  body_temperature?: number
}

interface VitalsHistory {
  period: string
  data: VitalsDataPoint[]
  current_spo2?: number
  avg_spo2?: number
  min_spo2?: number
  current_vo2_max?: number
  vo2_max_trend?: 'improving' | 'stable' | 'declining'
  avg_respiratory_rate?: number
}

interface MobilityDataPoint {
  date: string
  walking_speed_kmh?: number
  step_length_cm?: number
  walking_asymmetry_pct?: number
  double_support_pct?: number
  stair_speed_up?: number
  stair_speed_down?: number
}

interface MobilityHistory {
  period: string
  data: MobilityDataPoint[]
  avg_walking_speed_kmh?: number
  avg_step_length_cm?: number
  avg_asymmetry_pct?: number
  asymmetry_status?: 'normal' | 'elevated' | 'concerning'
}

interface SleepStage {
  stage: string
  minutes: number
  percentage: number
}

interface SleepSession {
  date: string
  start_time: string
  end_time: string
  total_minutes: number
  time_in_bed_minutes: number
  sleep_efficiency?: number
  stages: SleepStage[]
  avg_heart_rate?: number
  respiratory_rate?: number
}

interface SleepHistory {
  period: string
  data: SleepSession[]
  avg_sleep_hours: number
  avg_time_in_bed_hours: number
  avg_sleep_efficiency?: number
  sleep_goal_hours: number
  goal_met_days: number
}

interface WorkoutSummary {
  workout_id: string
  workout_type: string
  date: string
  duration_minutes: number
  calories_burned?: number
  distance_meters?: number
  avg_heart_rate?: number
  max_heart_rate?: number
  indoor?: boolean
}

interface WorkoutHistory {
  period: string
  workouts: WorkoutSummary[]
  total_workouts: number
  total_duration_minutes: number
  total_calories_burned: number
  total_distance_meters: number
  workouts_by_type: Record<string, number>
  avg_workouts_per_week: number
}

interface HealthDiagnostics {
  total_metrics: number
  total_workouts: number
  total_sleep_records: number
  total_body_measurements: number
  data_range_start?: string
  data_range_end?: string
  metric_types: Array<{
    metric_type: string
    record_count: number
    first_date?: string
    last_date?: string
  }>
  collection_status: Array<{
    category: string
    has_data: boolean
    metric_types: string[]
    total_records: number
    warning?: string
  }>
  missing_data_warnings: string[]
}

interface RedFlag {
  issue: string
  severity: 'low' | 'medium' | 'high'
  metric: string
  explanation: string
  suggestion: string
}

interface GreenFlag {
  achievement: string
  metric: string
  explanation: string
}

interface PointOfInterest {
  observation: string
  context: string
  recommendation?: string
}

interface HealthAssessment {
  id: string
  period_type: 'daily' | 'weekly' | 'monthly'
  period_start: string
  period_end: string
  summary: string
  red_flags: RedFlag[]
  green_flags: GreenFlag[]
  points_of_interest: PointOfInterest[]
  data_snapshot: Record<string, unknown>
  generated_at: string
  expires_at: string
  user_rating?: number
  user_feedback?: string
  model_used: string
  cost_cents: number
  error?: string
  // Insufficient data response fields
  insufficient_data?: boolean
  data_status?: {
    days_available: number
    days_required: number
    metrics_available: number
    metrics_required: number
  }
}

type TabType = 'overview' | 'activity' | 'heart' | 'sleep' | 'workouts' | 'body' | 'nutrition' | 'vitals' | 'insights'
type AssessmentPeriod = 'daily' | 'weekly' | 'monthly'
type TimeRange = 1 | 7 | 30 | 90

export default function Health() {
  const [activeTab, setActiveTab] = useState<TabType>('overview')
  const [timeRange, setTimeRange] = useState<TimeRange>(7)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showConfig, setShowConfig] = useState(false)

  // Data state
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [summary, setSummary] = useState<HealthSummary | null>(null)

  // WebSocket sync indicator state
  const [wsConnected, setWsConnected] = useState(false)
  const [activeSyncs, setActiveSyncs] = useState<Map<string, { started: Date; status: string }>>(new Map())
  const [lastSyncEvent, setLastSyncEvent] = useState<SyncEvent | null>(null)
  const [showSyncDetails, setShowSyncDetails] = useState(false)
  const [stepsHistory, setStepsHistory] = useState<StepsHistory | null>(null)
  const [heartRateHistory, setHeartRateHistory] = useState<HeartRateHistory | null>(null)
  const [bodyHistory, setBodyHistory] = useState<BodyHistory | null>(null)
  const [nutritionHistory, setNutritionHistory] = useState<NutritionHistory | null>(null)
  const [detailedNutrition, setDetailedNutrition] = useState<DetailedNutritionHistory | null>(null)
  const [vitalsHistory, setVitalsHistory] = useState<VitalsHistory | null>(null)
  const [mobilityHistory, setMobilityHistory] = useState<MobilityHistory | null>(null)
  const [sleepHistory, setSleepHistory] = useState<SleepHistory | null>(null)
  const [workoutHistory, setWorkoutHistory] = useState<WorkoutHistory | null>(null)
  const [trends, setTrends] = useState<HealthTrends | null>(null)
  const [showMicronutrients, setShowMicronutrients] = useState(false)
  const [diagnostics, setDiagnostics] = useState<HealthDiagnostics | null>(null)
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false)

  // Assessment state
  const [assessmentPeriod, setAssessmentPeriod] = useState<AssessmentPeriod>('weekly')
  const [assessment, setAssessment] = useState<HealthAssessment | null>(null)
  const [loadingAssessment, setLoadingAssessment] = useState(false)
  const [assessmentError, setAssessmentError] = useState<string | null>(null)

  // Fetch all data
  const fetchData = async () => {
    setLoading(true)
    setError(null)
    try {
      const [statusData, summaryData, stepsData, hrData, bodyData, nutritionData, detailedNutritionData, vitalsData, mobilityData, sleepData, workoutData, trendsData, diagnosticsData] =
        await Promise.all([
          api.getHealthSyncStatus(),
          api.getHealthSummary(),
          api.getStepsHistory(timeRange),
          api.getHeartRateHistory(timeRange),
          api.getBodyHistory(timeRange),
          api.getNutritionHistory(timeRange),
          api.getDetailedNutrition(timeRange),
          api.getVitals(timeRange),
          api.getMobility(timeRange),
          api.getSleepHistory(timeRange),
          api.getWorkoutHistory(Math.max(timeRange, 30)), // Workouts benefit from longer history
          api.getHealthTrends(Math.min(timeRange, 30)),
          api.getHealthDiagnostics(),
        ])
      setSyncStatus(statusData)
      setSummary(summaryData)
      setStepsHistory(stepsData)
      setHeartRateHistory(hrData)
      setBodyHistory(bodyData)
      setNutritionHistory(nutritionData)
      setDetailedNutrition(detailedNutritionData)
      setVitalsHistory(vitalsData)
      setMobilityHistory(mobilityData)
      setSleepHistory(sleepData)
      setWorkoutHistory(workoutData)
      setTrends(trendsData)
      setDiagnostics(diagnosticsData)
    } catch (err) {
      console.error('Failed to fetch health data:', err)
      setError('Failed to load health data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchData()
  }, [timeRange])

  // WebSocket connection for real-time sync updates
  useEffect(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/health/ws/sync`

    let ws: WebSocket | null = null
    let reconnectTimeout: number | null = null
    let pingInterval: number | null = null

    const connect = () => {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('Health sync WebSocket connected')
        setWsConnected(true)
        // Start ping interval to keep connection alive
        pingInterval = window.setInterval(() => {
          if (ws?.readyState === WebSocket.OPEN) {
            ws.send('ping')
          }
        }, 25000)
      }

      ws.onclose = () => {
        console.log('Health sync WebSocket disconnected')
        setWsConnected(false)
        if (pingInterval) {
          clearInterval(pingInterval)
          pingInterval = null
        }
        // Reconnect after 5 seconds
        reconnectTimeout = window.setTimeout(connect, 5000)
      }

      ws.onerror = (error) => {
        console.error('Health sync WebSocket error:', error)
      }

      ws.onmessage = (event) => {
        try {
          const data: SyncEvent = JSON.parse(event.data)
          setLastSyncEvent(data)

          if (data.event === 'sync_started' && data.upload_id) {
            setActiveSyncs(prev => {
              const newMap = new Map(prev)
              newMap.set(data.upload_id!, { started: new Date(), status: 'processing' })
              return newMap
            })
          } else if (data.event === 'sync_completed' && data.upload_id) {
            setActiveSyncs(prev => {
              const newMap = new Map(prev)
              newMap.delete(data.upload_id!)
              return newMap
            })
            // Refresh data after sync completes
            fetchData()
          } else if (data.event === 'sync_failed' && data.upload_id) {
            setActiveSyncs(prev => {
              const newMap = new Map(prev)
              newMap.set(data.upload_id!, { started: new Date(), status: 'failed' })
              return newMap
            })
            // Remove failed sync indicator after 10 seconds
            setTimeout(() => {
              setActiveSyncs(prev => {
                const newMap = new Map(prev)
                newMap.delete(data.upload_id!)
                return newMap
              })
            }, 10000)
          } else if (data.event === 'status') {
            // Initial status - check for active uploads
            const statusData = data as unknown as SyncStatus
            if (statusData.active_uploads?.length > 0) {
              setActiveSyncs(new Map(
                statusData.active_uploads.map(u => [u.upload_id, { started: new Date(u.started_at), status: u.status }])
              ))
            }
          }
        } catch (e) {
          // Ignore non-JSON messages (like "pong")
        }
      }
    }

    connect()

    return () => {
      if (reconnectTimeout) {
        clearTimeout(reconnectTimeout)
      }
      if (pingInterval) {
        clearInterval(pingInterval)
      }
      if (ws) {
        ws.close()
      }
    }
  }, [])

  // Polling fallback when WebSocket is disconnected and we have active syncs
  useEffect(() => {
    // Only poll if WebSocket is disconnected AND we have active syncs
    if (wsConnected || activeSyncs.size === 0) {
      return
    }

    const pollInterval = setInterval(async () => {
      const uploadIds = Array.from(activeSyncs.keys())

      for (const uploadId of uploadIds) {
        try {
          const status = await api.getHealthUploadStatus(uploadId)

          if (status.status === 'completed') {
            // Remove from active syncs
            setActiveSyncs(prev => {
              const newMap = new Map(prev)
              newMap.delete(uploadId)
              return newMap
            })
            // Set last sync event for notification
            setLastSyncEvent({
              event: 'sync_completed',
              upload_id: uploadId,
              timestamp: new Date().toISOString(),
              records_processed: status.records_processed,
              records_inserted: status.records_inserted,
              records_duplicate: status.records_duplicate,
            })
            // Refresh data
            fetchData()
          } else if (status.status === 'failed') {
            // Mark as failed
            setActiveSyncs(prev => {
              const newMap = new Map(prev)
              newMap.set(uploadId, { started: new Date(), status: 'failed' })
              return newMap
            })
            // Set last sync event for notification
            setLastSyncEvent({
              event: 'sync_failed',
              upload_id: uploadId,
              timestamp: new Date().toISOString(),
              error: status.error_message || 'Upload failed',
            })
            // Remove failed sync indicator after 10 seconds
            setTimeout(() => {
              setActiveSyncs(prev => {
                const newMap = new Map(prev)
                newMap.delete(uploadId)
                return newMap
              })
            }, 10000)
          }
          // If still processing, update the record count
          else if (status.status === 'processing') {
            setActiveSyncs(prev => {
              const existing = prev.get(uploadId)
              if (existing) {
                const newMap = new Map(prev)
                newMap.set(uploadId, {
                  ...existing,
                  status: 'processing',
                })
                return newMap
              }
              return prev
            })
          }
        } catch (err) {
          // Upload not found or error - remove from tracking
          console.warn(`Failed to poll upload ${uploadId}:`, err)
          setActiveSyncs(prev => {
            const newMap = new Map(prev)
            newMap.delete(uploadId)
            return newMap
          })
        }
      }
    }, 3000) // Poll every 3 seconds

    return () => clearInterval(pollInterval)
  }, [wsConnected, activeSyncs.size])

  // Format number with commas
  const formatNumber = (num: number) => num.toLocaleString()

  // Format date - handles date-only strings (YYYY-MM-DD) correctly
  const formatDate = (dateStr: string) => {
    let date: Date
    // Date-only strings should be parsed as local dates to prevent timezone shift
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [year, month, day] = dateStr.split('-').map(Number)
      date = new Date(year, month - 1, day)
    } else {
      date = new Date(dateStr)
    }
    return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
  }

  // Prepare steps chart data
  const stepsChartData = useMemo(() => {
    if (!stepsHistory) return []
    return stepsHistory.data.map(d => ({
      date: formatDate(d.date),
      steps: d.steps,
      goal: stepsHistory.steps_goal,
    }))
  }, [stepsHistory])

  // Prepare heart rate chart data
  const hrChartData = useMemo(() => {
    if (!heartRateHistory) return []
    return heartRateHistory.daily_summary.map(d => ({
      date: formatDate(d.date),
      resting: d.resting_hr,
      avg: d.avg_hr,
      max: d.max_hr,
      min: d.min_hr,
    }))
  }, [heartRateHistory])

  // Prepare body chart data
  const bodyChartData = useMemo(() => {
    if (!bodyHistory) return []
    return bodyHistory.measurements.map(m => ({
      date: formatDate(m.timestamp),
      weight: m.weight_kg,
      bodyFat: m.body_fat_percentage,
    }))
  }, [bodyHistory])

  // Prepare nutrition chart data
  const nutritionChartData = useMemo(() => {
    if (!nutritionHistory) return []
    return nutritionHistory.data.map(d => ({
      date: formatDate(d.date),
      calories: d.calories || 0,
      protein: d.protein_grams || 0,
      carbs: d.carbs_grams || 0,
      fat: d.fat_grams || 0,
      water: d.water_ml || 0, // Already in fl oz from backend
    }))
  }, [nutritionHistory])

  // Get today's nutrition
  const todayNutrition = useMemo(() => {
    if (!nutritionHistory?.data.length) return null
    return nutritionHistory.data[nutritionHistory.data.length - 1]
  }, [nutritionHistory])

  // Get latest HRV value
  const latestHrv = useMemo(() => {
    if (!heartRateHistory?.daily_summary?.length) return null
    // Find the most recent day with HRV data
    for (let i = heartRateHistory.daily_summary.length - 1; i >= 0; i--) {
      if (heartRateHistory.daily_summary[i].hrv_avg) {
        return heartRateHistory.daily_summary[i].hrv_avg
      }
    }
    return null
  }, [heartRateHistory])

  // Calculate total distance and flights from steps history
  const activityTotals = useMemo(() => {
    if (!stepsHistory?.data?.length) return { totalDistance: 0, totalFlights: 0, avgDailyDistance: 0 }
    const totalDistance = stepsHistory.data.reduce((sum, d) => sum + (d.distance_meters || 0), 0)
    const totalFlights = stepsHistory.data.reduce((sum, d) => sum + (d.flights_climbed || 0), 0)
    const avgDailyDistance = totalDistance / stepsHistory.data.length
    return { totalDistance, totalFlights, avgDailyDistance }
  }, [stepsHistory])

  // Steps progress percentage
  const stepsProgress = summary?.steps
    ? Math.min((summary.steps / summary.steps_goal) * 100, 100)
    : 0

  // Fetch assessment when period changes or tab is selected
  const fetchAssessment = async (forceRefresh = false) => {
    setLoadingAssessment(true)
    setAssessmentError(null)
    try {
      const data = await api.getHealthAssessment(assessmentPeriod, undefined, forceRefresh)
      // Check for insufficient data response
      if (data.insufficient_data) {
        const status = data.data_status
        let errorMsg = data.error || 'Insufficient data for assessment'
        if (status) {
          errorMsg = `Need more data: ${status.days_available}/${status.days_required} days and ${status.metrics_available}/${status.metrics_required} metric types available. Keep syncing your health data to get insights!`
        }
        setAssessmentError(errorMsg)
        setAssessment(null)
      } else {
        setAssessment(data)
      }
    } catch (err) {
      console.error('Failed to fetch assessment:', err)
      setAssessmentError('Failed to load health assessment')
      setAssessment(null)
    } finally {
      setLoadingAssessment(false)
    }
  }

  // Fetch assessment when tab changes to insights or period changes
  useEffect(() => {
    if (activeTab === 'insights') {
      fetchAssessment()
    }
  }, [activeTab, assessmentPeriod])

  // Helper to check if a category has data
  const hasData = useMemo(() => {
    if (!diagnostics) return { activity: true, heart: true, vitals: true, mobility: true, nutrition: true, body: true, sleep: true, workouts: true }
    const statusMap: Record<string, boolean> = {}
    diagnostics.collection_status.forEach(s => {
      statusMap[s.category.toLowerCase()] = s.has_data
    })
    return {
      activity: statusMap['activity'] ?? false,
      heart: statusMap['heart'] ?? false,
      vitals: statusMap['vitals'] ?? false,
      mobility: statusMap['mobility'] ?? false,
      nutrition: statusMap['nutrition'] ?? false,
      body: (diagnostics.total_body_measurements ?? 0) > 0,
      sleep: (diagnostics.total_sleep_records ?? 0) > 0,
      workouts: (diagnostics.total_workouts ?? 0) > 0,
    }
  }, [diagnostics])

  // Filter tabs based on available data
  const tabs = useMemo(() => {
    const allTabs = [
      { id: 'overview' as const, name: 'Overview', icon: Activity, show: true },
      { id: 'activity' as const, name: 'Activity', icon: Footprints, show: hasData.activity },
      { id: 'heart' as const, name: 'Heart', icon: Heart, show: hasData.heart },
      { id: 'sleep' as const, name: 'Sleep', icon: Moon, show: hasData.sleep },
      { id: 'workouts' as const, name: 'Workouts', icon: Dumbbell, show: hasData.workouts },
      { id: 'vitals' as const, name: 'Vitals', icon: Wind, show: hasData.vitals || hasData.mobility },
      { id: 'body' as const, name: 'Body', icon: Scale, show: hasData.body },
      { id: 'nutrition' as const, name: 'Nutrition', icon: Utensils, show: hasData.nutrition },
      { id: 'insights' as const, name: 'AI Insights', icon: Sparkles, show: true },
    ]
    return allTabs.filter(tab => tab.show)
  }, [hasData])

  // Switch to first available tab if current tab becomes hidden
  useEffect(() => {
    if (!diagnostics) return
    const availableTabs = tabs.map(t => t.id)
    if (!availableTabs.includes(activeTab) && availableTabs.length > 0) {
      setActiveTab(availableTabs[0])
    }
  }, [tabs, activeTab, diagnostics])

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Health</h1>
          <p className="text-surface-300 mt-1">Apple Health data and insights</p>
        </div>
        <div className="flex items-center gap-3">
          {/* Time range selector */}
          <div className="flex bg-surface-600 rounded-magnetic p-1">
            {[
              { value: 1 as TimeRange, label: '24h' },
              { value: 7 as TimeRange, label: '7d' },
              { value: 30 as TimeRange, label: '30d' },
              { value: 90 as TimeRange, label: '90d' },
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
          <button
            onClick={() => setShowConfig(true)}
            className="p-2 rounded-magnetic bg-surface-600 text-surface-300 hover:text-white transition-colors"
            title="Webhook Configuration"
          >
            <Settings className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* Config Modal */}
      {showConfig && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="magnetic-card bg-surface-800 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-medium text-white">Health Data Configuration</h2>
              <button
                onClick={() => setShowConfig(false)}
                className="p-1 rounded-magnetic text-surface-400 hover:text-white hover:bg-surface-700 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Webhook Setup Section */}
            <div className="mb-6">
              <h3 className="text-white font-medium mb-2">Webhook Setup</h3>
              <p className="text-surface-300 text-sm mb-4">
                Configure Health Auto Export iOS app to sync your Apple Health data automatically.
              </p>
              <ol className="text-sm text-surface-300 space-y-2 list-decimal list-inside mb-4">
                <li>
                  Install{' '}
                  <a
                    href="https://apps.apple.com/app/health-auto-export/id1115567069"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary hover:underline"
                  >
                    Health Auto Export
                  </a>{' '}
                  from the App Store ($2.99)
                </li>
                <li>Open the app and go to <span className="text-white">Automations</span></li>
                <li>Create a new REST API automation with these settings:</li>
              </ol>
              <div className="p-3 bg-surface-900 rounded-magnetic text-sm font-mono space-y-2">
                <div className="flex justify-between items-center">
                  <span className="text-surface-500">URL:</span>
                  <code className="text-primary">http://10.10.20.235:8000/api/health/webhook</code>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-500">Method:</span>
                  <span className="text-white">POST</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-500">Format:</span>
                  <span className="text-white">JSON</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-500">Data Types:</span>
                  <span className="text-white">All (recommended)</span>
                </div>
                <div className="flex justify-between items-center">
                  <span className="text-surface-500">Interval:</span>
                  <span className="text-white">Every 15 minutes</span>
                </div>
              </div>
            </div>

            {/* Data Diagnostics Section */}
            <div className="border-t border-surface-700 pt-4">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-white font-medium">Data Diagnostics</h3>
                <button
                  onClick={async () => {
                    setLoadingDiagnostics(true)
                    try {
                      const data = await api.getHealthDiagnostics()
                      setDiagnostics(data)
                    } catch (err) {
                      console.error('Failed to fetch diagnostics:', err)
                    } finally {
                      setLoadingDiagnostics(false)
                    }
                  }}
                  disabled={loadingDiagnostics}
                  className="magnetic-button-secondary text-sm py-1.5 px-3 flex items-center gap-2"
                >
                  {loadingDiagnostics ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  Check Data Status
                </button>
              </div>

              {diagnostics ? (
                <div className="space-y-4">
                  {/* Warnings */}
                  {diagnostics.missing_data_warnings.length > 0 && (
                    <div className="p-3 bg-warning/10 border border-warning/30 rounded-magnetic">
                      <p className="text-warning text-sm font-medium mb-2">Missing Data Warnings</p>
                      <ul className="text-warning/80 text-sm space-y-1">
                        {diagnostics.missing_data_warnings.map((warning, i) => (
                          <li key={i} className="flex items-center gap-2">
                            <AlertCircle className="w-3 h-3 flex-shrink-0" />
                            {warning}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {/* Collection Status by Category */}
                  <div className="grid grid-cols-2 gap-3">
                    {diagnostics.collection_status.map(status => (
                      <div key={status.category} className="p-3 bg-surface-700 rounded-magnetic">
                        <div className="flex items-center gap-2 mb-1">
                          {status.has_data ? (
                            <CheckCircle className="w-4 h-4 text-success" />
                          ) : (
                            <AlertCircle className="w-4 h-4 text-surface-500" />
                          )}
                          <span className="text-white text-sm font-medium">{status.category}</span>
                        </div>
                        <p className="text-surface-400 text-xs">
                          {status.has_data
                            ? `${status.total_records.toLocaleString()} records`
                            : status.warning || 'No data'}
                        </p>
                        {status.has_data && status.metric_types.length > 0 && (
                          <p className="text-surface-500 text-xs mt-1 truncate" title={status.metric_types.join(', ')}>
                            {status.metric_types.slice(0, 3).join(', ')}
                            {status.metric_types.length > 3 && ` +${status.metric_types.length - 3} more`}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>

                  {/* Data Range */}
                  {diagnostics.data_range_start && diagnostics.data_range_end && (
                    <div className="p-3 bg-surface-700 rounded-magnetic">
                      <p className="text-surface-400 text-xs mb-1">Data Range</p>
                      <p className="text-white text-sm">
                        {new Date(diagnostics.data_range_start).toLocaleDateString()} -{' '}
                        {new Date(diagnostics.data_range_end).toLocaleDateString()}
                      </p>
                    </div>
                  )}

                  {/* Totals */}
                  <div className="flex gap-4 text-xs text-surface-400">
                    <span>{diagnostics.total_metrics.toLocaleString()} metrics</span>
                    <span>{diagnostics.total_workouts} workouts</span>
                    <span>{diagnostics.total_sleep_records} sleep records</span>
                    <span>{diagnostics.total_body_measurements} body measurements</span>
                  </div>
                </div>
              ) : (
                <p className="text-surface-500 text-sm">
                  Click "Check Data Status" to see what data types are being collected.
                </p>
              )}
            </div>

            <p className="text-surface-500 text-xs mt-4 pt-4 border-t border-surface-700">
              Data syncs automatically when your iPhone is connected to your home WiFi network.
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-magnetic bg-error/10 border border-error/30 text-error flex items-center gap-2">
          <AlertCircle className="w-5 h-5" />
          {error}
        </div>
      )}

      {/* Sync Status Bar */}
      <div className="magnetic-card !p-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4 text-sm">
            {/* Active sync indicator */}
            {activeSyncs.size > 0 ? (
              <div className="flex items-center gap-2">
                <div className="relative">
                  <Loader2 className="w-5 h-5 text-primary animate-spin" />
                  <div className="absolute -top-1 -right-1 w-2.5 h-2.5 bg-primary rounded-full animate-pulse" />
                </div>
                <span className="text-white font-medium">
                  Syncing health data...
                </span>
                <span className="text-surface-400">
                  ({activeSyncs.size} {activeSyncs.size === 1 ? 'upload' : 'uploads'})
                </span>
              </div>
            ) : syncStatus?.last_sync ? (
              <div className="flex items-center gap-1.5">
                <CheckCircle className="w-4 h-4 text-success" />
                <span className="text-surface-300">Last sync: {new Date(syncStatus.last_sync).toLocaleString()}</span>
              </div>
            ) : (
              <div className="flex items-center gap-1.5">
                <AlertCircle className="w-4 h-4 text-warning" />
                <span className="text-surface-400">No data synced yet</span>
              </div>
            )}

            {/* Data counts */}
            {syncStatus && (
              <>
                <span className="text-surface-600">|</span>
                <span className="text-surface-400">
                  <Database className="w-3.5 h-3.5 inline mr-1" />
                  {formatNumber(syncStatus.total_metrics)} metrics
                </span>
                <span className="text-surface-400">
                  {formatNumber(syncStatus.total_workouts)} workouts
                </span>
              </>
            )}
          </div>

          <div className="flex items-center gap-3">
            {/* Last sync event notification */}
            {lastSyncEvent?.event === 'sync_completed' && (
              <div className="flex items-center gap-2 text-sm text-success animate-fade-in">
                <CheckCircle className="w-4 h-4" />
                <span>
                  +{lastSyncEvent.records_inserted} records
                  {lastSyncEvent.records_duplicate ? ` (${lastSyncEvent.records_duplicate} duplicates skipped)` : ''}
                </span>
              </div>
            )}

            {/* WebSocket connection status */}
            <div className="flex items-center gap-1.5 text-xs">
              {wsConnected ? (
                <>
                  <Wifi className="w-3.5 h-3.5 text-success" />
                  <span className="text-surface-500">Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="w-3.5 h-3.5 text-surface-500" />
                  <span className="text-surface-500">Offline</span>
                </>
              )}
            </div>

            {/* Show sync details button */}
            {syncStatus?.recent_uploads && syncStatus.recent_uploads.length > 0 && (
              <button
                onClick={() => setShowSyncDetails(!showSyncDetails)}
                className="text-xs text-primary hover:text-primary-light transition-colors"
              >
                {showSyncDetails ? 'Hide history' : 'View history'}
              </button>
            )}
          </div>
        </div>

        {/* Expandable sync history */}
        {showSyncDetails && syncStatus?.recent_uploads && (
          <div className="mt-3 pt-3 border-t border-surface-600">
            <h4 className="text-xs font-medium text-surface-400 mb-2 flex items-center gap-1">
              <Clock className="w-3.5 h-3.5" />
              Recent Sync History
            </h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {syncStatus.recent_uploads.map((upload) => (
                <div
                  key={upload.upload_id}
                  className={`flex items-center justify-between text-xs p-2 rounded-magnetic ${
                    upload.status === 'processing'
                      ? 'bg-primary/10 border border-primary/30'
                      : upload.status === 'failed'
                      ? 'bg-error/10 border border-error/30'
                      : 'bg-surface-700'
                  }`}
                >
                  <div className="flex items-center gap-2">
                    {upload.status === 'processing' ? (
                      <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
                    ) : upload.status === 'failed' ? (
                      <AlertCircle className="w-3.5 h-3.5 text-error" />
                    ) : (
                      <CheckCircle className="w-3.5 h-3.5 text-success" />
                    )}
                    <span className="text-surface-300">
                      {new Date(upload.started_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-surface-400">
                    {upload.status === 'completed' && (
                      <>
                        <span className="text-success">+{upload.records_inserted}</span>
                        {upload.records_duplicate > 0 && (
                          <span className="text-surface-500">{upload.records_duplicate} dup</span>
                        )}
                      </>
                    )}
                    {upload.status === 'failed' && upload.error_message && (
                      <span className="text-error truncate max-w-[200px]" title={upload.error_message}>
                        {upload.error_message}
                      </span>
                    )}
                    {upload.status === 'processing' && (
                      <span className="text-primary">{upload.records_processed} processed</span>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Summary Cards - Only show cards with data */}
      {summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
          {/* Steps Card with Progress Ring */}
          {hasData.activity && (
            <div className="magnetic-card col-span-2 md:col-span-1">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">Steps</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {summary.steps ? formatNumber(summary.steps) : '-'}
                  </p>
                  <p className="text-surface-500 text-sm">
                    Goal: {formatNumber(summary.steps_goal)}
                  </p>
                </div>
                <div className="relative w-16 h-16">
                  <svg className="w-16 h-16 transform -rotate-90">
                    <circle
                      cx="32"
                      cy="32"
                      r="28"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="transparent"
                      className="text-surface-600"
                    />
                    <circle
                      cx="32"
                      cy="32"
                      r="28"
                      stroke="currentColor"
                      strokeWidth="4"
                      fill="transparent"
                      strokeDasharray={`${stepsProgress * 1.76} 176`}
                      className="text-success"
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <Footprints className="w-6 h-6 text-success" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Resting Heart Rate */}
          {hasData.heart && summary.resting_heart_rate && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">Resting HR</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {Math.round(summary.resting_heart_rate)}
                  </p>
                  <p className="text-surface-500 text-sm">bpm</p>
                </div>
                <div className="p-3 rounded-magnetic bg-error/20 text-error">
                  <Heart className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}

          {/* Active Calories */}
          {hasData.activity && summary.active_calories && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">Active Cal</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {Math.round(summary.active_calories)}
                  </p>
                  <p className="text-surface-500 text-sm">kcal</p>
                </div>
                <div className="p-3 rounded-magnetic bg-orange-500/20 text-orange-400">
                  <Flame className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}

          {/* Distance */}
          {hasData.activity && summary.distance_km && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">Distance</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {summary.distance_km.toFixed(1)}
                  </p>
                  <p className="text-surface-500 text-sm">mi</p>
                </div>
                <div className="p-3 rounded-magnetic bg-primary/20 text-primary">
                  <MapPin className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}

          {/* Sleep Hours */}
          {hasData.sleep && summary.sleep_hours && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">Sleep</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {summary.sleep_hours.toFixed(1)}
                  </p>
                  <p className="text-surface-500 text-sm">hours</p>
                </div>
                <div className="p-3 rounded-magnetic bg-indigo-500/20 text-indigo-400">
                  <Moon className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}

          {/* HRV */}
          {hasData.heart && (latestHrv || summary.hrv_avg) && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">HRV</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {Math.round(summary.hrv_avg || latestHrv || 0)}
                  </p>
                  <p className="text-surface-500 text-sm">ms</p>
                </div>
                <div className="p-3 rounded-magnetic bg-green-500/20 text-green-400">
                  <Activity className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}

          {/* Blood Oxygen (SpO2) */}
          {hasData.vitals && summary.blood_oxygen_avg && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">Blood Oxygen</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {summary.blood_oxygen_avg.toFixed(0)}
                  </p>
                  <p className="text-surface-500 text-sm">% SpO2</p>
                </div>
                <div className="p-3 rounded-magnetic bg-red-500/20 text-red-400">
                  <Wind className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}

          {/* VO2 Max */}
          {hasData.vitals && summary.vo2_max && (
            <div className="magnetic-card">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-surface-400 text-sm">VO2 Max</p>
                  <p className="text-2xl font-semibold text-white mt-1">
                    {summary.vo2_max.toFixed(1)}
                  </p>
                  <p className="text-surface-500 text-sm">mL/kg/min</p>
                </div>
                <div className="p-3 rounded-magnetic bg-blue-500/20 text-blue-400">
                  <Zap className="w-6 h-6" />
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-2 border-b border-surface-600 pb-2 overflow-x-auto">
        {tabs.map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-t-magnetic font-medium transition-colors whitespace-nowrap ${
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
            {/* Steps Chart */}
            {hasData.activity && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Daily Steps</h3>
                {stepsChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <AreaChart data={stepsChartData}>
                      <defs>
                        <linearGradient id="stepsGradient" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                          <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                        </linearGradient>
                      </defs>
                      <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                      <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                        labelStyle={{ color: '#fff' }}
                        formatter={(value: number) => [formatNumber(value), 'Steps']}
                      />
                      <Area
                        type="monotone"
                        dataKey="steps"
                        stroke="#10b981"
                        fill="url(#stepsGradient)"
                      />
                      <Line
                        type="monotone"
                        dataKey="goal"
                        stroke="#6b7280"
                        strokeDasharray="5 5"
                        dot={false}
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[250px] flex items-center justify-center text-surface-400">
                    No step data available
                  </div>
                )}
              </div>
            )}

            {/* Heart Rate Chart */}
            {hasData.heart && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Heart Rate</h3>
                {hrChartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={250}>
                    <LineChart data={hrChartData}>
                      <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                      <YAxis stroke="#6b7280" fontSize={12} domain={['dataMin - 10', 'dataMax + 10']} />
                      <Tooltip
                        contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                        labelStyle={{ color: '#fff' }}
                        formatter={(value: number) => [Math.round(value), 'bpm']}
                      />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="resting"
                        name="Resting"
                        stroke="#ef4444"
                        dot={false}
                        connectNulls={true}
                      />
                      <Line
                        type="monotone"
                        dataKey="avg"
                        name="Average"
                        stroke="#00bceb"
                        dot={false}
                        connectNulls={true}
                      />
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="h-[250px] flex items-center justify-center text-surface-400">
                    No heart rate data available
                  </div>
                )}
              </div>
            )}

            {/* Activity Rings */}
            {hasData.activity && summary && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Today's Activity</h3>
                <div className="grid grid-cols-3 gap-6">
                  {/* Move Ring */}
                  <div className="flex flex-col items-center">
                    <div className="relative w-16 h-16">
                      <svg className="w-16 h-16 transform -rotate-90">
                        <circle cx="32" cy="32" r="27" stroke="currentColor" strokeWidth="5" fill="transparent" className="text-red-900/30" />
                        <circle cx="32" cy="32" r="27" stroke="currentColor" strokeWidth="5" fill="transparent"
                          strokeDasharray={`${Math.min(((summary.active_calories || 0) / 500) * 100, 100) * 1.696} 169.6`}
                          strokeLinecap="round" className="text-red-500" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Flame className="w-5 h-5 text-red-400" />
                      </div>
                    </div>
                    <p className="text-white font-medium text-sm mt-2">{Math.round(summary.active_calories || 0)} kcal</p>
                    <p className="text-surface-500 text-xs">Move</p>
                  </div>
                  {/* Exercise Ring */}
                  <div className="flex flex-col items-center">
                    <div className="relative w-16 h-16">
                      <svg className="w-16 h-16 transform -rotate-90">
                        <circle cx="32" cy="32" r="27" stroke="currentColor" strokeWidth="5" fill="transparent" className="text-green-900/30" />
                        <circle cx="32" cy="32" r="27" stroke="currentColor" strokeWidth="5" fill="transparent"
                          strokeDasharray={`${Math.min(((summary.exercise_minutes || 0) / 30) * 100, 100) * 1.696} 169.6`}
                          strokeLinecap="round" className="text-green-500" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Timer className="w-5 h-5 text-green-400" />
                      </div>
                    </div>
                    <p className="text-white font-medium text-sm mt-2">{summary.exercise_minutes || 0} min</p>
                    <p className="text-surface-500 text-xs">Exercise</p>
                  </div>
                  {/* Stand Ring */}
                  <div className="flex flex-col items-center">
                    <div className="relative w-16 h-16">
                      <svg className="w-16 h-16 transform -rotate-90">
                        <circle cx="32" cy="32" r="27" stroke="currentColor" strokeWidth="5" fill="transparent" className="text-cyan-900/30" />
                        <circle cx="32" cy="32" r="27" stroke="currentColor" strokeWidth="5" fill="transparent"
                          strokeDasharray={`${Math.min(((summary.stand_hours || 0) / 12) * 100, 100) * 1.696} 169.6`}
                          strokeLinecap="round" className="text-cyan-500" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Activity className="w-5 h-5 text-cyan-400" />
                      </div>
                    </div>
                    <p className="text-white font-medium text-sm mt-2">{summary.stand_hours || 0} hrs</p>
                    <p className="text-surface-500 text-xs">Stand</p>
                  </div>
                </div>
              </div>
            )}

            {/* Trends */}
            {trends && trends.trends.length > 0 && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Trends vs Previous {timeRange} Days</h3>
                <div className="space-y-4">
                  {trends.trends.map(trend => (
                    <div key={trend.metric} className="flex items-center justify-between">
                      <div>
                        <p className="text-white capitalize">
                          {trend.metric.replace(/_/g, ' ')}
                        </p>
                        <p className="text-sm text-surface-400">
                          {Math.round(trend.current_value).toLocaleString()} vs{' '}
                          {Math.round(trend.previous_value).toLocaleString()}
                        </p>
                      </div>
                      <div className={`flex items-center gap-1 ${
                        trend.trend === 'improving' ? 'text-success' :
                        trend.trend === 'declining' ? 'text-error' :
                        'text-surface-400'
                      }`}>
                        {trend.trend === 'improving' ? (
                          <TrendingUp className="w-4 h-4" />
                        ) : trend.trend === 'declining' ? (
                          <TrendingDown className="w-4 h-4" />
                        ) : null}
                        <span>{Math.abs(trend.change_percentage).toFixed(1)}%</span>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* No Data State */}
            {!hasData.activity && !hasData.heart && (
              <div className="magnetic-card col-span-2 text-center py-12">
                <Activity className="w-12 h-12 text-surface-500 mx-auto mb-4" />
                <p className="text-surface-400">No health data available yet</p>
                <p className="text-surface-500 text-sm mt-2">
                  Configure Health Auto Export to sync your Apple Health data
                </p>
                <button
                  onClick={() => setShowConfig(true)}
                  className="magnetic-button-primary mt-4"
                >
                  Configure Sync
                </button>
              </div>
            )}
          </div>
        )}

        {/* Activity Tab */}
        {activeTab === 'activity' && stepsHistory && (
          <div className="space-y-6">
            {/* Activity Rings Summary - Apple's Move/Exercise/Stand */}
            {summary && (
              <div className="magnetic-card bg-gradient-to-br from-surface-700/50 to-transparent">
                <h3 className="text-lg font-medium text-white mb-4">Activity Rings</h3>
                <div className="grid grid-cols-3 gap-4">
                  {/* Move Ring */}
                  <div className="flex flex-col items-center">
                    <div className="relative w-20 h-20">
                      <svg className="w-20 h-20 transform -rotate-90">
                        <circle cx="40" cy="40" r="34" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-red-900/30" />
                        <circle cx="40" cy="40" r="34" stroke="currentColor" strokeWidth="6" fill="transparent"
                          strokeDasharray={`${Math.min(((summary.active_calories || 0) / 500) * 100, 100) * 2.136} 213.6`}
                          strokeLinecap="round" className="text-red-500" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Flame className="w-6 h-6 text-red-400" />
                      </div>
                    </div>
                    <p className="text-white font-semibold mt-2">{Math.round(summary.active_calories || 0)}</p>
                    <p className="text-surface-400 text-xs">/ 500 kcal</p>
                  </div>
                  {/* Exercise Ring */}
                  <div className="flex flex-col items-center">
                    <div className="relative w-20 h-20">
                      <svg className="w-20 h-20 transform -rotate-90">
                        <circle cx="40" cy="40" r="34" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-green-900/30" />
                        <circle cx="40" cy="40" r="34" stroke="currentColor" strokeWidth="6" fill="transparent"
                          strokeDasharray={`${Math.min(((summary.exercise_minutes || 0) / 30) * 100, 100) * 2.136} 213.6`}
                          strokeLinecap="round" className="text-green-500" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Timer className="w-6 h-6 text-green-400" />
                      </div>
                    </div>
                    <p className="text-white font-semibold mt-2">{summary.exercise_minutes || 0}</p>
                    <p className="text-surface-400 text-xs">/ 30 min</p>
                  </div>
                  {/* Stand Ring */}
                  <div className="flex flex-col items-center">
                    <div className="relative w-20 h-20">
                      <svg className="w-20 h-20 transform -rotate-90">
                        <circle cx="40" cy="40" r="34" stroke="currentColor" strokeWidth="6" fill="transparent" className="text-cyan-900/30" />
                        <circle cx="40" cy="40" r="34" stroke="currentColor" strokeWidth="6" fill="transparent"
                          strokeDasharray={`${Math.min(((summary.stand_hours || 0) / 12) * 100, 100) * 2.136} 213.6`}
                          strokeLinecap="round" className="text-cyan-500" />
                      </svg>
                      <div className="absolute inset-0 flex items-center justify-center">
                        <Activity className="w-6 h-6 text-cyan-400" />
                      </div>
                    </div>
                    <p className="text-white font-semibold mt-2">{summary.stand_hours || 0}</p>
                    <p className="text-surface-400 text-xs">/ 12 hrs</p>
                  </div>
                </div>
              </div>
            )}

            {/* Distance Highlight */}
            <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
              <div className="magnetic-card bg-gradient-to-br from-primary/20 to-transparent">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-magnetic bg-primary/30 text-primary">
                    <MapPin className="w-8 h-8" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-sm">Total Distance</p>
                    <p className="text-3xl font-semibold text-white">
                      {activityTotals.totalDistance.toFixed(1)}
                      <span className="text-lg text-surface-400 ml-1">mi</span>
                    </p>
                  </div>
                </div>
              </div>
              <div className="magnetic-card">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-magnetic bg-purple-500/20 text-purple-400">
                    <TrendingUp className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-sm">Daily Avg Distance</p>
                    <p className="text-2xl font-semibold text-white">
                      {activityTotals.avgDailyDistance.toFixed(1)}
                      <span className="text-sm text-surface-400 ml-1">mi</span>
                    </p>
                  </div>
                </div>
              </div>
              <div className="magnetic-card">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-magnetic bg-orange-500/20 text-orange-400">
                    <Activity className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-sm">Flights Climbed</p>
                    <p className="text-2xl font-semibold text-white">
                      {formatNumber(activityTotals.totalFlights)}
                      <span className="text-sm text-surface-400 ml-1">floors</span>
                    </p>
                  </div>
                </div>
              </div>
              {/* Stand Hours */}
              <div className="magnetic-card">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-magnetic bg-cyan-500/20 text-cyan-400">
                    <Activity className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-sm">Stand Hours</p>
                    <p className="text-2xl font-semibold text-white">
                      {summary?.stand_hours ?? '-'}
                      <span className="text-sm text-surface-400 ml-1">/ 12 hrs</span>
                    </p>
                  </div>
                </div>
              </div>
              {/* Exercise Minutes */}
              <div className="magnetic-card">
                <div className="flex items-center gap-4">
                  <div className="p-3 rounded-magnetic bg-green-500/20 text-green-400">
                    <Timer className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-sm">Exercise</p>
                    <p className="text-2xl font-semibold text-white">
                      {summary?.exercise_minutes ?? '-'}
                      <span className="text-sm text-surface-400 ml-1">/ 30 min</span>
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* Steps Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Total Steps</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {formatNumber(stepsHistory.total_steps)}
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Daily Average</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {formatNumber(Math.round(stepsHistory.avg_daily_steps))}
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Goal Met Days</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {stepsHistory.goal_met_days} / {stepsHistory.data.length}
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Best Day</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {stepsHistory.best_day ? formatNumber(stepsHistory.best_day.steps) : '-'}
                </p>
              </div>
            </div>

            {/* Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Daily Steps</h3>
              {stepsChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={350}>
                  <BarChart data={stepsChartData}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `${(v/1000).toFixed(0)}k`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [formatNumber(value), 'Steps']}
                    />
                    <Bar dataKey="steps" radius={[4, 4, 0, 0]}>
                      {stepsChartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.steps >= stepsHistory.steps_goal ? '#10b981' : '#00bceb'}
                        />
                      ))}
                    </Bar>
                    <Line
                      type="monotone"
                      dataKey="goal"
                      stroke="#6b7280"
                      strokeDasharray="5 5"
                      dot={false}
                    />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[350px] flex items-center justify-center text-surface-400">
                  No step data available
                </div>
              )}
            </div>

            {/* Daily Details */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Daily Details</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-surface-400 font-medium py-3 px-4">Date</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Steps</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Distance</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Flights</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Goal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...stepsHistory.data].reverse().map((day, i) => (
                      <tr key={i} className="border-b border-surface-700 hover:bg-surface-700/50">
                        <td className="py-3 px-4 text-white">{formatDate(day.date)}</td>
                        <td className="py-3 px-4 text-right text-white">{formatNumber(day.steps)}</td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {day.distance_meters ? `${day.distance_meters.toFixed(1)} mi` : '-'}
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {day.flights_climbed || '-'}
                        </td>
                        <td className="py-3 px-4 text-right">
                          {day.steps >= stepsHistory.steps_goal ? (
                            <CheckCircle className="w-5 h-5 text-success inline" />
                          ) : (
                            <span className="text-surface-500">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Heart Rate Tab */}
        {activeTab === 'heart' && heartRateHistory && (
          <div className="space-y-6">
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Current Resting</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {heartRateHistory.current_resting_hr
                    ? Math.round(heartRateHistory.current_resting_hr)
                    : '-'}{' '}
                  <span className="text-sm text-surface-400">bpm</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Average Resting</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {heartRateHistory.avg_resting_hr
                    ? Math.round(heartRateHistory.avg_resting_hr)
                    : '-'}{' '}
                  <span className="text-sm text-surface-400">bpm</span>
                </p>
              </div>
            </div>

            {/* Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Heart Rate Over Time</h3>
              {hrChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={hrChartData}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} domain={['dataMin - 10', 'dataMax + 10']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [Math.round(value) + ' bpm', '']}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="max" name="Max" stroke="#ef4444" dot={false} connectNulls={true} />
                    <Line type="monotone" dataKey="avg" name="Average" stroke="#00bceb" dot={false} connectNulls={true} />
                    <Line type="monotone" dataKey="resting" name="Resting" stroke="#10b981" strokeWidth={2} connectNulls={true} />
                    <Line type="monotone" dataKey="min" name="Min" stroke="#6366f1" dot={false} connectNulls={true} />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[350px] flex items-center justify-center text-surface-400">
                  No heart rate data available
                </div>
              )}
            </div>
          </div>
        )}

        {/* Sleep Tab */}
        {activeTab === 'sleep' && sleepHistory && (
          <div className="space-y-6">
            {/* Sleep Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="magnetic-card bg-gradient-to-br from-indigo-500/20 to-transparent">
                <p className="text-surface-400 text-sm">Avg Sleep</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {sleepHistory.avg_sleep_hours.toFixed(1)}{' '}
                  <span className="text-sm text-surface-400">hrs</span>
                </p>
                <p className="text-surface-500 text-sm">
                  Goal: {sleepHistory.sleep_goal_hours} hrs
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Avg Time in Bed</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {sleepHistory.avg_time_in_bed_hours.toFixed(1)}{' '}
                  <span className="text-sm text-surface-400">hrs</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Sleep Efficiency</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {sleepHistory.avg_sleep_efficiency?.toFixed(0) ?? '-'}
                  <span className="text-sm text-surface-400">%</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Goal Met Days</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {sleepHistory.goal_met_days} / {sleepHistory.data.length}
                </p>
              </div>
            </div>

            {/* Sleep Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Sleep Duration</h3>
              {sleepHistory.data.length > 0 ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={sleepHistory.data.map(d => ({
                    date: formatDate(d.date),
                    total: (d.total_minutes / 60).toFixed(1),
                    deep: d.stages.find(s => s.stage === 'deep')?.minutes ?? 0,
                    rem: d.stages.find(s => s.stage === 'rem')?.minutes ?? 0,
                    core: d.stages.find(s => s.stage === 'core')?.minutes ?? 0,
                    goal: sleepHistory.sleep_goal_hours,
                  }))}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `${v}h`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number, name: string) => [
                        name === 'total' ? `${value} hrs` : `${Math.round(value)} min`,
                        name === 'total' ? 'Total Sleep' : name.charAt(0).toUpperCase() + name.slice(1),
                      ]}
                    />
                    <Legend />
                    <Bar dataKey="total" name="Total Sleep" radius={[4, 4, 0, 0]}>
                      {sleepHistory.data.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={(entry.total_minutes / 60) >= sleepHistory.sleep_goal_hours ? '#10b981' : '#6366f1'}
                        />
                      ))}
                    </Bar>
                    <Line type="monotone" dataKey="goal" name="Goal" stroke="#6b7280" strokeDasharray="5 5" dot={false} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-surface-400">
                  No sleep data available
                </div>
              )}
            </div>

            {/* Sleep Stages Breakdown (if available) */}
            {sleepHistory.data.length > 0 && sleepHistory.data.some(d => d.stages.length > 0) && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Sleep Stages (Latest Night)</h3>
                {(() => {
                  const latestSleep = sleepHistory.data[sleepHistory.data.length - 1]
                  if (!latestSleep?.stages.length) return <p className="text-surface-400">No stage data available</p>
                  return (
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                      {latestSleep.stages.map(stage => (
                        <div key={stage.stage} className="p-3 bg-surface-700 rounded-magnetic">
                          <p className="text-surface-400 text-xs capitalize">{stage.stage}</p>
                          <p className="text-lg font-semibold text-white">
                            {Math.round(stage.minutes)} min
                          </p>
                          <p className="text-surface-500 text-xs">{stage.percentage.toFixed(0)}%</p>
                        </div>
                      ))}
                    </div>
                  )
                })()}
              </div>
            )}

            {/* Sleep History Table */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Sleep History</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-surface-400 font-medium py-3 px-4">Date</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Duration</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">In Bed</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Efficiency</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Goal</th>
                    </tr>
                  </thead>
                  <tbody>
                    {[...sleepHistory.data].reverse().map((session, i) => (
                      <tr key={i} className="border-b border-surface-700 hover:bg-surface-700/50">
                        <td className="py-3 px-4 text-white">{formatDate(session.date)}</td>
                        <td className="py-3 px-4 text-right text-white">
                          {(session.total_minutes / 60).toFixed(1)} hrs
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {(session.time_in_bed_minutes / 60).toFixed(1)} hrs
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {session.sleep_efficiency?.toFixed(0) ?? '-'}%
                        </td>
                        <td className="py-3 px-4 text-right">
                          {(session.total_minutes / 60) >= sleepHistory.sleep_goal_hours ? (
                            <CheckCircle className="w-5 h-5 text-success inline" />
                          ) : (
                            <span className="text-surface-500">-</span>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Workouts Tab */}
        {activeTab === 'workouts' && workoutHistory && (
          <div className="space-y-6">
            {/* Workout Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="magnetic-card bg-gradient-to-br from-orange-500/20 to-transparent">
                <p className="text-surface-400 text-sm">Total Workouts</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {workoutHistory.total_workouts}
                </p>
                <p className="text-surface-500 text-sm">
                  {workoutHistory.avg_workouts_per_week.toFixed(1)} / week
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Total Duration</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {(workoutHistory.total_duration_minutes / 60).toFixed(1)}{' '}
                  <span className="text-sm text-surface-400">hrs</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Calories Burned</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {formatNumber(Math.round(workoutHistory.total_calories_burned))}
                  <span className="text-sm text-surface-400 ml-1">kcal</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Total Distance</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {workoutHistory.total_distance_meters.toFixed(1)}
                  <span className="text-sm text-surface-400 ml-1">mi</span>
                </p>
              </div>
            </div>

            {/* Workouts by Type */}
            {Object.keys(workoutHistory.workouts_by_type).length > 0 && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Workouts by Type</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  {Object.entries(workoutHistory.workouts_by_type)
                    .sort((a, b) => b[1] - a[1])
                    .map(([type, count]) => (
                      <div key={type} className="p-3 bg-surface-700 rounded-magnetic">
                        <p className="text-surface-400 text-xs capitalize">
                          {type.replace(/_/g, ' ')}
                        </p>
                        <p className="text-lg font-semibold text-white">{count}</p>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {/* Workout History Table */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Workout History</h3>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-surface-600">
                      <th className="text-left text-surface-400 font-medium py-3 px-4">Date</th>
                      <th className="text-left text-surface-400 font-medium py-3 px-4">Type</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Duration</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Calories</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Distance</th>
                      <th className="text-right text-surface-400 font-medium py-3 px-4">Avg HR</th>
                    </tr>
                  </thead>
                  <tbody>
                    {workoutHistory.workouts.map(workout => (
                      <tr key={workout.workout_id} className="border-b border-surface-700 hover:bg-surface-700/50">
                        <td className="py-3 px-4 text-white">
                          {new Date(workout.date).toLocaleDateString('en-US', {
                            month: 'short',
                            day: 'numeric',
                            hour: '2-digit',
                            minute: '2-digit',
                          })}
                        </td>
                        <td className="py-3 px-4 text-white capitalize">
                          {workout.workout_type.replace(/_/g, ' ')}
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {workout.duration_minutes.toFixed(0)} min
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {workout.calories_burned ? Math.round(workout.calories_burned) : '-'}
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {workout.distance_meters ? `${workout.distance_meters.toFixed(2)} mi` : '-'}
                        </td>
                        <td className="py-3 px-4 text-right text-surface-300">
                          {workout.avg_heart_rate ? `${Math.round(workout.avg_heart_rate)} bpm` : '-'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}

        {/* Vitals Tab */}
        {activeTab === 'vitals' && (
          <div className="space-y-6">
            {/* Vitals Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {/* SpO2 Card */}
              <div className="magnetic-card bg-gradient-to-br from-red-500/20 to-transparent">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-magnetic bg-red-500/20 text-red-400">
                    <Wind className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-xs">Blood Oxygen</p>
                    <p className="text-xl font-semibold text-white">
                      {vitalsHistory?.current_spo2?.toFixed(0) ?? '-'}%
                    </p>
                  </div>
                </div>
                <div className="mt-3 text-xs text-surface-400">
                  Avg: {vitalsHistory?.avg_spo2?.toFixed(0) ?? '-'}% | Min: {vitalsHistory?.min_spo2?.toFixed(0) ?? '-'}%
                </div>
              </div>

              {/* VO2 Max Card */}
              <div className="magnetic-card bg-gradient-to-br from-blue-500/20 to-transparent">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-magnetic bg-blue-500/20 text-blue-400">
                    <Zap className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-xs">VO2 Max</p>
                    <p className="text-xl font-semibold text-white">
                      {vitalsHistory?.current_vo2_max?.toFixed(1) ?? '-'}
                    </p>
                  </div>
                </div>
                <div className="mt-3 text-xs">
                  <span className={`${
                    vitalsHistory?.vo2_max_trend === 'improving' ? 'text-success' :
                    vitalsHistory?.vo2_max_trend === 'declining' ? 'text-error' :
                    'text-surface-400'
                  }`}>
                    {vitalsHistory?.vo2_max_trend ? `Trend: ${vitalsHistory.vo2_max_trend}` : 'No trend data'}
                  </span>
                </div>
              </div>

              {/* Respiratory Rate Card */}
              <div className="magnetic-card">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-magnetic bg-purple-500/20 text-purple-400">
                    <Activity className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-xs">Respiratory Rate</p>
                    <p className="text-xl font-semibold text-white">
                      {vitalsHistory?.avg_respiratory_rate?.toFixed(0) ?? '-'}
                      <span className="text-sm text-surface-400 ml-1">br/min</span>
                    </p>
                  </div>
                </div>
              </div>

              {/* Mobility Summary Card */}
              <div className="magnetic-card">
                <div className="flex items-center gap-3">
                  <div className="p-2 rounded-magnetic bg-green-500/20 text-green-400">
                    <Footprints className="w-5 h-5" />
                  </div>
                  <div>
                    <p className="text-surface-400 text-xs">Walking Speed</p>
                    <p className="text-xl font-semibold text-white">
                      {mobilityHistory?.avg_walking_speed_kmh?.toFixed(1) ?? '-'}
                      <span className="text-sm text-surface-400 ml-1">mph</span>
                    </p>
                  </div>
                </div>
              </div>
            </div>

            {/* SpO2 Trend Chart */}
            {vitalsHistory && vitalsHistory.data.length > 0 && vitalsHistory.data.some(d => d.blood_oxygen_avg) && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Blood Oxygen (SpO2) Trend</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={vitalsHistory.data.map(d => {
                    // Parse date-only strings as local dates to prevent timezone shift
                    let date: Date
                    if (/^\d{4}-\d{2}-\d{2}$/.test(d.date)) {
                      const [year, month, day] = d.date.split('-').map(Number)
                      date = new Date(year, month - 1, day)
                    } else {
                      date = new Date(d.date)
                    }
                    return {
                      date: date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
                      avg: d.blood_oxygen_avg,
                      min: d.blood_oxygen_min,
                    }
                  })}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} domain={[90, 100]} tickFormatter={v => `${v}%`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [`${value?.toFixed(1)}%`, '']}
                    />
                    <Legend />
                    <Line type="monotone" dataKey="avg" name="Average" stroke="#ef4444" strokeWidth={2} dot={true} connectNulls={true} />
                    <Line type="monotone" dataKey="min" name="Minimum" stroke="#6b7280" strokeDasharray="3 3" dot={false} connectNulls={true} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* Mobility Metrics */}
            {mobilityHistory && mobilityHistory.data.length > 0 && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-4">Mobility Metrics</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                  <div className="p-3 bg-surface-700 rounded-magnetic">
                    <p className="text-surface-400 text-xs">Avg Step Length</p>
                    <p className="text-lg font-semibold text-white">
                      {mobilityHistory.avg_step_length_cm?.toFixed(0) ?? '-'} in
                    </p>
                  </div>
                  <div className="p-3 bg-surface-700 rounded-magnetic">
                    <p className="text-surface-400 text-xs">Walking Asymmetry</p>
                    <p className={`text-lg font-semibold ${
                      mobilityHistory.asymmetry_status === 'normal' ? 'text-success' :
                      mobilityHistory.asymmetry_status === 'elevated' ? 'text-warning' :
                      mobilityHistory.asymmetry_status === 'concerning' ? 'text-error' :
                      'text-white'
                    }`}>
                      {mobilityHistory.avg_asymmetry_pct?.toFixed(1) ?? '-'}%
                    </p>
                    <p className="text-surface-500 text-xs mt-1">
                      {mobilityHistory.asymmetry_status === 'normal' ? 'Normal (<10%)' :
                       mobilityHistory.asymmetry_status === 'elevated' ? 'Elevated (10-20%)' :
                       mobilityHistory.asymmetry_status === 'concerning' ? 'Concerning (>20%)' : ''}
                    </p>
                  </div>
                </div>

                {/* Mobility Chart */}
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={mobilityHistory.data.map(d => {
                    // Parse date-only strings as local dates to prevent timezone shift
                    let date: Date
                    if (/^\d{4}-\d{2}-\d{2}$/.test(d.date)) {
                      const [year, month, day] = d.date.split('-').map(Number)
                      date = new Date(year, month - 1, day)
                    } else {
                      date = new Date(d.date)
                    }
                    return {
                      date: date.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' }),
                      speed: d.walking_speed_kmh,
                      stepLength: d.step_length_cm,
                    }
                  })}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis yAxisId="speed" orientation="left" stroke="#10b981" fontSize={12} tickFormatter={v => `${v} mph`} />
                    <YAxis yAxisId="length" orientation="right" stroke="#6366f1" fontSize={12} tickFormatter={v => `${v} in`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                    />
                    <Legend />
                    <Line yAxisId="speed" type="monotone" dataKey="speed" name="Walking Speed" stroke="#10b981" strokeWidth={2} dot={true} connectNulls={true} />
                    <Line yAxisId="length" type="monotone" dataKey="stepLength" name="Step Length" stroke="#6366f1" strokeWidth={2} dot={true} connectNulls={true} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            {/* VO2 Max Info Card */}
            {vitalsHistory?.current_vo2_max && (
              <div className="magnetic-card bg-gradient-to-br from-blue-500/10 to-transparent">
                <h3 className="text-lg font-medium text-white mb-2">VO2 Max - Cardiorespiratory Fitness</h3>
                <p className="text-surface-300 text-sm mb-4">
                  Your current VO2 Max is <span className="text-white font-semibold">{vitalsHistory.current_vo2_max.toFixed(1)} mL/kg/min</span>.
                  This measures your body's ability to use oxygen during exercise.
                </p>
                <div className="flex items-center gap-2 text-sm">
                  <span className="text-surface-400">Fitness Level:</span>
                  <span className={`font-medium ${
                    vitalsHistory.current_vo2_max >= 50 ? 'text-success' :
                    vitalsHistory.current_vo2_max >= 40 ? 'text-primary' :
                    vitalsHistory.current_vo2_max >= 30 ? 'text-warning' :
                    'text-error'
                  }`}>
                    {vitalsHistory.current_vo2_max >= 50 ? 'Excellent' :
                     vitalsHistory.current_vo2_max >= 40 ? 'Good' :
                     vitalsHistory.current_vo2_max >= 30 ? 'Fair' : 'Below Average'}
                  </span>
                </div>
              </div>
            )}

            {/* No Data State */}
            {(!vitalsHistory || vitalsHistory.data.length === 0) && (!mobilityHistory || mobilityHistory.data.length === 0) && (
              <div className="magnetic-card text-center py-12">
                <Wind className="w-12 h-12 text-surface-500 mx-auto mb-4" />
                <p className="text-surface-400">No vitals data available</p>
                <p className="text-surface-500 text-sm mt-2">SpO2, VO2 Max, and mobility data will appear here once collected</p>
              </div>
            )}
          </div>
        )}

        {/* Body Tab */}
        {activeTab === 'body' && bodyHistory && (
          <div className="space-y-6">
            {/* Stats */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Current Weight</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {bodyHistory.current_weight_kg
                    ? bodyHistory.current_weight_kg.toFixed(1)
                    : '-'}{' '}
                  <span className="text-sm text-surface-400">lbs</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Change</p>
                <p className={`text-2xl font-semibold mt-1 ${
                  bodyHistory.weight_change_kg
                    ? bodyHistory.weight_change_kg > 0
                      ? 'text-error'
                      : 'text-success'
                    : 'text-white'
                }`}>
                  {bodyHistory.weight_change_kg
                    ? `${bodyHistory.weight_change_kg > 0 ? '+' : ''}${bodyHistory.weight_change_kg.toFixed(1)}`
                    : '-'}{' '}
                  <span className="text-sm text-surface-400">lbs</span>
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">BMI</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {bodyHistory.current_bmi ? bodyHistory.current_bmi.toFixed(1) : '-'}
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Body Fat</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {bodyHistory.current_body_fat
                    ? bodyHistory.current_body_fat.toFixed(1)
                    : '-'}
                  <span className="text-sm text-surface-400">%</span>
                </p>
              </div>
            </div>

            {/* Weight Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Weight Over Time</h3>
              {bodyChartData.length > 0 ? (
                <ResponsiveContainer width="100%" height={350}>
                  <LineChart data={bodyChartData}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} domain={['dataMin - 2', 'dataMax + 2']} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value, name) => [
                        typeof value === 'number' ? value.toFixed(1) + (name === 'Weight' ? ' lbs' : '%') : '-',
                        name as string,
                      ]}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="weight"
                      name="Weight"
                      stroke="#00bceb"
                      strokeWidth={2}
                      dot={{ fill: '#00bceb' }}
                      connectNulls={true}
                    />
                  </LineChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[350px] flex items-center justify-center text-surface-400">
                  No weight data available
                </div>
              )}
            </div>

            {/* Trend */}
            {bodyHistory.weight_trend && (
              <div className="magnetic-card">
                <h3 className="text-lg font-medium text-white mb-2">Trend</h3>
                <div className="flex items-center gap-2">
                  {bodyHistory.weight_trend === 'losing' ? (
                    <>
                      <TrendingDown className="w-5 h-5 text-success" />
                      <span className="text-success">Weight decreasing</span>
                    </>
                  ) : bodyHistory.weight_trend === 'gaining' ? (
                    <>
                      <TrendingUp className="w-5 h-5 text-error" />
                      <span className="text-error">Weight increasing</span>
                    </>
                  ) : (
                    <>
                      <Activity className="w-5 h-5 text-surface-400" />
                      <span className="text-surface-400">Weight stable</span>
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Nutrition Tab */}
        {activeTab === 'nutrition' && nutritionHistory && (
          <div className="space-y-6">
            {/* Today's Summary Cards */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              {/* Calories with progress ring */}
              <div className="magnetic-card col-span-2 md:col-span-1">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-surface-400 text-sm">Calories</p>
                    <p className="text-2xl font-semibold text-white mt-1">
                      {todayNutrition?.calories ? Math.round(todayNutrition.calories).toLocaleString() : '-'}
                    </p>
                    <p className="text-surface-500 text-sm">
                      Goal: {nutritionHistory.calorie_goal?.toLocaleString() || '2,000'}
                    </p>
                  </div>
                  <div className="relative w-14 h-14">
                    <svg className="w-14 h-14 transform -rotate-90">
                      <circle
                        cx="28"
                        cy="28"
                        r="24"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="transparent"
                        className="text-surface-600"
                      />
                      <circle
                        cx="28"
                        cy="28"
                        r="24"
                        stroke="currentColor"
                        strokeWidth="4"
                        fill="transparent"
                        strokeDasharray={`${Math.min(((todayNutrition?.calories || 0) / (nutritionHistory.calorie_goal || 2000)) * 100, 100) * 1.51} 151`}
                        className="text-orange-500"
                      />
                    </svg>
                    <div className="absolute inset-0 flex items-center justify-center">
                      <Flame className="w-5 h-5 text-orange-500" />
                    </div>
                  </div>
                </div>
              </div>

              {/* Protein */}
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Protein</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {todayNutrition?.protein_grams ? Math.round(todayNutrition.protein_grams) : '-'}
                  <span className="text-sm text-surface-400 ml-1">g</span>
                </p>
                <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-red-500 rounded-full"
                    style={{ width: `${Math.min(((todayNutrition?.protein_grams || 0) / 150) * 100, 100)}%` }}
                  />
                </div>
              </div>

              {/* Carbs */}
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Carbs</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {todayNutrition?.carbs_grams ? Math.round(todayNutrition.carbs_grams) : '-'}
                  <span className="text-sm text-surface-400 ml-1">g</span>
                </p>
                <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-yellow-500 rounded-full"
                    style={{ width: `${Math.min(((todayNutrition?.carbs_grams || 0) / 250) * 100, 100)}%` }}
                  />
                </div>
              </div>

              {/* Fat */}
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Fat</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {todayNutrition?.fat_grams ? Math.round(todayNutrition.fat_grams) : '-'}
                  <span className="text-sm text-surface-400 ml-1">g</span>
                </p>
                <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 rounded-full"
                    style={{ width: `${Math.min(((todayNutrition?.fat_grams || 0) / 75) * 100, 100)}%` }}
                  />
                </div>
              </div>

              {/* Water */}
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Water</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {todayNutrition?.water_ml ? todayNutrition.water_ml.toFixed(0) : '-'}
                  <span className="text-sm text-surface-400 ml-1">fl oz</span>
                </p>
                <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-cyan-500 rounded-full"
                    style={{ width: `${Math.min(((todayNutrition?.water_ml || 0) / 100) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Average Stats */}
            <div className="grid grid-cols-2 gap-4">
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Avg Daily Calories</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {nutritionHistory.avg_daily_calories
                    ? Math.round(nutritionHistory.avg_daily_calories).toLocaleString()
                    : '-'}
                </p>
              </div>
              <div className="magnetic-card">
                <p className="text-surface-400 text-sm">Avg Daily Protein</p>
                <p className="text-2xl font-semibold text-white mt-1">
                  {nutritionHistory.avg_daily_protein
                    ? Math.round(nutritionHistory.avg_daily_protein)
                    : '-'}
                  <span className="text-sm text-surface-400 ml-1">g</span>
                </p>
              </div>
            </div>

            {/* Calorie Trend Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Calorie Intake</h3>
              {nutritionChartData.length > 0 && nutritionChartData.some(d => d.calories > 0) ? (
                <ResponsiveContainer width="100%" height={300}>
                  <AreaChart data={nutritionChartData}>
                    <defs>
                      <linearGradient id="caloriesGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#f97316" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#f97316" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [value.toLocaleString(), 'Calories']}
                    />
                    <Area
                      type="monotone"
                      dataKey="calories"
                      stroke="#f97316"
                      fill="url(#caloriesGradient)"
                    />
                    {nutritionHistory.calorie_goal && (
                      <Line
                        type="monotone"
                        dataKey={() => nutritionHistory.calorie_goal}
                        stroke="#6b7280"
                        strokeDasharray="5 5"
                        dot={false}
                        name="Goal"
                      />
                    )}
                  </AreaChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-surface-400">
                  No calorie data available
                </div>
              )}
            </div>

            {/* Macros Stacked Bar Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Daily Macros</h3>
              {nutritionChartData.length > 0 && nutritionChartData.some(d => d.protein > 0 || d.carbs > 0 || d.fat > 0) ? (
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={nutritionChartData}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `${v}g`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number, name: string) => [`${Math.round(value)}g`, name]}
                    />
                    <Legend />
                    <Bar dataKey="protein" name="Protein" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} />
                    <Bar dataKey="carbs" name="Carbs" stackId="a" fill="#eab308" />
                    <Bar dataKey="fat" name="Fat" stackId="a" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[300px] flex items-center justify-center text-surface-400">
                  No macro data available
                </div>
              )}
            </div>

            {/* Water Intake Chart */}
            <div className="magnetic-card">
              <h3 className="text-lg font-medium text-white mb-4">Water Intake</h3>
              {nutritionChartData.length > 0 && nutritionChartData.some(d => d.water > 0) ? (
                <ResponsiveContainer width="100%" height={250}>
                  <BarChart data={nutritionChartData}>
                    <XAxis dataKey="date" stroke="#6b7280" fontSize={12} />
                    <YAxis stroke="#6b7280" fontSize={12} tickFormatter={v => `${v} oz`} />
                    <Tooltip
                      contentStyle={{ backgroundColor: '#252542', border: '1px solid #374151' }}
                      labelStyle={{ color: '#fff' }}
                      formatter={(value: number) => [`${value.toFixed(0)} fl oz`, 'Water']}
                    />
                    <Bar dataKey="water" name="Water" fill="#06b6d4" radius={[4, 4, 0, 0]}>
                      {nutritionChartData.map((entry, index) => (
                        <Cell
                          key={`cell-${index}`}
                          fill={entry.water >= 100 ? '#10b981' : '#06b6d4'}
                        />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[250px] flex items-center justify-center text-surface-400">
                  No water data available
                </div>
              )}
            </div>

            {/* Micronutrients Section */}
            {detailedNutrition && (
              <div className="magnetic-card">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-medium text-white">Vitamins & Minerals</h3>
                  <button
                    onClick={() => setShowMicronutrients(!showMicronutrients)}
                    className="text-sm text-primary hover:text-primary-light transition-colors"
                  >
                    {showMicronutrients ? 'Hide details' : 'Show details'}
                  </button>
                </div>

                {showMicronutrients ? (
                  <div className="space-y-6">
                    {/* Vitamins */}
                    <div>
                      <h4 className="text-surface-400 text-sm font-medium mb-3">Vitamins (Avg Daily)</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {[
                          { key: 'vitamin_a_mcg', label: 'Vitamin A', unit: 'mcg', dv: 900 },
                          { key: 'vitamin_c_mg', label: 'Vitamin C', unit: 'mg', dv: 90 },
                          { key: 'vitamin_d_mcg', label: 'Vitamin D', unit: 'mcg', dv: 20 },
                          { key: 'vitamin_e_mg', label: 'Vitamin E', unit: 'mg', dv: 15 },
                          { key: 'vitamin_k_mcg', label: 'Vitamin K', unit: 'mcg', dv: 120 },
                          { key: 'vitamin_b6_mg', label: 'Vitamin B6', unit: 'mg', dv: 1.7 },
                          { key: 'vitamin_b12_mcg', label: 'Vitamin B12', unit: 'mcg', dv: 2.4 },
                          { key: 'thiamin_mg', label: 'Thiamin (B1)', unit: 'mg', dv: 1.2 },
                          { key: 'riboflavin_mg', label: 'Riboflavin (B2)', unit: 'mg', dv: 1.3 },
                          { key: 'niacin_mg', label: 'Niacin (B3)', unit: 'mg', dv: 16 },
                          { key: 'folate_mcg', label: 'Folate', unit: 'mcg', dv: 400 },
                          { key: 'pantothenic_acid_mg', label: 'Pantothenic Acid', unit: 'mg', dv: 5 },
                        ].map(({ key, label, unit, dv }) => {
                          const value = detailedNutrition.avg_daily_micronutrients[key as keyof MicronutrientData]
                          const percent = value ? Math.min((value / dv) * 100, 100) : 0
                          return (
                            <div key={key} className="p-3 bg-surface-700 rounded-magnetic">
                              <p className="text-surface-300 text-xs mb-1">{label}</p>
                              <p className="text-white font-medium">
                                {value ? value.toFixed(1) : '-'} <span className="text-surface-400 text-xs">{unit}</span>
                              </p>
                              <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${percent >= 100 ? 'bg-success' : percent >= 50 ? 'bg-primary' : 'bg-warning'}`}
                                  style={{ width: `${percent}%` }}
                                />
                              </div>
                              <p className="text-surface-500 text-xs mt-1">{percent.toFixed(0)}% DV</p>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Minerals */}
                    <div>
                      <h4 className="text-surface-400 text-sm font-medium mb-3">Minerals (Avg Daily)</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {[
                          { key: 'calcium_mg', label: 'Calcium', unit: 'mg', dv: 1300 },
                          { key: 'iron_mg', label: 'Iron', unit: 'mg', dv: 18 },
                          { key: 'magnesium_mg', label: 'Magnesium', unit: 'mg', dv: 420 },
                          { key: 'phosphorus_mg', label: 'Phosphorus', unit: 'mg', dv: 1250 },
                          { key: 'potassium_mg', label: 'Potassium', unit: 'mg', dv: 4700 },
                          { key: 'sodium_mg', label: 'Sodium', unit: 'mg', dv: 2300 },
                          { key: 'zinc_mg', label: 'Zinc', unit: 'mg', dv: 11 },
                          { key: 'copper_mg', label: 'Copper', unit: 'mg', dv: 0.9 },
                          { key: 'manganese_mg', label: 'Manganese', unit: 'mg', dv: 2.3 },
                          { key: 'selenium_mcg', label: 'Selenium', unit: 'mcg', dv: 55 },
                        ].map(({ key, label, unit, dv }) => {
                          const value = detailedNutrition.avg_daily_micronutrients[key as keyof MicronutrientData]
                          const percent = value ? Math.min((value / dv) * 100, 100) : 0
                          // Sodium shows as over limit warning
                          const isSodium = key === 'sodium_mg'
                          const overLimit = isSodium && value && value > dv
                          return (
                            <div key={key} className="p-3 bg-surface-700 rounded-magnetic">
                              <p className="text-surface-300 text-xs mb-1">{label}</p>
                              <p className="text-white font-medium">
                                {value ? value.toFixed(1) : '-'} <span className="text-surface-400 text-xs">{unit}</span>
                              </p>
                              <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${overLimit ? 'bg-error' : percent >= 100 ? 'bg-success' : percent >= 50 ? 'bg-primary' : 'bg-warning'}`}
                                  style={{ width: `${Math.min(percent, 100)}%` }}
                                />
                              </div>
                              <p className={`text-xs mt-1 ${overLimit ? 'text-error' : 'text-surface-500'}`}>
                                {percent.toFixed(0)}% DV {overLimit && '(over limit)'}
                              </p>
                            </div>
                          )
                        })}
                      </div>
                    </div>

                    {/* Other */}
                    <div>
                      <h4 className="text-surface-400 text-sm font-medium mb-3">Other (Avg Daily)</h4>
                      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
                        {[
                          { key: 'cholesterol_mg', label: 'Cholesterol', unit: 'mg', dv: 300 },
                          { key: 'saturated_fat_grams', label: 'Saturated Fat', unit: 'g', dv: 20 },
                          { key: 'caffeine_mg', label: 'Caffeine', unit: 'mg', dv: 400 },
                        ].map(({ key, label, unit, dv }) => {
                          const value = detailedNutrition.avg_daily_micronutrients[key as keyof MicronutrientData]
                          const percent = value ? (value / dv) * 100 : 0
                          const overLimit = value && value > dv
                          return (
                            <div key={key} className="p-3 bg-surface-700 rounded-magnetic">
                              <p className="text-surface-300 text-xs mb-1">{label}</p>
                              <p className="text-white font-medium">
                                {value ? value.toFixed(1) : '-'} <span className="text-surface-400 text-xs">{unit}</span>
                              </p>
                              <div className="mt-2 h-1.5 bg-surface-600 rounded-full overflow-hidden">
                                <div
                                  className={`h-full rounded-full ${overLimit ? 'bg-error' : percent >= 80 ? 'bg-warning' : 'bg-success'}`}
                                  style={{ width: `${Math.min(percent, 100)}%` }}
                                />
                              </div>
                              <p className={`text-xs mt-1 ${overLimit ? 'text-error' : 'text-surface-500'}`}>
                                {percent.toFixed(0)}% limit {overLimit && '(over)'}
                              </p>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="grid grid-cols-4 gap-4 text-center">
                    <div>
                      <p className="text-2xl font-semibold text-white">
                        {detailedNutrition.avg_daily_micronutrients.vitamin_c_mg?.toFixed(0) || '-'}
                      </p>
                      <p className="text-surface-400 text-xs">Vitamin C mg</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-white">
                        {detailedNutrition.avg_daily_micronutrients.calcium_mg?.toFixed(0) || '-'}
                      </p>
                      <p className="text-surface-400 text-xs">Calcium mg</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-white">
                        {detailedNutrition.avg_daily_micronutrients.iron_mg?.toFixed(1) || '-'}
                      </p>
                      <p className="text-surface-400 text-xs">Iron mg</p>
                    </div>
                    <div>
                      <p className="text-2xl font-semibold text-white">
                        {detailedNutrition.avg_daily_micronutrients.potassium_mg?.toFixed(0) || '-'}
                      </p>
                      <p className="text-surface-400 text-xs">Potassium mg</p>
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Insights Tab - AI-Powered Assessments */}
        {activeTab === 'insights' && (
          <div className="space-y-6">
            {/* Period Selector */}
            <div className="flex items-center justify-between">
              <div className="flex bg-surface-600 rounded-magnetic p-1">
                {[
                  { value: 'daily' as AssessmentPeriod, label: 'Daily' },
                  { value: 'weekly' as AssessmentPeriod, label: 'Weekly' },
                  { value: 'monthly' as AssessmentPeriod, label: 'Monthly' },
                ].map(({ value, label }) => (
                  <button
                    key={value}
                    onClick={() => setAssessmentPeriod(value)}
                    className={`px-4 py-2 rounded-magnetic text-sm font-medium transition-colors ${
                      assessmentPeriod === value
                        ? 'bg-primary text-white'
                        : 'text-surface-300 hover:text-white'
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
              <button
                onClick={() => fetchAssessment(true)}
                disabled={loadingAssessment}
                className="magnetic-button-secondary text-sm py-2 px-4 flex items-center gap-2"
              >
                {loadingAssessment ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                Refresh
              </button>
            </div>

            {/* Loading State */}
            {loadingAssessment && !assessment && (
              <div className="magnetic-card flex flex-col items-center justify-center py-12">
                <Loader2 className="w-8 h-8 text-primary animate-spin mb-4" />
                <p className="text-surface-300">Analyzing your health data...</p>
                <p className="text-surface-500 text-sm mt-1">This may take a moment</p>
              </div>
            )}

            {/* Error State */}
            {assessmentError && !assessment && (
              <div className={`magnetic-card p-6 ${
                assessmentError.includes('Need more data')
                  ? 'bg-primary/10 border border-primary/30'
                  : 'bg-error/10 border border-error/30'
              }`}>
                <div className={`flex items-start gap-3 ${
                  assessmentError.includes('Need more data') ? 'text-primary' : 'text-error'
                }`}>
                  {assessmentError.includes('Need more data') ? (
                    <Database className="w-6 h-6 flex-shrink-0 mt-0.5" />
                  ) : (
                    <AlertCircle className="w-6 h-6 flex-shrink-0 mt-0.5" />
                  )}
                  <div>
                    <p className="font-medium">
                      {assessmentError.includes('Need more data')
                        ? 'More data needed for insights'
                        : 'Failed to load assessment'}
                    </p>
                    <p className={`text-sm mt-1 ${
                      assessmentError.includes('Need more data') ? 'text-primary/80' : 'text-error/80'
                    }`}>
                      {assessmentError}
                    </p>
                    {assessmentError.includes('Need more data') && (
                      <div className="mt-4 p-3 bg-surface-800/50 rounded-magnetic">
                        <p className="text-surface-300 text-sm">
                          <strong>Tip:</strong> Make sure Health Auto Export is syncing regularly.
                          For weekly assessments, you need at least 3 days of data.
                          For monthly assessments, at least 7 days.
                        </p>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            )}

            {/* Assessment Content */}
            {assessment && !loadingAssessment && (
              <>
                {/* Period Info */}
                <div className="flex items-center gap-4 text-sm text-surface-400">
                  <span>
                    Period: {new Date(assessment.period_start).toLocaleDateString()} - {new Date(assessment.period_end).toLocaleDateString()}
                  </span>
                  <span className="text-surface-600">|</span>
                  <span>Generated: {new Date(assessment.generated_at).toLocaleString()}</span>
                </div>

                {/* Summary Card */}
                <div className="magnetic-card bg-gradient-to-br from-primary/10 to-transparent border border-primary/20">
                  <div className="flex items-start gap-4">
                    <div className="p-3 rounded-magnetic bg-primary/20 text-primary">
                      <Sparkles className="w-6 h-6" />
                    </div>
                    <div>
                      <h3 className="text-lg font-medium text-white mb-2">Summary</h3>
                      <p className="text-surface-200 leading-relaxed">{assessment.summary}</p>
                    </div>
                  </div>
                </div>

                {/* Red Flags */}
                {assessment.red_flags.length > 0 && (
                  <div className="magnetic-card">
                    <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5 text-error" />
                      Areas Needing Attention
                      <span className="ml-2 px-2 py-0.5 rounded-full bg-error/20 text-error text-xs">
                        {assessment.red_flags.length}
                      </span>
                    </h3>
                    <div className="space-y-4">
                      {assessment.red_flags.map((flag, index) => (
                        <div
                          key={index}
                          className={`p-4 rounded-magnetic border-l-4 ${
                            flag.severity === 'high'
                              ? 'bg-error/10 border-error'
                              : flag.severity === 'medium'
                              ? 'bg-warning/10 border-warning'
                              : 'bg-surface-700 border-surface-500'
                          }`}
                        >
                          <div className="flex items-start justify-between gap-4">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-2">
                                <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${
                                  flag.severity === 'high'
                                    ? 'bg-error/30 text-error'
                                    : flag.severity === 'medium'
                                    ? 'bg-warning/30 text-warning'
                                    : 'bg-surface-600 text-surface-300'
                                }`}>
                                  {flag.severity.toUpperCase()}
                                </span>
                                <span className="text-surface-400 text-sm">{flag.metric}</span>
                              </div>
                              <p className="text-white font-medium mb-2">{flag.issue}</p>
                              <p className="text-surface-300 text-sm mb-3">{flag.explanation}</p>
                              <div className="flex items-start gap-2 p-3 bg-surface-800/50 rounded-magnetic">
                                <Lightbulb className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                                <p className="text-primary text-sm">{flag.suggestion}</p>
                              </div>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Green Flags */}
                {assessment.green_flags.length > 0 && (
                  <div className="magnetic-card">
                    <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                      <ThumbsUp className="w-5 h-5 text-success" />
                      Achievements
                      <span className="ml-2 px-2 py-0.5 rounded-full bg-success/20 text-success text-xs">
                        {assessment.green_flags.length}
                      </span>
                    </h3>
                    <div className="grid gap-4 md:grid-cols-2">
                      {assessment.green_flags.map((flag, index) => (
                        <div
                          key={index}
                          className="p-4 rounded-magnetic bg-success/10 border border-success/30"
                        >
                          <div className="flex items-center gap-2 mb-2">
                            <CheckCircle className="w-5 h-5 text-success" />
                            <span className="text-surface-400 text-sm">{flag.metric}</span>
                          </div>
                          <p className="text-white font-medium mb-2">{flag.achievement}</p>
                          <p className="text-surface-300 text-sm">{flag.explanation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Points of Interest */}
                {assessment.points_of_interest.length > 0 && (
                  <div className="magnetic-card">
                    <h3 className="text-lg font-medium text-white mb-4 flex items-center gap-2">
                      <Star className="w-5 h-5 text-primary" />
                      Points of Interest
                    </h3>
                    <div className="space-y-4">
                      {assessment.points_of_interest.map((point, index) => (
                        <div
                          key={index}
                          className="p-4 rounded-magnetic bg-surface-700/50"
                        >
                          <p className="text-white font-medium mb-2">{point.observation}</p>
                          <p className="text-surface-300 text-sm mb-2">{point.context}</p>
                          {point.recommendation && (
                            <div className="flex items-start gap-2 mt-3 pt-3 border-t border-surface-600">
                              <Lightbulb className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                              <p className="text-primary text-sm">{point.recommendation}</p>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* No Data States */}
                {assessment.red_flags.length === 0 && assessment.green_flags.length === 0 && assessment.points_of_interest.length === 0 && (
                  <div className="magnetic-card text-center py-8">
                    <CheckCircle className="w-12 h-12 text-success mx-auto mb-4" />
                    <p className="text-white font-medium">All Good!</p>
                    <p className="text-surface-400 mt-1">No significant observations for this period.</p>
                  </div>
                )}

                {/* Meta Info */}
                <div className="flex items-center justify-between text-xs text-surface-500">
                  <span>Powered by {assessment.model_used}</span>
                  <span>Cost: ${assessment.cost_cents.toFixed(4)}</span>
                </div>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
