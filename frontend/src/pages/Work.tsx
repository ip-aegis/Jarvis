import { useState, useEffect, useCallback, useMemo, useRef } from 'react'
import { Bot, Settings } from 'lucide-react'
import { Link } from 'react-router-dom'
import { api } from '../services/api'
import ChatPanel from '../components/chat/ChatPanel'
import type {
  WorkAccount,
  WorkNote,
  AccountStats,
  AccountEvents,
  AccountSummary,
  AccountIntelligence,
  WorkNoteCreate,
  AccountCreate,
  WorkContact,
  WorkUserProfile,
  LearnedFact,
} from '../types'

const ACTIVITY_TYPES = [
  { value: 'meeting', label: 'Meeting', icon: '📅' },
  { value: 'call', label: 'Call', icon: '📞' },
  { value: 'email', label: 'Email', icon: '📧' },
  { value: 'task', label: 'Task', icon: '✅' },
  { value: 'note', label: 'Note', icon: '📝' },
  { value: 'follow_up', label: 'Follow-up', icon: '🔄' },
]

const STATUS_OPTIONS = [
  { value: 'active', label: 'Active', color: 'bg-green-500' },
  { value: 'prospect', label: 'Prospect', color: 'bg-blue-500' },
  { value: 'inactive', label: 'Inactive', color: 'bg-yellow-500' },
  { value: 'closed', label: 'Closed', color: 'bg-gray-500' },
]

export default function Work() {
  // Tab state - Chat is default
  const [activeTab, setActiveTab] = useState<'chat' | 'accounts' | 'profile'>('chat')

  // Shared state
  const [accounts, setAccounts] = useState<WorkAccount[]>([])
  const [loading, setLoading] = useState(true)
  const [currentModel, setCurrentModel] = useState<string | null>(null)

  // Session ID for work chat (can be reset for new conversations)
  const [sessionId, setSessionId] = useState(() => {
    const stored = localStorage.getItem('work-chat-session-id')
    if (stored) return stored
    const newId = `work-${Date.now()}`
    localStorage.setItem('work-chat-session-id', newId)
    return newId
  })

  // Handler for starting a new chat - extracts profile info first
  const handleNewChat = useCallback(async () => {
    // First, try to extract any useful info from the current chat
    const currentMessages = sessionStorage.getItem(`chat-${sessionId}`)
    if (currentMessages) {
      try {
        const messages = JSON.parse(currentMessages)
        if (messages.length > 0) {
          // Auto-learn from the conversation before clearing
          const result = await api.learnFromChats(messages, sessionId)
          if (result.added > 0) {
            console.log(`Extracted ${result.added} facts before clearing chat`)
            // Refresh profile data if we're on that tab
            if (activeTab === 'profile') {
              const profileData = await api.getWorkProfile()
              setProfile(profileData)
            }
          }
        }
      } catch (err) {
        console.error('Failed to extract info before clearing chat:', err)
      }
    }

    // Now create new session
    const newId = `work-${Date.now()}`
    localStorage.setItem('work-chat-session-id', newId)
    setSessionId(newId)
  }, [sessionId, activeTab])

  // Chat tab context state
  const [contextAccount, setContextAccount] = useState<WorkAccount | null>(null)
  const [contextNotes, setContextNotes] = useState<WorkNote[]>([])
  const [contextStats, setContextStats] = useState<AccountStats | null>(null)
  const [loadingContext, setLoadingContext] = useState(false)
  const lastMessageRef = useRef<string>('')

  // Accounts tab state
  const [selectedAccount, setSelectedAccount] = useState<WorkAccount | null>(null)
  const [accountStats, setAccountStats] = useState<AccountStats | null>(null)
  const [accountNotes, setAccountNotes] = useState<WorkNote[]>([])
  const [accountEvents, setAccountEvents] = useState<AccountEvents | null>(null)
  const [accountSummary, setAccountSummary] = useState<AccountSummary | null>(null)
  const [loadingSummary, setLoadingSummary] = useState(false)
  const [enriching, setEnriching] = useState(false)
  const [eventsTab, setEventsTab] = useState<'overdue' | 'upcoming' | 'recent'>('upcoming')
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('')

  // Modal state
  const [isAccountModalOpen, setIsAccountModalOpen] = useState(false)
  const [isNoteModalOpen, setIsNoteModalOpen] = useState(false)
  const [isContactModalOpen, setIsContactModalOpen] = useState(false)

  // Account form state
  const [accountName, setAccountName] = useState('')
  const [accountDescription, setAccountDescription] = useState('')
  const [accountStatus, setAccountStatus] = useState('active')
  const [editingAccount, setEditingAccount] = useState<WorkAccount | null>(null)
  const [similarAccounts, setSimilarAccounts] = useState<Array<{ account: WorkAccount; score: number }>>([])
  const [checkingSimilar, setCheckingSimilar] = useState(false)

  // Note form state
  const [noteContent, setNoteContent] = useState('')
  const [noteActivityType, setNoteActivityType] = useState<string>('note')
  const [saving, setSaving] = useState(false)

  // Contact form state
  const [contactName, setContactName] = useState('')
  const [contactRole, setContactRole] = useState('')
  const [contactEmail, setContactEmail] = useState('')
  const [contactPhone, setContactPhone] = useState('')

  // Accounts tab chat state
  const [isAccountsChatOpen, setIsAccountsChatOpen] = useState(false)
  const accountsChatSessionId = useMemo(() => `work-accounts-${Date.now()}`, [])

  // Debounce timer for similar account check
  const similarCheckTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Profile tab state
  const [profile, setProfile] = useState<WorkUserProfile | null>(null)
  const [loadingProfile, setLoadingProfile] = useState(false)
  const [learningFromChats, setLearningFromChats] = useState(false)
  const [editingSection, setEditingSection] = useState<string | null>(null)
  const [editValue, setEditValue] = useState<string>('')
  const [editListValue, setEditListValue] = useState<string[]>([])
  const [newListItem, setNewListItem] = useState('')

  // =============================================================================
  // Data Loading
  // =============================================================================

  const loadAccounts = useCallback(async () => {
    setLoading(true)
    try {
      const response = await api.listWorkAccounts({
        status: statusFilter || undefined,
        limit: 100,
      })
      setAccounts(response.accounts)
    } catch (err) {
      console.error('Failed to load accounts:', err)
    }
    setLoading(false)
  }, [statusFilter])

  const loadAccountDetails = useCallback(async (account: WorkAccount) => {
    // Reset summary when switching accounts
    setAccountSummary(null)
    try {
      const [statsRes, notesRes, eventsRes] = await Promise.all([
        api.getAccountStats(account.account_id),
        api.listWorkNotes(account.account_id, { limit: 50 }),
        api.getAccountEvents(account.account_id),
      ])
      setAccountStats(statsRes)
      setAccountNotes(notesRes.notes)
      setAccountEvents(eventsRes)
      // Default to overdue tab if there are overdue items, otherwise upcoming
      if (eventsRes.overdue.length > 0) {
        setEventsTab('overdue')
      } else if (eventsRes.upcoming.length > 0) {
        setEventsTab('upcoming')
      } else {
        setEventsTab('recent')
      }
    } catch (err) {
      console.error('Failed to load account details:', err)
    }
  }, [])

  const loadContextForAccount = useCallback(async (account: WorkAccount) => {
    setLoadingContext(true)
    try {
      const [statsRes, notesRes] = await Promise.all([
        api.getAccountStats(account.account_id),
        api.listWorkNotes(account.account_id, { limit: 10 }),
      ])
      setContextStats(statsRes)
      setContextNotes(notesRes.notes)
      setContextAccount(account)
    } catch (err) {
      console.error('Failed to load context:', err)
    }
    setLoadingContext(false)
  }, [])

  useEffect(() => {
    loadAccounts()
  }, [loadAccounts])

  useEffect(() => {
    if (selectedAccount) {
      loadAccountDetails(selectedAccount)
    }
  }, [selectedAccount, loadAccountDetails])

  const handleModelLoaded = useCallback((model: string) => {
    setCurrentModel(model)
  }, [])

  const generateSummary = useCallback(async () => {
    if (!selectedAccount) return
    setLoadingSummary(true)
    try {
      const summary = await api.getAccountSummary(selectedAccount.account_id)
      setAccountSummary(summary)
    } catch (err) {
      console.error('Failed to generate summary:', err)
    }
    setLoadingSummary(false)
  }, [selectedAccount])

  const enrichAccount = useCallback(async (force = false) => {
    if (!selectedAccount) return
    setEnriching(true)
    try {
      const updated = await api.enrichAccount(selectedAccount.account_id, force)
      setSelectedAccount(updated)
      // Also update the account in the accounts list
      setAccounts(prev => prev.map(acc =>
        acc.account_id === updated.account_id ? updated : acc
      ))
    } catch (err) {
      console.error('Failed to enrich account:', err)
      alert('Failed to gather company intelligence. Please try again.')
    }
    setEnriching(false)
  }, [selectedAccount])

  // Check for similar accounts when name changes (debounced)
  const checkSimilarAccounts = useCallback((name: string) => {
    // Clear any pending check
    if (similarCheckTimeoutRef.current) {
      clearTimeout(similarCheckTimeoutRef.current)
    }

    // Don't check if name is too short or if editing an existing account
    if (name.trim().length < 2 || editingAccount) {
      setSimilarAccounts([])
      setCheckingSimilar(false)
      return
    }

    setCheckingSimilar(true)

    // Debounce the API call
    similarCheckTimeoutRef.current = setTimeout(async () => {
      try {
        const response = await api.searchWorkAccounts(name.trim(), 5)
        // Filter to only show accounts with reasonably high match scores
        const matches = response.results
          .filter((r: { match_score: number }) => r.match_score > 0.5)
          .map((r: { match_score: number }) => ({ account: r as unknown as WorkAccount, score: r.match_score }))
        setSimilarAccounts(matches)
      } catch (err) {
        console.error('Failed to check similar accounts:', err)
        setSimilarAccounts([])
      }
      setCheckingSimilar(false)
    }, 300)
  }, [editingAccount])

  const completeActionItem = useCallback(async (noteId: string, task: string) => {
    if (!selectedAccount) return
    try {
      await api.updateActionItem(noteId, task, { status: 'completed' })
      // Refresh events
      const events = await api.getAccountEvents(selectedAccount.account_id)
      setAccountEvents(events)
    } catch (err) {
      console.error('Failed to complete action item:', err)
    }
  }, [selectedAccount])

  const deleteActionItem = useCallback(async (noteId: string, task: string) => {
    if (!selectedAccount) return
    if (!confirm('Delete this action item?')) return
    try {
      await api.deleteActionItem(noteId, task)
      // Refresh events
      const events = await api.getAccountEvents(selectedAccount.account_id)
      setAccountEvents(events)
    } catch (err) {
      console.error('Failed to delete action item:', err)
    }
  }, [selectedAccount])

  // =============================================================================
  // Profile Functions
  // =============================================================================

  const loadProfile = useCallback(async () => {
    setLoadingProfile(true)
    try {
      const profileData = await api.getWorkProfile()
      setProfile(profileData)
    } catch (err) {
      console.error('Failed to load profile:', err)
    }
    setLoadingProfile(false)
  }, [])

  const saveProfileField = useCallback(async (field: string, value: unknown) => {
    try {
      const updates = { [field]: value }
      const updated = await api.updateWorkProfile(updates)
      setProfile(updated)
      setEditingSection(null)
    } catch (err) {
      console.error('Failed to save profile:', err)
    }
  }, [])

  const learnFromChats = useCallback(async () => {
    setLearningFromChats(true)
    try {
      // Collect ALL work-related chat messages from sessionStorage
      const allMessages: Array<{ role: string; content: string }> = []

      // Look for all chat sessions in sessionStorage
      for (let i = 0; i < sessionStorage.length; i++) {
        const key = sessionStorage.key(i)
        if (key && key.startsWith('chat-work')) {
          try {
            const messages = JSON.parse(sessionStorage.getItem(key) || '[]')
            allMessages.push(...messages)
          } catch {
            // Skip invalid entries
          }
        }
      }

      // Also check the current session explicitly
      const currentSession = sessionStorage.getItem(`chat-${sessionId}`)
      if (currentSession) {
        try {
          const messages = JSON.parse(currentSession)
          // Avoid duplicates
          for (const msg of messages) {
            if (!allMessages.some(m => m.content === msg.content && m.role === msg.role)) {
              allMessages.push(msg)
            }
          }
        } catch {
          // Skip
        }
      }

      console.log('Learning from messages:', allMessages.length, 'messages found')

      if (allMessages.length === 0) {
        alert('No chat messages found. Have a conversation in the Chat tab first, then click "Learn from Chats".')
        setLearningFromChats(false)
        return
      }

      const result = await api.learnFromChats(allMessages, sessionId)
      console.log('Learn result:', result)

      if (result.added > 0) {
        await loadProfile()
        alert(`Learned ${result.added} new facts about you!`)
      } else if (result.extracted > 0) {
        alert(`Found ${result.extracted} facts, but they were already known.`)
      } else {
        alert('No new facts about you were found in the conversation. Try sharing more about yourself - your role, responsibilities, expertise, etc.')
      }
    } catch (err) {
      console.error('Failed to learn from chats:', err)
      alert('Failed to learn from chats: ' + (err instanceof Error ? err.message : 'Unknown error'))
    }
    setLearningFromChats(false)
  }, [sessionId, loadProfile])

  const verifyFact = useCallback(async (factId: string) => {
    try {
      const updated = await api.verifyFact(factId, true)
      setProfile(updated)
    } catch (err) {
      console.error('Failed to verify fact:', err)
    }
  }, [])

  const deleteFact = useCallback(async (factId: string) => {
    if (!confirm('Delete this learned fact?')) return
    try {
      await api.deleteFact(factId)
      await loadProfile()
    } catch (err) {
      console.error('Failed to delete fact:', err)
    }
  }, [loadProfile])

  // Load profile when switching to profile tab
  useEffect(() => {
    if (activeTab === 'profile' && !profile) {
      loadProfile()
    }
  }, [activeTab, profile, loadProfile])

  // =============================================================================
  // Account Detection for Chat Context
  // =============================================================================

  const detectAccountMention = useCallback((message: string): WorkAccount | null => {
    const lowerMessage = message.toLowerCase()
    for (const account of accounts) {
      if (lowerMessage.includes(account.name.toLowerCase())) {
        return account
      }
      // Check aliases
      for (const alias of account.aliases || []) {
        if (lowerMessage.includes(alias.toLowerCase())) {
          return account
        }
      }
    }
    return null
  }, [accounts])

  // Listen for chat input to detect account mentions
  useEffect(() => {
    if (activeTab !== 'chat') return

    const handleInput = () => {
      const chatInput = document.querySelector('textarea[placeholder*="Ask about"]') as HTMLTextAreaElement
      if (chatInput && chatInput.value !== lastMessageRef.current) {
        lastMessageRef.current = chatInput.value
        const detected = detectAccountMention(chatInput.value)
        if (detected && detected.account_id !== contextAccount?.account_id) {
          loadContextForAccount(detected)
        }
      }
    }

    const interval = setInterval(handleInput, 500)
    return () => clearInterval(interval)
  }, [activeTab, detectAccountMention, contextAccount, loadContextForAccount])

  // =============================================================================
  // Helpers
  // =============================================================================

  const filteredAccounts = useMemo(() => {
    if (!searchQuery) return accounts
    const q = searchQuery.toLowerCase()
    return accounts.filter(
      (acc) =>
        acc.name.toLowerCase().includes(q) ||
        acc.description?.toLowerCase().includes(q)
    )
  }, [accounts, searchQuery])

  const getStatusColor = (status: string) => {
    const s = STATUS_OPTIONS.find((o) => o.value === status)
    return s?.color || 'bg-gray-500'
  }

  const getActivityIcon = (type?: string) => {
    const a = ACTIVITY_TYPES.find((t) => t.value === type)
    return a?.icon || '📝'
  }

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return ''
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    })
  }

  // =============================================================================
  // Account CRUD
  // =============================================================================

  const openNewAccount = () => {
    setEditingAccount(null)
    setAccountName('')
    setAccountDescription('')
    setAccountStatus('active')
    setSimilarAccounts([])
    setCheckingSimilar(false)
    setIsAccountModalOpen(true)
  }

  const openEditAccount = (account: WorkAccount) => {
    setEditingAccount(account)
    setAccountName(account.name)
    setAccountDescription(account.description || '')
    setAccountStatus(account.status)
    setSimilarAccounts([])
    setCheckingSimilar(false)
    setIsAccountModalOpen(true)
  }

  const saveAccount = async () => {
    if (!accountName.trim()) return

    setSaving(true)
    try {
      if (editingAccount) {
        await api.updateWorkAccount(editingAccount.account_id, {
          name: accountName,
          description: accountDescription || undefined,
          status: accountStatus as 'active' | 'inactive' | 'prospect' | 'closed',
        })
      } else {
        const data: AccountCreate = {
          name: accountName,
          description: accountDescription || undefined,
        }
        await api.createWorkAccount(data)
      }
      setIsAccountModalOpen(false)
      loadAccounts()
    } catch (err) {
      console.error('Failed to save account:', err)
    }
    setSaving(false)
  }

  const deleteAccount = async (accountId: string) => {
    if (!confirm('Are you sure you want to delete this account and all its notes?'))
      return
    try {
      await api.deleteWorkAccount(accountId)
      setSelectedAccount(null)
      loadAccounts()
    } catch (err) {
      console.error('Failed to delete account:', err)
    }
  }

  // =============================================================================
  // Note CRUD
  // =============================================================================

  const openNewNote = () => {
    setNoteContent('')
    setNoteActivityType('note')
    setIsNoteModalOpen(true)
  }

  const saveNote = async () => {
    if (!noteContent.trim() || !selectedAccount) return

    setSaving(true)
    try {
      const data: WorkNoteCreate = {
        content: noteContent,
        activity_type: noteActivityType as 'meeting' | 'call' | 'email' | 'task' | 'note' | 'follow_up',
      }
      await api.createWorkNote(selectedAccount.account_id, data)
      setIsNoteModalOpen(false)
      loadAccountDetails(selectedAccount)
    } catch (err) {
      console.error('Failed to save note:', err)
    }
    setSaving(false)
  }

  const deleteNote = async (noteId: string) => {
    if (!confirm('Delete this note?')) return
    try {
      await api.deleteWorkNote(noteId)
      if (selectedAccount) {
        loadAccountDetails(selectedAccount)
      }
    } catch (err) {
      console.error('Failed to delete note:', err)
    }
  }

  // =============================================================================
  // Contact CRUD
  // =============================================================================

  const openAddContact = () => {
    setContactName('')
    setContactRole('')
    setContactEmail('')
    setContactPhone('')
    setIsContactModalOpen(true)
  }

  const saveContact = async () => {
    if (!contactName.trim() || !selectedAccount) return

    setSaving(true)
    try {
      const contact: WorkContact = {
        name: contactName,
        role: contactRole || undefined,
        email: contactEmail || undefined,
        phone: contactPhone || undefined,
      }
      await api.addAccountContact(selectedAccount.account_id, contact)
      setIsContactModalOpen(false)
      const updated = await api.getWorkAccount(selectedAccount.account_id)
      setSelectedAccount(updated)
    } catch (err) {
      console.error('Failed to add contact:', err)
    }
    setSaving(false)
  }

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
      <div className="flex items-center justify-between px-6 py-4 border-b border-surface-600 bg-surface-800">
        <div>
          <h1 className="text-2xl font-bold text-white">Work</h1>
          <p className="text-sm text-gray-400 mt-1">Customer notes and account management</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveTab('chat')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'chat'
                ? 'bg-primary-500 text-white'
                : 'bg-surface-700 text-gray-300 hover:bg-surface-600'
            }`}
          >
            <span className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
              </svg>
              Chat
            </span>
          </button>
          <button
            onClick={() => setActiveTab('accounts')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'accounts'
                ? 'bg-primary-500 text-white'
                : 'bg-surface-700 text-gray-300 hover:bg-surface-600'
            }`}
          >
            <span className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
              </svg>
              Accounts
            </span>
          </button>
          <button
            onClick={() => setActiveTab('profile')}
            className={`px-4 py-2 rounded-lg font-medium transition-colors ${
              activeTab === 'profile'
                ? 'bg-primary-500 text-white'
                : 'bg-surface-700 text-gray-300 hover:bg-surface-600'
            }`}
          >
            <span className="flex items-center gap-2">
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
              Profile
            </span>
          </button>
        </div>
      </div>

      {/* Tab Content */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' ? (
          /* ============================================================= */
          /* CHAT TAB                                                      */
          /* ============================================================= */
          <div className="h-full flex">
            {/* Main Chat Area */}
            <div className="flex-1 flex flex-col">
              {/* Model Badge */}
              <div className="p-3 border-b border-surface-600 bg-surface-800 flex items-center gap-2">
                <span className="text-sm text-gray-400">Model:</span>
                <Link
                  to="/settings"
                  className="flex items-center gap-2 px-2 py-1 bg-surface-700 border border-surface-600 rounded text-sm text-surface-300 hover:border-primary hover:text-white transition-colors"
                  title="Configure in Settings"
                >
                  <Bot className="w-3 h-3" />
                  <span>{currentModel || 'Loading...'}</span>
                  <Settings className="w-3 h-3 opacity-50" />
                </Link>
              </div>
              {/* Chat Panel */}
              <div className="flex-1 overflow-hidden">
                <ChatPanel
                  sessionId={sessionId}
                  context="work"
                  placeholder="Ask about accounts, add notes, search history..."
                  onModelLoaded={handleModelLoaded}
                  onNewChat={handleNewChat}
                />
              </div>
            </div>

            {/* Context Panel */}
            <div className="w-80 border-l border-surface-600 bg-surface-800 overflow-y-auto">
              <div className="p-4">
                <h3 className="text-sm font-semibold text-gray-400 uppercase tracking-wide mb-4">
                  Context
                </h3>

                {loadingContext ? (
                  <div className="flex items-center justify-center py-8">
                    <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-primary-500"></div>
                  </div>
                ) : contextAccount ? (
                  <div className="space-y-4">
                    {/* Account Header */}
                    <div className="p-3 bg-surface-700 rounded-lg">
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${getStatusColor(contextAccount.status)}`} />
                        <h4 className="font-semibold text-white">{contextAccount.name}</h4>
                      </div>
                      {contextAccount.description && (
                        <p className="text-sm text-gray-400 mt-1">{contextAccount.description}</p>
                      )}
                      <div className="flex gap-4 mt-2 text-xs text-gray-500">
                        <span>{contextStats?.total_notes || 0} notes</span>
                        <span>{contextStats?.contact_count || 0} contacts</span>
                      </div>
                    </div>

                    {/* Contacts */}
                    {contextAccount.contacts && contextAccount.contacts.length > 0 && (
                      <div>
                        <h5 className="text-xs font-semibold text-gray-400 uppercase mb-2">Contacts</h5>
                        <div className="space-y-2">
                          {contextAccount.contacts.slice(0, 5).map((contact, idx) => (
                            <div key={idx} className="p-2 bg-surface-700 rounded text-sm">
                              <div className="text-white">{contact.name}</div>
                              {contact.role && (
                                <div className="text-gray-400 text-xs">{contact.role}</div>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Recent Notes */}
                    {contextNotes.length > 0 && (
                      <div>
                        <h5 className="text-xs font-semibold text-gray-400 uppercase mb-2">Recent Notes</h5>
                        <div className="space-y-2">
                          {contextNotes.slice(0, 5).map((note) => (
                            <div key={note.note_id} className="p-2 bg-surface-700 rounded text-sm">
                              <div className="flex items-center gap-2 text-xs text-gray-400">
                                <span>{getActivityIcon(note.activity_type)}</span>
                                <span>{formatDate(note.created_at)}</span>
                              </div>
                              <p className="text-gray-300 mt-1 line-clamp-2">{note.content}</p>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Action Items */}
                    {contextStats?.pending_action_items && contextStats.pending_action_items.length > 0 && (
                      <div>
                        <h5 className="text-xs font-semibold text-gray-400 uppercase mb-2">Action Items</h5>
                        <div className="space-y-1">
                          {contextStats.pending_action_items.map((item, idx) => (
                            <div key={idx} className="flex items-center gap-2 text-sm text-yellow-400">
                              <span>○</span>
                              <span>{item.task}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center text-gray-500 py-8">
                    <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    <p className="text-sm">Mention an account name in your message to see context here</p>
                    {accounts.length > 0 && (
                      <p className="text-xs mt-2 text-gray-600">
                        Try: {accounts.slice(0, 3).map(a => a.name).join(', ')}
                      </p>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        ) : activeTab === 'accounts' ? (
          /* ============================================================= */
          /* ACCOUNTS TAB                                                  */
          /* ============================================================= */
          <div className="h-full flex">
            {/* Account List - Left Panel */}
            <div className="w-80 border-r border-surface-600 flex flex-col bg-surface-800">
              <div className="p-4 border-b border-surface-600">
                <div className="flex items-center justify-between mb-3">
                  <h2 className="text-lg font-semibold text-white">Accounts</h2>
                  <button
                    onClick={openNewAccount}
                    className="p-2 text-primary-500 hover:bg-surface-700 rounded"
                    title="New Account"
                  >
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                    </svg>
                  </button>
                </div>
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search accounts..."
                  className="magnetic-input w-full mb-2"
                />
                <select
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                  className="magnetic-input w-full text-sm"
                >
                  <option value="">All Statuses</option>
                  {STATUS_OPTIONS.map((s) => (
                    <option key={s.value} value={s.value}>
                      {s.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="flex-1 overflow-y-auto">
                {filteredAccounts.length === 0 ? (
                  <p className="text-gray-500 text-center py-8">No accounts found</p>
                ) : (
                  filteredAccounts.map((account) => (
                    <div
                      key={account.account_id}
                      onClick={() => setSelectedAccount(account)}
                      className={`p-4 cursor-pointer border-b border-surface-700 hover:bg-surface-700 transition-colors ${
                        selectedAccount?.account_id === account.account_id
                          ? 'bg-surface-700 border-l-2 border-l-primary-500'
                          : ''
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`w-2 h-2 rounded-full ${getStatusColor(account.status)}`} />
                        <h3 className="text-white font-medium truncate">{account.name}</h3>
                      </div>
                      {account.description && (
                        <p className="text-gray-400 text-sm mt-1 line-clamp-2">{account.description}</p>
                      )}
                      <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                        <span>{account.contacts?.length || 0} contacts</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Account Detail - Center */}
            <div className="flex-1 overflow-auto">
              {selectedAccount ? (
                <div className="p-6">
                  {/* Account Header */}
                  <div className="flex items-start justify-between mb-6">
                    <div>
                      <div className="flex items-center gap-3">
                        <h1 className="text-2xl font-bold text-white">{selectedAccount.name}</h1>
                        <span
                          className={`px-2 py-0.5 rounded text-xs text-white ${getStatusColor(
                            selectedAccount.status
                          )}`}
                        >
                          {selectedAccount.status}
                        </span>
                      </div>
                      {selectedAccount.description && (
                        <p className="text-gray-400 mt-2">{selectedAccount.description}</p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      <button onClick={() => openEditAccount(selectedAccount)} className="magnetic-button-secondary">
                        Edit
                      </button>
                      <button
                        onClick={() => deleteAccount(selectedAccount.account_id)}
                        className="magnetic-button-secondary text-red-400 hover:text-red-300"
                      >
                        Delete
                      </button>
                    </div>
                  </div>

                  {/* Stats */}
                  {accountStats && (
                    <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-6">
                      <div className="magnetic-card p-4">
                        <div className="text-sm text-gray-400">Total Notes</div>
                        <div className="text-2xl font-bold text-white">{accountStats.total_notes}</div>
                      </div>
                      <div className="magnetic-card p-4">
                        <div className="text-sm text-gray-400">Contacts</div>
                        <div className="text-2xl font-bold text-primary-500">
                          {accountStats.contact_count}
                        </div>
                      </div>
                      <div className="magnetic-card p-4">
                        <div className="text-sm text-gray-400">Last Activity</div>
                        <div className="text-lg font-bold text-white">
                          {accountStats.last_activity
                            ? formatDate(accountStats.last_activity)
                            : 'Never'}
                        </div>
                      </div>
                      <div className="magnetic-card p-4">
                        <div className="text-sm text-gray-400">Pending Actions</div>
                        <div className="text-2xl font-bold text-yellow-500">
                          {accountStats.pending_action_items?.length || 0}
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Company Intelligence */}
                  <div className="magnetic-card p-4 mb-6">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="text-lg font-semibold text-white">Company Intelligence</h2>
                      <button
                        onClick={() => enrichAccount(!!selectedAccount?.extra_data?.intelligence)}
                        disabled={enriching}
                        className="magnetic-button-secondary text-sm flex items-center gap-2"
                      >
                        {enriching ? (
                          <>
                            <span className="animate-spin">⏳</span>
                            Enriching...
                          </>
                        ) : selectedAccount?.extra_data?.intelligence ? (
                          '↻ Refresh'
                        ) : (
                          '✨ Gather Intelligence'
                        )}
                      </button>
                    </div>
                    {selectedAccount?.extra_data?.intelligence ? (
                      <div className="space-y-4">
                        {selectedAccount.extra_data.intelligence.summary && (
                          <div>
                            <div className="text-xs text-gray-500 uppercase mb-1">About</div>
                            <p className="text-gray-300 text-sm">{selectedAccount.extra_data.intelligence.summary}</p>
                          </div>
                        )}
                        <div className="grid grid-cols-2 gap-4">
                          {selectedAccount.extra_data.intelligence.industry && (
                            <div>
                              <div className="text-xs text-gray-500 uppercase mb-1">Industry</div>
                              <div className="text-white">{selectedAccount.extra_data.intelligence.industry}</div>
                            </div>
                          )}
                          {selectedAccount.extra_data.intelligence.headquarters && (
                            <div>
                              <div className="text-xs text-gray-500 uppercase mb-1">Headquarters</div>
                              <div className="text-white">{selectedAccount.extra_data.intelligence.headquarters}</div>
                            </div>
                          )}
                          {selectedAccount.extra_data.intelligence.employee_count_range && (
                            <div>
                              <div className="text-xs text-gray-500 uppercase mb-1">Employees</div>
                              <div className="text-white">{selectedAccount.extra_data.intelligence.employee_count_range}</div>
                            </div>
                          )}
                          {selectedAccount.extra_data.intelligence.founded_year && (
                            <div>
                              <div className="text-xs text-gray-500 uppercase mb-1">Founded</div>
                              <div className="text-white">{selectedAccount.extra_data.intelligence.founded_year}</div>
                            </div>
                          )}
                          {selectedAccount.extra_data.intelligence.website_url && (
                            <div>
                              <div className="text-xs text-gray-500 uppercase mb-1">Website</div>
                              <a
                                href={selectedAccount.extra_data.intelligence.website_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary-400 hover:text-primary-300"
                              >
                                {(() => {
                                  try {
                                    return new URL(selectedAccount.extra_data.intelligence.website_url).hostname
                                  } catch {
                                    return selectedAccount.extra_data.intelligence.website_url
                                  }
                                })()}
                              </a>
                            </div>
                          )}
                          {selectedAccount.extra_data.intelligence.stock_ticker && (
                            <div>
                              <div className="text-xs text-gray-500 uppercase mb-1">Stock</div>
                              <div className="text-white">
                                {selectedAccount.extra_data.intelligence.stock_ticker}
                                {selectedAccount.extra_data.intelligence.stock_exchange && (
                                  <span className="text-gray-400 text-sm ml-1">
                                    ({selectedAccount.extra_data.intelligence.stock_exchange})
                                  </span>
                                )}
                              </div>
                            </div>
                          )}
                        </div>
                        {selectedAccount.extra_data.intelligence.enriched_at && (
                          <div className="text-xs text-gray-600 mt-2">
                            Last updated: {formatDate(selectedAccount.extra_data.intelligence.enriched_at)}
                          </div>
                        )}
                      </div>
                    ) : (
                      <p className="text-gray-500 text-sm">
                        Click "Gather Intelligence" to automatically research this company and retrieve headquarters, industry, employee count, and more.
                      </p>
                    )}
                  </div>

                  {/* AI Summary */}
                  <div className="magnetic-card p-4 mb-6">
                    <div className="flex items-center justify-between mb-3">
                      <h2 className="text-lg font-semibold text-white">AI Summary</h2>
                      <button
                        onClick={generateSummary}
                        disabled={loadingSummary}
                        className="magnetic-button-secondary text-sm flex items-center gap-2"
                      >
                        {loadingSummary ? (
                          <>
                            <span className="animate-spin">⏳</span>
                            Generating...
                          </>
                        ) : accountSummary ? (
                          '↻ Refresh'
                        ) : (
                          '✨ Generate Summary'
                        )}
                      </button>
                    </div>
                    {accountSummary ? (
                      <div className="space-y-3">
                        <div>
                          <div className="text-xs text-gray-500 uppercase mb-1">Overview</div>
                          <p className="text-gray-300 text-sm">{accountSummary.account_overview}</p>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 uppercase mb-1">Recent Activity</div>
                          <p className="text-gray-300 text-sm">{accountSummary.recent_activity_summary}</p>
                        </div>
                        <div className="text-xs text-gray-600">Generated with {accountSummary.model_used}</div>
                      </div>
                    ) : (
                      <p className="text-gray-500 text-sm">
                        Click "Generate Summary" to create an AI-powered overview of this account.
                      </p>
                    )}
                  </div>

                  {/* Events Timeline */}
                  {accountEvents && (accountEvents.overdue.length > 0 || accountEvents.upcoming.length > 0 || accountEvents.recent.length > 0) && (
                    <div className="magnetic-card p-4 mb-6">
                      <h2 className="text-lg font-semibold text-white mb-3">Events Timeline</h2>
                      <div className="flex gap-2 mb-4">
                        <button
                          onClick={() => setEventsTab('overdue')}
                          className={`px-3 py-1 rounded-full text-sm ${
                            eventsTab === 'overdue'
                              ? 'bg-red-500/20 text-red-400 border border-red-500/50'
                              : 'bg-surface-600 text-gray-400 hover:text-white'
                          }`}
                        >
                          Overdue ({accountEvents.overdue.length})
                        </button>
                        <button
                          onClick={() => setEventsTab('upcoming')}
                          className={`px-3 py-1 rounded-full text-sm ${
                            eventsTab === 'upcoming'
                              ? 'bg-primary-500/20 text-primary-400 border border-primary-500/50'
                              : 'bg-surface-600 text-gray-400 hover:text-white'
                          }`}
                        >
                          Upcoming ({accountEvents.upcoming.length})
                        </button>
                        <button
                          onClick={() => setEventsTab('recent')}
                          className={`px-3 py-1 rounded-full text-sm ${
                            eventsTab === 'recent'
                              ? 'bg-gray-500/20 text-gray-300 border border-gray-500/50'
                              : 'bg-surface-600 text-gray-400 hover:text-white'
                          }`}
                        >
                          Recent ({accountEvents.recent.length})
                        </button>
                      </div>
                      <div className="space-y-2 max-h-48 overflow-y-auto">
                        {(eventsTab === 'overdue' ? accountEvents.overdue :
                          eventsTab === 'upcoming' ? accountEvents.upcoming :
                          accountEvents.recent
                        ).map((event, idx) => (
                          <div
                            key={idx}
                            className={`p-3 rounded-lg flex items-start gap-3 ${
                              eventsTab === 'overdue' ? 'bg-red-500/10 border border-red-500/20' :
                              eventsTab === 'upcoming' ? 'bg-surface-600' :
                              'bg-surface-600/50'
                            }`}
                          >
                            <span className="text-lg">
                              {event.type === 'action_item' ? '✅' :
                               event.activity_type === 'meeting' ? '📅' :
                               event.activity_type === 'call' ? '📞' :
                               event.activity_type === 'email' ? '📧' :
                               event.activity_type === 'follow_up' ? '🔄' : '📝'}
                            </span>
                            <div className="flex-1 min-w-0">
                              <div className="text-white text-sm">
                                {event.type === 'action_item' ? event.task : event.content_preview}
                              </div>
                              <div className="text-xs text-gray-500 mt-1">
                                {new Date(event.date).toLocaleDateString('en-US', {
                                  month: 'short',
                                  day: 'numeric',
                                  year: 'numeric'
                                })}
                                {eventsTab === 'overdue' && (
                                  <span className="text-red-400 ml-2">
                                    ({Math.floor((Date.now() - new Date(event.date).getTime()) / (1000 * 60 * 60 * 24))}d overdue)
                                  </span>
                                )}
                              </div>
                            </div>
                            {/* Action buttons for action items */}
                            {event.type === 'action_item' && event.task && (
                              <div className="flex items-center gap-1 ml-2">
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    completeActionItem(event.note_id, event.task!)
                                  }}
                                  className="p-1.5 text-green-400 hover:bg-green-500/20 rounded transition-colors"
                                  title="Mark as completed"
                                >
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                  </svg>
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation()
                                    deleteActionItem(event.note_id, event.task!)
                                  }}
                                  className="p-1.5 text-red-400 hover:bg-red-500/20 rounded transition-colors"
                                  title="Delete action item"
                                >
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                            )}
                          </div>
                        ))}
                        {(eventsTab === 'overdue' && accountEvents.overdue.length === 0) && (
                          <p className="text-gray-500 text-sm text-center py-2">No overdue items</p>
                        )}
                        {(eventsTab === 'upcoming' && accountEvents.upcoming.length === 0) && (
                          <p className="text-gray-500 text-sm text-center py-2">No upcoming events</p>
                        )}
                        {(eventsTab === 'recent' && accountEvents.recent.length === 0) && (
                          <p className="text-gray-500 text-sm text-center py-2">No recent events</p>
                        )}
                      </div>
                    </div>
                  )}

                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
                    {/* Contacts */}
                    <div className="magnetic-card p-4">
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-white">Contacts</h2>
                        <button
                          onClick={openAddContact}
                          className="text-primary-500 hover:text-primary-400 text-sm"
                        >
                          + Add
                        </button>
                      </div>
                      <div className="space-y-3">
                        {selectedAccount.contacts && selectedAccount.contacts.length > 0 ? (
                          selectedAccount.contacts.map((contact, idx) => (
                            <div key={idx} className="p-3 bg-surface-600 rounded-lg">
                              <div className="font-medium text-white">{contact.name}</div>
                              {contact.role && (
                                <div className="text-sm text-gray-400">{contact.role}</div>
                              )}
                              {contact.email && (
                                <div className="text-sm text-primary-400">{contact.email}</div>
                              )}
                              {contact.phone && (
                                <div className="text-sm text-gray-400">{contact.phone}</div>
                              )}
                            </div>
                          ))
                        ) : (
                          <p className="text-gray-500 text-sm">No contacts yet</p>
                        )}
                      </div>
                    </div>

                    {/* Notes Timeline */}
                    <div className="lg:col-span-2 magnetic-card p-4">
                      <div className="flex items-center justify-between mb-4">
                        <h2 className="text-lg font-semibold text-white">Notes</h2>
                        <button
                          onClick={openNewNote}
                          className="magnetic-button-primary flex items-center gap-2"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                          </svg>
                          Add Note
                        </button>
                      </div>
                      <div className="space-y-4 max-h-[500px] overflow-y-auto">
                        {accountNotes.length === 0 ? (
                          <p className="text-gray-500 text-center py-8">No notes yet. Add your first note!</p>
                        ) : (
                          accountNotes.map((note) => (
                            <div key={note.note_id} className="p-4 bg-surface-600 rounded-lg">
                              <div className="flex items-start justify-between">
                                <div className="flex items-center gap-2">
                                  <span className="text-xl">{getActivityIcon(note.activity_type)}</span>
                                  <span className="text-sm text-gray-400">{formatDate(note.created_at)}</span>
                                  {note.activity_type && (
                                    <span className="text-xs bg-surface-500 text-gray-300 px-2 py-0.5 rounded">
                                      {note.activity_type}
                                    </span>
                                  )}
                                </div>
                                <button
                                  onClick={() => deleteNote(note.note_id)}
                                  className="text-gray-500 hover:text-red-500"
                                >
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                  </svg>
                                </button>
                              </div>
                              <p className="text-gray-300 mt-2 whitespace-pre-wrap">{note.content}</p>
                              {note.mentioned_contacts && note.mentioned_contacts.length > 0 && (
                                <div className="flex gap-1 mt-2">
                                  {note.mentioned_contacts.map((c, i) => (
                                    <span key={i} className="text-xs bg-primary-500/20 text-primary-400 px-2 py-0.5 rounded">
                                      @{c}
                                    </span>
                                  ))}
                                </div>
                              )}
                              {note.action_items && note.action_items.length > 0 && (
                                <div className="mt-2 space-y-1">
                                  {note.action_items.map((item, i) => (
                                    <div
                                      key={i}
                                      className={`text-sm flex items-center gap-2 ${
                                        item.status === 'completed' ? 'text-gray-500 line-through' : 'text-yellow-400'
                                      }`}
                                    >
                                      <span>{item.status === 'completed' ? '✓' : '○'}</span>
                                      <span>{item.task}</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                              {note.tags && note.tags.length > 0 && (
                                <div className="flex gap-1 mt-2">
                                  {note.tags.map((tag, i) => (
                                    <span key={i} className="text-xs bg-surface-500 text-gray-300 px-2 py-0.5 rounded">
                                      {tag}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center h-full text-gray-500">
                  <svg className="w-16 h-16 mb-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" />
                  </svg>
                  <p className="text-lg">Select an account to view details</p>
                  <p className="text-sm mt-2">or create a new account to get started</p>
                </div>
              )}
            </div>

            {/* Chat Toggle Button */}
            <button
              onClick={() => setIsAccountsChatOpen(!isAccountsChatOpen)}
              className={`fixed bottom-6 right-6 p-4 rounded-full shadow-lg transition-all z-40 ${
                isAccountsChatOpen
                  ? 'bg-surface-600 text-gray-400'
                  : 'bg-primary-500 text-white hover:bg-primary-400'
              }`}
              title={isAccountsChatOpen ? 'Close chat' : 'Open chat'}
            >
              {isAccountsChatOpen ? (
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                </svg>
              )}
            </button>

            {/* Chat Sidebar */}
            {isAccountsChatOpen && (
              <div className="fixed right-0 top-0 h-full w-96 bg-surface-700 border-l border-surface-600 flex flex-col z-30 shadow-xl">
                <div className="p-4 border-b border-surface-600">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-white">Work Assistant</h3>
                    <button
                      onClick={() => setIsAccountsChatOpen(false)}
                      className="text-gray-400 hover:text-white"
                    >
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                  {selectedAccount && (
                    <div className="text-xs text-primary-400 bg-primary-500/10 px-2 py-1 rounded">
                      Context: {selectedAccount.name}
                    </div>
                  )}
                </div>
                <div className="flex-1 overflow-hidden">
                  <ChatPanel
                    sessionId={accountsChatSessionId}
                    context="work"
                    placeholder={selectedAccount ? `Ask about ${selectedAccount.name}...` : "Ask about your accounts..."}
                  />
                </div>
              </div>
            )}
          </div>
        ) : (
          /* ============================================================= */
          /* PROFILE TAB                                                   */
          /* ============================================================= */
          <div className="h-full overflow-auto p-6">
            <div className="max-w-4xl mx-auto">
              {/* Header */}
              <div className="flex items-center justify-between mb-6">
                <div>
                  <h1 className="text-2xl font-bold text-white">Your Work Profile</h1>
                  <p className="text-sm text-gray-400 mt-1">
                    The AI learns about you from conversations and builds this profile
                  </p>
                </div>
                <button
                  onClick={learnFromChats}
                  disabled={learningFromChats}
                  className="magnetic-button-primary flex items-center gap-2"
                >
                  {learningFromChats ? (
                    <>
                      <span className="animate-spin">⏳</span>
                      Learning...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                      </svg>
                      Learn from Chats
                    </>
                  )}
                </button>
              </div>

              {loadingProfile ? (
                <div className="flex items-center justify-center py-12">
                  <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-500"></div>
                </div>
              ) : (
                <div className="space-y-6">
                  {/* Identity Card */}
                  <div className="magnetic-card p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold text-white">Identity</h2>
                      {editingSection === 'identity' ? (
                        <div className="flex gap-2">
                          <button
                            onClick={() => setEditingSection(null)}
                            className="text-gray-400 hover:text-white text-sm"
                          >
                            Cancel
                          </button>
                          <button
                            onClick={async () => {
                              const [name, role, company, department] = editValue.split('\n')
                              await saveProfileField('name', name || null)
                              await saveProfileField('role', role || null)
                              await saveProfileField('company', company || null)
                              await saveProfileField('department', department || null)
                            }}
                            className="text-primary-500 hover:text-primary-400 text-sm"
                          >
                            Save
                          </button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingSection('identity')
                            setEditValue([
                              profile?.name || '',
                              profile?.role || '',
                              profile?.company || '',
                              profile?.department || '',
                            ].join('\n'))
                          }}
                          className="text-primary-500 hover:text-primary-400 text-sm"
                        >
                          Edit
                        </button>
                      )}
                    </div>
                    {editingSection === 'identity' ? (
                      <div className="space-y-3">
                        <input
                          type="text"
                          value={editValue.split('\n')[0]}
                          onChange={(e) => {
                            const parts = editValue.split('\n')
                            parts[0] = e.target.value
                            setEditValue(parts.join('\n'))
                          }}
                          placeholder="Your name..."
                          className="magnetic-input w-full"
                        />
                        <input
                          type="text"
                          value={editValue.split('\n')[1]}
                          onChange={(e) => {
                            const parts = editValue.split('\n')
                            parts[1] = e.target.value
                            setEditValue(parts.join('\n'))
                          }}
                          placeholder="Your role..."
                          className="magnetic-input w-full"
                        />
                        <input
                          type="text"
                          value={editValue.split('\n')[2]}
                          onChange={(e) => {
                            const parts = editValue.split('\n')
                            parts[2] = e.target.value
                            setEditValue(parts.join('\n'))
                          }}
                          placeholder="Your company..."
                          className="magnetic-input w-full"
                        />
                        <input
                          type="text"
                          value={editValue.split('\n')[3]}
                          onChange={(e) => {
                            const parts = editValue.split('\n')
                            parts[3] = e.target.value
                            setEditValue(parts.join('\n'))
                          }}
                          placeholder="Your department..."
                          className="magnetic-input w-full"
                        />
                      </div>
                    ) : (
                      <div className="grid grid-cols-2 gap-4">
                        <div>
                          <div className="text-xs text-gray-500 uppercase">Name</div>
                          <div className="text-white">{profile?.name || <span className="text-gray-500 italic">Not set</span>}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 uppercase">Role</div>
                          <div className="text-white">{profile?.role || <span className="text-gray-500 italic">Not set</span>}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 uppercase">Company</div>
                          <div className="text-white">{profile?.company || <span className="text-gray-500 italic">Not set</span>}</div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 uppercase">Department</div>
                          <div className="text-white">{profile?.department || <span className="text-gray-500 italic">Not set</span>}</div>
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Responsibilities */}
                  <div className="magnetic-card p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold text-white">Responsibilities</h2>
                      {editingSection === 'responsibilities' ? (
                        <div className="flex gap-2">
                          <button onClick={() => setEditingSection(null)} className="text-gray-400 hover:text-white text-sm">Cancel</button>
                          <button onClick={() => saveProfileField('responsibilities', editListValue)} className="text-primary-500 hover:text-primary-400 text-sm">Save</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingSection('responsibilities')
                            setEditListValue(profile?.responsibilities || [])
                            setNewListItem('')
                          }}
                          className="text-primary-500 hover:text-primary-400 text-sm"
                        >
                          Edit
                        </button>
                      )}
                    </div>
                    {editingSection === 'responsibilities' ? (
                      <div className="space-y-2">
                        {editListValue.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <input
                              type="text"
                              value={item}
                              onChange={(e) => {
                                const newList = [...editListValue]
                                newList[idx] = e.target.value
                                setEditListValue(newList)
                              }}
                              className="magnetic-input flex-1"
                            />
                            <button onClick={() => setEditListValue(editListValue.filter((_, i) => i !== idx))} className="text-red-400 hover:text-red-300">
                              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        ))}
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={newListItem}
                            onChange={(e) => setNewListItem(e.target.value)}
                            placeholder="Add responsibility..."
                            className="magnetic-input flex-1"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && newListItem.trim()) {
                                setEditListValue([...editListValue, newListItem.trim()])
                                setNewListItem('')
                              }
                            }}
                          />
                          <button
                            onClick={() => {
                              if (newListItem.trim()) {
                                setEditListValue([...editListValue, newListItem.trim()])
                                setNewListItem('')
                              }
                            }}
                            className="text-primary-500 hover:text-primary-400"
                          >
                            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    ) : (
                      <ul className="space-y-1">
                        {profile?.responsibilities && profile.responsibilities.length > 0 ? (
                          profile.responsibilities.map((r, idx) => (
                            <li key={idx} className="text-gray-300 flex items-start gap-2">
                              <span className="text-primary-500">•</span>
                              <span>{r}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-gray-500 italic">No responsibilities set</li>
                        )}
                      </ul>
                    )}
                  </div>

                  {/* Expertise Areas */}
                  <div className="magnetic-card p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold text-white">Expertise Areas</h2>
                      {editingSection === 'expertise' ? (
                        <div className="flex gap-2">
                          <button onClick={() => setEditingSection(null)} className="text-gray-400 hover:text-white text-sm">Cancel</button>
                          <button onClick={() => saveProfileField('expertise_areas', editListValue)} className="text-primary-500 hover:text-primary-400 text-sm">Save</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingSection('expertise')
                            setEditListValue(profile?.expertise_areas || [])
                            setNewListItem('')
                          }}
                          className="text-primary-500 hover:text-primary-400 text-sm"
                        >
                          Edit
                        </button>
                      )}
                    </div>
                    {editingSection === 'expertise' ? (
                      <div className="space-y-2">
                        <div className="flex flex-wrap gap-2 mb-2">
                          {editListValue.map((item, idx) => (
                            <span key={idx} className="inline-flex items-center gap-1 px-3 py-1 bg-primary-500/20 text-primary-400 rounded-full">
                              {item}
                              <button onClick={() => setEditListValue(editListValue.filter((_, i) => i !== idx))} className="hover:text-red-400">
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </span>
                          ))}
                        </div>
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={newListItem}
                            onChange={(e) => setNewListItem(e.target.value)}
                            placeholder="Add expertise..."
                            className="magnetic-input flex-1"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && newListItem.trim()) {
                                setEditListValue([...editListValue, newListItem.trim()])
                                setNewListItem('')
                              }
                            }}
                          />
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap gap-2">
                        {profile?.expertise_areas && profile.expertise_areas.length > 0 ? (
                          profile.expertise_areas.map((area, idx) => (
                            <span key={idx} className="px-3 py-1 bg-primary-500/20 text-primary-400 rounded-full text-sm">
                              {area}
                            </span>
                          ))
                        ) : (
                          <span className="text-gray-500 italic">No expertise areas set</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* Current Priorities */}
                  <div className="magnetic-card p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold text-white">Current Priorities</h2>
                      {editingSection === 'priorities' ? (
                        <div className="flex gap-2">
                          <button onClick={() => setEditingSection(null)} className="text-gray-400 hover:text-white text-sm">Cancel</button>
                          <button onClick={() => saveProfileField('current_priorities', editListValue)} className="text-primary-500 hover:text-primary-400 text-sm">Save</button>
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setEditingSection('priorities')
                            setEditListValue(profile?.current_priorities || [])
                            setNewListItem('')
                          }}
                          className="text-primary-500 hover:text-primary-400 text-sm"
                        >
                          Edit
                        </button>
                      )}
                    </div>
                    {editingSection === 'priorities' ? (
                      <div className="space-y-2">
                        {editListValue.map((item, idx) => (
                          <div key={idx} className="flex items-center gap-2">
                            <span className="text-yellow-500 font-medium w-6">{idx + 1}.</span>
                            <input
                              type="text"
                              value={item}
                              onChange={(e) => {
                                const newList = [...editListValue]
                                newList[idx] = e.target.value
                                setEditListValue(newList)
                              }}
                              className="magnetic-input flex-1"
                            />
                            <button onClick={() => setEditListValue(editListValue.filter((_, i) => i !== idx))} className="text-red-400 hover:text-red-300">
                              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                              </svg>
                            </button>
                          </div>
                        ))}
                        <div className="flex items-center gap-2">
                          <span className="text-gray-500 font-medium w-6">{editListValue.length + 1}.</span>
                          <input
                            type="text"
                            value={newListItem}
                            onChange={(e) => setNewListItem(e.target.value)}
                            placeholder="Add priority..."
                            className="magnetic-input flex-1"
                            onKeyDown={(e) => {
                              if (e.key === 'Enter' && newListItem.trim()) {
                                setEditListValue([...editListValue, newListItem.trim()])
                                setNewListItem('')
                              }
                            }}
                          />
                        </div>
                      </div>
                    ) : (
                      <ol className="space-y-1">
                        {profile?.current_priorities && profile.current_priorities.length > 0 ? (
                          profile.current_priorities.map((p, idx) => (
                            <li key={idx} className="text-gray-300 flex items-start gap-2">
                              <span className="text-yellow-500 font-medium">{idx + 1}.</span>
                              <span>{p}</span>
                            </li>
                          ))
                        ) : (
                          <li className="text-gray-500 italic">No priorities set</li>
                        )}
                      </ol>
                    )}
                  </div>

                  {/* Learned Facts */}
                  <div className="magnetic-card p-4">
                    <div className="flex items-center justify-between mb-4">
                      <h2 className="text-lg font-semibold text-white">Learned Facts</h2>
                      <span className="text-xs text-gray-500">
                        {profile?.learned_facts?.length || 0} facts learned
                      </span>
                    </div>
                    {profile?.learned_facts && profile.learned_facts.length > 0 ? (
                      <div className="space-y-2">
                        {profile.learned_facts.map((fact: LearnedFact) => (
                          <div
                            key={fact.id}
                            className={`p-3 rounded-lg flex items-start justify-between gap-3 ${
                              fact.verified
                                ? 'bg-green-500/10 border border-green-500/20'
                                : 'bg-surface-600'
                            }`}
                          >
                            <div className="flex-1">
                              <div className="flex items-center gap-2">
                                <span className={fact.verified ? 'text-green-400' : 'text-yellow-400'}>
                                  {fact.verified ? '✓' : '?'}
                                </span>
                                <span className="text-white text-sm">{fact.fact}</span>
                              </div>
                              <div className="text-xs text-gray-500 mt-1">
                                <span className="capitalize">{fact.category}</span>
                                <span className="mx-2">•</span>
                                <span>{new Date(fact.learned_at).toLocaleDateString()}</span>
                                <span className="mx-2">•</span>
                                <span>{Math.round(fact.confidence * 100)}% confidence</span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              {!fact.verified && (
                                <button
                                  onClick={() => verifyFact(fact.id)}
                                  className="p-1.5 text-green-400 hover:bg-green-500/20 rounded transition-colors"
                                  title="Verify fact"
                                >
                                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                                  </svg>
                                </button>
                              )}
                              <button
                                onClick={() => deleteFact(fact.id)}
                                className="p-1.5 text-red-400 hover:bg-red-500/20 rounded transition-colors"
                                title="Delete fact"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                                </svg>
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="text-center py-6 text-gray-500">
                        <svg className="w-12 h-12 mx-auto mb-3 opacity-50" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
                        </svg>
                        <p className="text-sm">No facts learned yet</p>
                        <p className="text-xs mt-1">Chat in the Work tab and click "Learn from Chats" to extract facts about you</p>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ================================================================= */}
      {/* MODALS                                                           */}
      {/* ================================================================= */}

      {/* Account Modal */}
      {isAccountModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-700 rounded-lg w-full max-w-md">
            <div className="p-4 border-b border-surface-600 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">
                {editingAccount ? 'Edit Account' : 'New Account'}
              </h3>
              <button onClick={() => setIsAccountModalOpen(false)} className="text-gray-400 hover:text-white">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Account Name</label>
                <input
                  type="text"
                  value={accountName}
                  onChange={(e) => {
                    setAccountName(e.target.value)
                    checkSimilarAccounts(e.target.value)
                  }}
                  placeholder="Company or client name..."
                  className="magnetic-input w-full"
                />
                {/* Similar accounts warning/suggestions */}
                {!editingAccount && (checkingSimilar || similarAccounts.length > 0) && (
                  <div className="mt-2">
                    {checkingSimilar ? (
                      <div className="text-xs text-gray-500 flex items-center gap-2">
                        <span className="animate-spin">⏳</span>
                        Checking for similar accounts...
                      </div>
                    ) : similarAccounts.length > 0 && (
                      <div className="p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                        <div className="text-sm text-yellow-400 mb-2 flex items-center gap-2">
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                          </svg>
                          Similar accounts found
                        </div>
                        <div className="space-y-2">
                          {similarAccounts.map(({ account, score }) => (
                            <button
                              key={account.account_id}
                              onClick={() => {
                                setIsAccountModalOpen(false)
                                setSelectedAccount(account)
                              }}
                              className="w-full p-2 text-left bg-surface-600 hover:bg-surface-500 rounded-lg transition-colors"
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <span className={`w-2 h-2 rounded-full ${getStatusColor(account.status)}`} />
                                  <span className="text-white text-sm font-medium">{account.name}</span>
                                </div>
                                <span className="text-xs text-gray-500">{Math.round(score * 100)}% match</span>
                              </div>
                              {account.description && (
                                <p className="text-xs text-gray-400 mt-1 truncate">{account.description}</p>
                              )}
                            </button>
                          ))}
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                          Click an account to view it, or continue to create a new one.
                        </p>
                      </div>
                    )}
                  </div>
                )}
                {!editingAccount && accountName.trim().length >= 2 && similarAccounts.length === 0 && !checkingSimilar && (
                  <div className="mt-2 text-xs text-gray-500 flex items-center gap-1">
                    <span className="text-primary-400">✨</span>
                    Company intelligence will be gathered automatically
                  </div>
                )}
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Description</label>
                <textarea
                  value={accountDescription}
                  onChange={(e) => setAccountDescription(e.target.value)}
                  placeholder="Brief description..."
                  rows={3}
                  className="magnetic-input w-full resize-none"
                />
              </div>
              {editingAccount && (
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Status</label>
                  <select
                    value={accountStatus}
                    onChange={(e) => setAccountStatus(e.target.value)}
                    className="magnetic-input w-full"
                  >
                    {STATUS_OPTIONS.map((s) => (
                      <option key={s.value} value={s.value}>{s.label}</option>
                    ))}
                  </select>
                </div>
              )}
            </div>
            <div className="p-4 border-t border-surface-600 flex justify-end gap-3">
              <button onClick={() => setIsAccountModalOpen(false)} className="magnetic-button-secondary">
                Cancel
              </button>
              <button
                onClick={saveAccount}
                disabled={saving || !accountName.trim()}
                className="magnetic-button-primary disabled:opacity-50"
              >
                {saving ? 'Saving...' : editingAccount ? 'Update' : 'Create'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Note Modal */}
      {isNoteModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-700 rounded-lg w-full max-w-lg">
            <div className="p-4 border-b border-surface-600 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Add Note</h3>
              <button onClick={() => setIsNoteModalOpen(false)} className="text-gray-400 hover:text-white">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-2">Activity Type</label>
                <div className="flex flex-wrap gap-2">
                  {ACTIVITY_TYPES.map((type) => (
                    <button
                      key={type.value}
                      onClick={() => setNoteActivityType(type.value)}
                      className={`px-3 py-2 rounded-lg flex items-center gap-2 transition-all ${
                        noteActivityType === type.value
                          ? 'bg-primary-500 text-white'
                          : 'bg-surface-600 text-gray-300 hover:bg-surface-500'
                      }`}
                    >
                      <span>{type.icon}</span>
                      <span className="text-sm">{type.label}</span>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Note Content</label>
                <textarea
                  value={noteContent}
                  onChange={(e) => setNoteContent(e.target.value)}
                  placeholder="What happened? Include @names for contacts..."
                  rows={6}
                  className="magnetic-input w-full resize-none"
                />
              </div>
            </div>
            <div className="p-4 border-t border-surface-600 flex justify-end gap-3">
              <button onClick={() => setIsNoteModalOpen(false)} className="magnetic-button-secondary">
                Cancel
              </button>
              <button
                onClick={saveNote}
                disabled={saving || !noteContent.trim()}
                className="magnetic-button-primary disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Add Note'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Contact Modal */}
      {isContactModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-surface-700 rounded-lg w-full max-w-md">
            <div className="p-4 border-b border-surface-600 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Add Contact</h3>
              <button onClick={() => setIsContactModalOpen(false)} className="text-gray-400 hover:text-white">
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="p-4 space-y-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Name *</label>
                <input
                  type="text"
                  value={contactName}
                  onChange={(e) => setContactName(e.target.value)}
                  placeholder="Contact name..."
                  className="magnetic-input w-full"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Role</label>
                <input
                  type="text"
                  value={contactRole}
                  onChange={(e) => setContactRole(e.target.value)}
                  placeholder="e.g., Manager, Engineer..."
                  className="magnetic-input w-full"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Email</label>
                <input
                  type="email"
                  value={contactEmail}
                  onChange={(e) => setContactEmail(e.target.value)}
                  placeholder="email@example.com"
                  className="magnetic-input w-full"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Phone</label>
                <input
                  type="tel"
                  value={contactPhone}
                  onChange={(e) => setContactPhone(e.target.value)}
                  placeholder="+1 (555) 123-4567"
                  className="magnetic-input w-full"
                />
              </div>
            </div>
            <div className="p-4 border-t border-surface-600 flex justify-end gap-3">
              <button onClick={() => setIsContactModalOpen(false)} className="magnetic-button-secondary">
                Cancel
              </button>
              <button
                onClick={saveContact}
                disabled={saving || !contactName.trim()}
                className="magnetic-button-primary disabled:opacity-50"
              >
                {saving ? 'Saving...' : 'Add Contact'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
