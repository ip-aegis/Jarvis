import { useState, useEffect, useCallback } from 'react'
import { Bot, Settings } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import ChatPanel from '../components/chat/ChatPanel'
import type { JournalEntry, JournalStats, JournalCalendarData, JournalEntryCreate, JournalChatSummary } from '../types'

const MOODS = [
  { value: 'happy', label: 'Happy', emoji: '😊', color: 'bg-green-500' },
  { value: 'excited', label: 'Excited', emoji: '🎉', color: 'bg-yellow-500' },
  { value: 'grateful', label: 'Grateful', emoji: '🙏', color: 'bg-purple-500' },
  { value: 'calm', label: 'Calm', emoji: '😌', color: 'bg-blue-400' },
  { value: 'neutral', label: 'Neutral', emoji: '😐', color: 'bg-gray-400' },
  { value: 'anxious', label: 'Anxious', emoji: '😰', color: 'bg-orange-500' },
  { value: 'sad', label: 'Sad', emoji: '😢', color: 'bg-blue-600' },
  { value: 'stressed', label: 'Stressed', emoji: '😤', color: 'bg-red-500' },
]

const ENERGY_LEVELS = [1, 2, 3, 4, 5]

export default function Journal() {
  // Tab state
  const [activeTab, setActiveTab] = useState<'chat' | 'entries' | 'summaries'>('chat')

  // Data state
  const [entries, setEntries] = useState<JournalEntry[]>([])
  const [stats, setStats] = useState<JournalStats | null>(null)
  const [calendarData, setCalendarData] = useState<JournalCalendarData | null>(null)
  const [pendingSummaries, setPendingSummaries] = useState<JournalChatSummary[]>([])
  const [selectedEntry, setSelectedEntry] = useState<JournalEntry | null>(null)
  const [isEditorOpen, setIsEditorOpen] = useState(false)
  const [loading, setLoading] = useState(true)
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<string | null>(null)
  const [currentModel, setCurrentModel] = useState<string | null>(null)

  // Session persistence for chat
  const [sessionId, setSessionId] = useState(() => {
    const stored = localStorage.getItem('journal-chat-session-id')
    if (stored) return stored
    const newId = `journal-${Date.now()}`
    localStorage.setItem('journal-chat-session-id', newId)
    return newId
  })

  // Editor state
  const [editorContent, setEditorContent] = useState('')
  const [editorTitle, setEditorTitle] = useState('')
  const [editorMood, setEditorMood] = useState<string>('')
  const [editorEnergy, setEditorEnergy] = useState<number>(3)
  const [editorTags, setEditorTags] = useState<string>('')
  const [editorDate, setEditorDate] = useState<string>(new Date().toISOString().split('T')[0])
  const [saving, setSaving] = useState(false)

  // =============================================================================
  // Data Loading
  // =============================================================================

  const loadData = useCallback(async () => {
    setLoading(true)
    try {
      const [entriesRes, statsRes, summariesRes] = await Promise.all([
        api.listJournalEntries({ limit: 20 }),
        api.getJournalStats(),
        api.listPendingSummaries(),
      ])
      setEntries(entriesRes.entries)
      setStats(statsRes)
      setPendingSummaries(summariesRes.summaries || [])
    } catch (err) {
      console.error('Failed to load journal data:', err)
    }
    setLoading(false)
  }, [])

  const loadCalendar = useCallback(async () => {
    try {
      const data = await api.getJournalCalendar(
        currentDate.getFullYear(),
        currentDate.getMonth() + 1
      )
      setCalendarData(data)
    } catch (err) {
      console.error('Failed to load calendar:', err)
    }
  }, [currentDate])

  useEffect(() => {
    loadData()
  }, [loadData])

  useEffect(() => {
    loadCalendar()
  }, [loadCalendar])

  // =============================================================================
  // Handlers
  // =============================================================================

  const handleModelLoaded = useCallback((model: string) => {
    setCurrentModel(model)
  }, [])

  const handleNewChat = useCallback(() => {
    const newId = `journal-${Date.now()}`
    localStorage.setItem('journal-chat-session-id', newId)
    setSessionId(newId)
  }, [])

  const openNewEntry = (date?: string) => {
    setSelectedEntry(null)
    setEditorContent('')
    setEditorTitle('')
    setEditorMood('')
    setEditorEnergy(3)
    setEditorTags('')
    setEditorDate(date || new Date().toISOString().split('T')[0])
    setIsEditorOpen(true)
  }

  const openEditEntry = (entry: JournalEntry) => {
    setSelectedEntry(entry)
    setEditorContent(entry.content)
    setEditorTitle(entry.title || '')
    setEditorMood(entry.mood || '')
    setEditorEnergy(entry.energy_level || 3)
    setEditorTags(entry.tags?.join(', ') || '')
    setEditorDate(entry.date.split('T')[0])
    setIsEditorOpen(true)
  }

  const saveEntry = async () => {
    if (!editorContent.trim()) return

    setSaving(true)
    try {
      const entryData: JournalEntryCreate = {
        content: editorContent,
        title: editorTitle || undefined,
        mood: editorMood || undefined,
        energy_level: editorEnergy,
        tags: editorTags.split(',').map(t => t.trim()).filter(Boolean),
        date: editorDate,
      }

      if (selectedEntry) {
        await api.updateJournalEntry(selectedEntry.entry_id, entryData)
      } else {
        await api.createJournalEntry(entryData)
      }

      setIsEditorOpen(false)
      loadData()
      loadCalendar()
    } catch (err) {
      console.error('Failed to save entry:', err)
    }
    setSaving(false)
  }

  const deleteEntry = async (entryId: string) => {
    if (!confirm('Are you sure you want to delete this entry?')) return
    try {
      await api.deleteJournalEntry(entryId)
      loadData()
      loadCalendar()
    } catch (err) {
      console.error('Failed to delete entry:', err)
    }
  }

  const approveSummary = async (summaryId: string) => {
    try {
      await api.approveSummary(summaryId)
      loadData()
    } catch (err) {
      console.error('Failed to approve summary:', err)
    }
  }

  const rejectSummary = async (summaryId: string) => {
    try {
      await api.rejectSummary(summaryId)
      setPendingSummaries(prev => prev.filter(s => s.summary_id !== summaryId))
    } catch (err) {
      console.error('Failed to reject summary:', err)
    }
  }

  // =============================================================================
  // Helpers
  // =============================================================================

  const getMoodEmoji = (mood?: string) => {
    const m = MOODS.find(m => m.value === mood)
    return m?.emoji || ''
  }

  const getMoodColor = (mood?: string) => {
    const m = MOODS.find(m => m.value === mood)
    return m?.color || 'bg-gray-400'
  }

  // Calendar helpers
  const getDaysInMonth = (date: Date) => {
    const year = date.getFullYear()
    const month = date.getMonth()
    const firstDay = new Date(year, month, 1)
    const lastDay = new Date(year, month + 1, 0)
    const daysInMonth = lastDay.getDate()
    const startingDay = firstDay.getDay()

    const days: (number | null)[] = []
    for (let i = 0; i < startingDay; i++) {
      days.push(null)
    }
    for (let i = 1; i <= daysInMonth; i++) {
      days.push(i)
    }
    return days
  }

  const formatDateKey = (day: number) => {
    const year = currentDate.getFullYear()
    const month = String(currentDate.getMonth() + 1).padStart(2, '0')
    return `${year}-${month}-${String(day).padStart(2, '0')}`
  }

  const prevMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() - 1, 1))
  }

  const nextMonth = () => {
    setCurrentDate(new Date(currentDate.getFullYear(), currentDate.getMonth() + 1, 1))
  }

  const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December']

  const days = getDaysInMonth(currentDate)

  const tabButtonClass = (tab: 'chat' | 'entries' | 'summaries') => `
    px-4 py-2 rounded-lg font-medium transition-colors
    ${activeTab === tab
      ? 'bg-primary-500 text-white'
      : 'bg-surface-700 text-gray-400 hover:text-white hover:bg-surface-600'}
  `

  // =============================================================================
  // Render
  // =============================================================================

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500"></div>
      </div>
    )
  }

  return (
    <div className="h-full flex flex-col">
      {/* Header with Tabs */}
      <div className="border-b border-surface-600 bg-surface-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-6">
            <h1 className="text-2xl font-bold text-white">Journal</h1>
            {/* Tab buttons */}
            <div className="flex gap-2">
              <button onClick={() => setActiveTab('chat')} className={tabButtonClass('chat')}>
                Chat
              </button>
              <button onClick={() => setActiveTab('entries')} className={tabButtonClass('entries')}>
                Entries
              </button>
              <button onClick={() => setActiveTab('summaries')} className={tabButtonClass('summaries')}>
                Summaries
                {pendingSummaries.length > 0 && (
                  <span className="ml-2 px-1.5 py-0.5 text-xs bg-yellow-500 text-black rounded-full">
                    {pendingSummaries.length}
                  </span>
                )}
              </button>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {/* Model indicator for chat tab */}
            {activeTab === 'chat' && (
              <Link
                to="/settings"
                className="flex items-center gap-2 px-3 py-1.5 bg-surface-700 rounded-lg text-sm text-gray-400 hover:text-white transition-colors"
                title="Configure in Settings"
              >
                <Bot className="w-4 h-4" />
                <span className="truncate max-w-[150px]">{currentModel || 'Loading...'}</span>
                <Settings className="w-4 h-4 opacity-50" />
              </Link>
            )}
            {/* New Entry button - show on entries tab */}
            {activeTab === 'entries' && (
              <button
                onClick={() => openNewEntry()}
                className="magnetic-button-primary flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Entry
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === 'chat' ? (
        // =======================================================================
        // CHAT TAB - Full width ChatPanel
        // =======================================================================
        <div className="flex-1 flex flex-col overflow-hidden">
          <ChatPanel
            sessionId={sessionId}
            context="journal"
            placeholder="Reflect on your day, share your thoughts..."
            onModelLoaded={handleModelLoaded}
            onNewChat={handleNewChat}
          />
        </div>
      ) : activeTab === 'entries' ? (
        // =======================================================================
        // ENTRIES TAB - Calendar + Recent Entries
        // =======================================================================
        <div className="flex-1 overflow-auto p-6">
          {/* Stats */}
          {stats && (
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
              <div className="magnetic-card p-4">
                <div className="text-sm text-gray-400">Total Entries</div>
                <div className="text-2xl font-bold text-white">{stats.total_entries}</div>
              </div>
              <div className="magnetic-card p-4">
                <div className="text-sm text-gray-400">Current Streak</div>
                <div className="text-2xl font-bold text-primary-500">{stats.current_streak} days</div>
              </div>
              <div className="magnetic-card p-4">
                <div className="text-sm text-gray-400">Pending Summaries</div>
                <div className="text-2xl font-bold text-yellow-500">{stats.pending_summaries}</div>
              </div>
              <div className="magnetic-card p-4">
                <div className="text-sm text-gray-400">Top Mood</div>
                <div className="text-2xl font-bold text-white">
                  {Object.entries(stats.mood_distribution || {}).sort((a, b) => b[1] - a[1])[0]?.[0] || 'N/A'}
                </div>
              </div>
            </div>
          )}

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Calendar */}
            <div className="magnetic-card p-4">
              <div className="flex items-center justify-between mb-4">
                <button onClick={prevMonth} className="p-2 hover:bg-surface-600 rounded">
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
                  </svg>
                </button>
                <h2 className="text-lg font-semibold text-white">
                  {monthNames[currentDate.getMonth()]} {currentDate.getFullYear()}
                </h2>
                <button onClick={nextMonth} className="p-2 hover:bg-surface-600 rounded">
                  <svg className="w-5 h-5 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                  </svg>
                </button>
              </div>

              {/* Calendar Grid */}
              <div className="grid grid-cols-7 gap-1">
                {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(day => (
                  <div key={day} className="text-center text-xs text-gray-500 py-2">{day}</div>
                ))}
                {days.map((day, idx) => {
                  if (day === null) {
                    return <div key={`empty-${idx}`} className="h-12"></div>
                  }
                  const dateKey = formatDateKey(day)
                  const dayEntries = calendarData?.entries[dateKey] || []
                  const isToday = dateKey === new Date().toISOString().split('T')[0]
                  const isSelected = dateKey === selectedDate

                  return (
                    <button
                      key={dateKey}
                      onClick={() => {
                        setSelectedDate(dateKey)
                        if (dayEntries.length === 0) {
                          openNewEntry(dateKey)
                        }
                      }}
                      className={`h-12 rounded flex flex-col items-center justify-center relative
                        ${isToday ? 'ring-2 ring-primary-500' : ''}
                        ${isSelected ? 'bg-primary-500/20' : 'hover:bg-surface-600'}
                      `}
                    >
                      <span className={`text-sm ${isToday ? 'text-primary-500 font-bold' : 'text-gray-300'}`}>
                        {day}
                      </span>
                      {dayEntries.length > 0 && (
                        <div className="flex gap-0.5 mt-0.5">
                          {dayEntries.slice(0, 3).map((entry, i) => (
                            <div
                              key={i}
                              className={`w-1.5 h-1.5 rounded-full ${getMoodColor(entry.mood)}`}
                            />
                          ))}
                        </div>
                      )}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Recent Entries */}
            <div className="magnetic-card p-4">
              <h2 className="text-lg font-semibold text-white mb-4">Recent Entries</h2>
              <div className="space-y-3 max-h-[400px] overflow-y-auto">
                {entries.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No entries yet. Start journaling!</p>
                ) : (
                  entries.map(entry => (
                    <div
                      key={entry.entry_id}
                      onClick={() => openEditEntry(entry)}
                      className="p-3 bg-surface-600 rounded-lg cursor-pointer hover:bg-surface-500 transition-colors"
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center gap-2">
                            <span className="text-lg">{getMoodEmoji(entry.mood)}</span>
                            <span className="text-sm text-gray-400">{entry.date.split('T')[0]}</span>
                            {entry.source === 'chat_summary' && (
                              <span className="text-xs bg-purple-500/20 text-purple-400 px-2 py-0.5 rounded">
                                From Chat
                              </span>
                            )}
                          </div>
                          {entry.title && (
                            <h3 className="text-white font-medium mt-1">{entry.title}</h3>
                          )}
                          <p className="text-gray-400 text-sm mt-1 line-clamp-2">{entry.content}</p>
                          {entry.tags && entry.tags.length > 0 && (
                            <div className="flex gap-1 mt-2">
                              {entry.tags.map(tag => (
                                <span
                                  key={tag}
                                  className="text-xs bg-surface-500 text-gray-300 px-2 py-0.5 rounded"
                                >
                                  {tag}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            deleteEntry(entry.entry_id)
                          }}
                          className="p-1 text-gray-500 hover:text-red-500"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>
      ) : (
        // =======================================================================
        // SUMMARIES TAB - Pending summaries + Insights
        // =======================================================================
        <div className="flex-1 overflow-auto p-6">
          <div className="max-w-4xl mx-auto space-y-6">
            {/* Pending Summaries */}
            <div className="magnetic-card p-4">
              <h2 className="text-lg font-semibold text-white mb-4">Pending Summaries</h2>
              {pendingSummaries.length === 0 ? (
                <p className="text-gray-500 text-center py-8">
                  No pending summaries. Chat with the journal assistant to generate reflections!
                </p>
              ) : (
                <div className="space-y-4">
                  {pendingSummaries.map(summary => (
                    <div
                      key={summary.summary_id}
                      className="p-4 bg-surface-600 rounded-lg"
                    >
                      <div className="flex items-start justify-between mb-3">
                        <div>
                          <div className="text-sm text-gray-400">
                            {summary.created_at ? new Date(summary.created_at).toLocaleDateString() : 'Recent'}
                          </div>
                          {summary.key_topics && summary.key_topics.length > 0 && (
                            <div className="flex gap-1 mt-1">
                              {summary.key_topics.map(topic => (
                                <span
                                  key={topic}
                                  className="text-xs bg-primary-500/20 text-primary-400 px-2 py-0.5 rounded"
                                >
                                  {topic}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        {summary.sentiment && (
                          <span className="text-sm text-gray-400">{summary.sentiment}</span>
                        )}
                      </div>
                      <p className="text-gray-300 text-sm mb-4">{summary.summary_text}</p>
                      <div className="flex justify-end gap-2">
                        <button
                          onClick={() => rejectSummary(summary.summary_id)}
                          className="px-3 py-1.5 text-sm bg-surface-500 text-gray-300 rounded hover:bg-surface-400 transition-colors"
                        >
                          Dismiss
                        </button>
                        <button
                          onClick={() => approveSummary(summary.summary_id)}
                          className="px-3 py-1.5 text-sm bg-primary-500 text-white rounded hover:bg-primary-400 transition-colors"
                        >
                          Save as Entry
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Weekly Insights */}
            {stats && (
              <div className="magnetic-card p-4">
                <h2 className="text-lg font-semibold text-white mb-4">Insights</h2>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Mood Distribution */}
                  <div className="p-4 bg-surface-600 rounded-lg">
                    <div className="text-sm text-gray-400 mb-3">Mood Distribution</div>
                    {stats.mood_distribution && Object.keys(stats.mood_distribution).length > 0 ? (
                      <div className="space-y-2">
                        {Object.entries(stats.mood_distribution)
                          .sort((a, b) => b[1] - a[1])
                          .slice(0, 5)
                          .map(([mood, count]) => {
                            const total = Object.values(stats.mood_distribution).reduce((a, b) => a + b, 0)
                            const percentage = Math.round((count / total) * 100)
                            return (
                              <div key={mood} className="flex items-center gap-2">
                                <span className="text-lg">{getMoodEmoji(mood)}</span>
                                <span className="text-sm text-gray-300 capitalize w-20">{mood}</span>
                                <div className="flex-1 h-2 bg-surface-500 rounded-full overflow-hidden">
                                  <div
                                    className={`h-full ${getMoodColor(mood)}`}
                                    style={{ width: `${percentage}%` }}
                                  />
                                </div>
                                <span className="text-xs text-gray-500 w-12 text-right">{percentage}%</span>
                              </div>
                            )
                          })}
                      </div>
                    ) : (
                      <p className="text-gray-500 text-sm">No mood data yet</p>
                    )}
                  </div>

                  {/* Entry Sources */}
                  <div className="p-4 bg-surface-600 rounded-lg">
                    <div className="text-sm text-gray-400 mb-3">Entry Sources</div>
                    {stats.source_distribution && Object.keys(stats.source_distribution).length > 0 ? (
                      <div className="space-y-2">
                        {Object.entries(stats.source_distribution).map(([source, count]) => (
                          <div key={source} className="flex items-center justify-between">
                            <span className="text-sm text-gray-300 capitalize">
                              {source === 'chat_summary' ? 'From Chat' : 'Manual'}
                            </span>
                            <span className="text-lg font-bold text-white">{count}</span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-gray-500 text-sm">No source data yet</p>
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* Entry Editor Modal */}
      {isEditorOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-700 rounded-lg w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="p-4 border-b border-surface-600 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">
                {selectedEntry ? 'Edit Entry' : 'New Entry'}
              </h3>
              <button
                onClick={() => setIsEditorOpen(false)}
                className="text-gray-400 hover:text-white"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <div className="p-4 space-y-4">
              {/* Date */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Date</label>
                <input
                  type="date"
                  value={editorDate}
                  onChange={(e) => setEditorDate(e.target.value)}
                  className="magnetic-input w-full"
                />
              </div>

              {/* Title */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Title (optional)</label>
                <input
                  type="text"
                  value={editorTitle}
                  onChange={(e) => setEditorTitle(e.target.value)}
                  placeholder="Give your entry a title..."
                  className="magnetic-input w-full"
                />
              </div>

              {/* Content */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">What's on your mind?</label>
                <textarea
                  value={editorContent}
                  onChange={(e) => setEditorContent(e.target.value)}
                  placeholder="Write your thoughts..."
                  rows={8}
                  className="magnetic-input w-full resize-none"
                />
              </div>

              {/* Mood */}
              <div>
                <label className="block text-sm text-gray-400 mb-2">How are you feeling?</label>
                <div className="flex flex-wrap gap-2">
                  {MOODS.map(mood => (
                    <button
                      key={mood.value}
                      onClick={() => setEditorMood(mood.value)}
                      className={`px-3 py-2 rounded-lg flex items-center gap-2 transition-all
                        ${editorMood === mood.value
                          ? `${mood.color} text-white`
                          : 'bg-surface-600 text-gray-300 hover:bg-surface-500'
                        }`}
                    >
                      <span>{mood.emoji}</span>
                      <span className="text-sm">{mood.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Energy Level */}
              <div>
                <label className="block text-sm text-gray-400 mb-2">Energy Level</label>
                <div className="flex gap-2">
                  {ENERGY_LEVELS.map(level => (
                    <button
                      key={level}
                      onClick={() => setEditorEnergy(level)}
                      className={`w-10 h-10 rounded-lg flex items-center justify-center transition-all
                        ${editorEnergy === level
                          ? 'bg-primary-500 text-white'
                          : 'bg-surface-600 text-gray-300 hover:bg-surface-500'
                        }`}
                    >
                      {level}
                    </button>
                  ))}
                </div>
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>Low</span>
                  <span>High</span>
                </div>
              </div>

              {/* Tags */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Tags (comma-separated)</label>
                <input
                  type="text"
                  value={editorTags}
                  onChange={(e) => setEditorTags(e.target.value)}
                  placeholder="work, family, health..."
                  className="magnetic-input w-full"
                />
              </div>
            </div>

            <div className="p-4 border-t border-surface-600 flex justify-end gap-3">
              <button
                onClick={() => setIsEditorOpen(false)}
                className="magnetic-button-secondary"
              >
                Cancel
              </button>
              <button
                onClick={saveEntry}
                disabled={saving || !editorContent.trim()}
                className="magnetic-button-primary disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Save Entry'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
