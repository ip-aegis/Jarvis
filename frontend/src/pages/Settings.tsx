import { useState, useEffect } from 'react'
import { Sparkles, Check } from 'lucide-react'
import { api } from '../services/api'
import type { ModelDefaults } from '../types'

// Context display names for UI
const CONTEXT_LABELS: Record<keyof ModelDefaults, string> = {
  general: 'General Chat',
  monitoring: 'Lab / Monitoring',
  projects: 'Projects',
  network: 'Network',
  actions: 'Actions',
  home: 'Home Automation',
  journal: 'Journal',
  work: 'Work Notes',
}

interface Recommendation {
  model: string
  reason: string
}

export default function Settings() {
  const [models, setModels] = useState<{ name: string; owned_by: string }[]>([])
  const [defaults, setDefaults] = useState<ModelDefaults | null>(null)
  const [originalDefaults, setOriginalDefaults] = useState<ModelDefaults | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)

  // Recommendation state
  const [recommendations, setRecommendations] = useState<Record<string, Recommendation> | null>(null)
  const [loadingRecommendations, setLoadingRecommendations] = useState(false)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    setLoading(true)
    try {
      const [modelsRes, defaultsRes] = await Promise.all([
        api.getModels(),
        api.getModelDefaults(),
      ])
      setModels(modelsRes.models)
      setDefaults(defaultsRes)
      setOriginalDefaults(defaultsRes)
    } catch (err) {
      console.error('Failed to load settings:', err)
      setMessage({ type: 'error', text: 'Failed to load settings' })
    } finally {
      setLoading(false)
    }
  }

  const handleModelChange = (context: keyof ModelDefaults, model: string) => {
    if (defaults) {
      setDefaults({ ...defaults, [context]: model })
    }
  }

  const hasChanges = () => {
    if (!defaults || !originalDefaults) return false
    return JSON.stringify(defaults) !== JSON.stringify(originalDefaults)
  }

  const handleSave = async () => {
    if (!defaults || !hasChanges()) return

    setSaving(true)
    setMessage(null)
    try {
      // Only send changed values
      const changedDefaults: Partial<ModelDefaults> = {}
      for (const key of Object.keys(defaults) as (keyof ModelDefaults)[]) {
        if (defaults[key] !== originalDefaults?.[key]) {
          changedDefaults[key] = defaults[key]
        }
      }

      await api.updateModelDefaults(changedDefaults)
      setOriginalDefaults(defaults)
      setMessage({ type: 'success', text: 'Settings saved successfully' })
    } catch (err) {
      console.error('Failed to save settings:', err)
      setMessage({ type: 'error', text: 'Failed to save settings' })
    } finally {
      setSaving(false)
    }
  }

  const handleReset = () => {
    if (originalDefaults) {
      setDefaults(originalDefaults)
    }
    setRecommendations(null)
  }

  const handleGetRecommendations = async () => {
    setLoadingRecommendations(true)
    setMessage(null)
    try {
      const result = await api.getModelRecommendations()
      setRecommendations(result.recommendations)
      setMessage({
        type: 'success',
        text: `AI recommendations generated using ${result.model_used}`,
      })
    } catch (err) {
      console.error('Failed to get recommendations:', err)
      setMessage({
        type: 'error',
        text: err instanceof Error ? err.message : 'Failed to get recommendations',
      })
    } finally {
      setLoadingRecommendations(false)
    }
  }

  const handleApplyAllRecommendations = () => {
    if (!recommendations || !defaults) return

    const newDefaults = { ...defaults }
    for (const [context, rec] of Object.entries(recommendations)) {
      if (context in newDefaults) {
        newDefaults[context as keyof ModelDefaults] = rec.model
      }
    }
    setDefaults(newDefaults)
  }

  const handleApplyRecommendation = (context: keyof ModelDefaults) => {
    if (!recommendations || !defaults) return
    const rec = recommendations[context]
    if (rec) {
      setDefaults({ ...defaults, [context]: rec.model })
    }
  }

  const hasRecommendationForContext = (context: keyof ModelDefaults): boolean => {
    if (!recommendations || !defaults) return false
    const rec = recommendations[context]
    return rec && rec.model !== defaults[context]
  }

  const hasAnyUnappliedRecommendations = (): boolean => {
    if (!recommendations || !defaults) return false
    return Object.keys(CONTEXT_LABELS).some((ctx) =>
      hasRecommendationForContext(ctx as keyof ModelDefaults)
    )
  }

  if (loading) {
    return (
      <div className="flex-1 p-6">
        <div className="flex items-center justify-center h-64">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-cyan-400"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex-1 p-6 overflow-auto">
      <div className="max-w-3xl mx-auto">
        {/* Header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold text-white mb-2">Settings</h1>
          <p className="text-gray-400">Configure your Jarvis preferences</p>
        </div>

        {/* Message */}
        {message && (
          <div
            className={`mb-6 p-4 rounded-lg ${
              message.type === 'success'
                ? 'bg-green-500/20 border border-green-500/50 text-green-400'
                : 'bg-red-500/20 border border-red-500/50 text-red-400'
            }`}
          >
            {message.text}
          </div>
        )}

        {/* Chat Model Defaults */}
        <div className="magnetic-card p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-white">Chat Model Defaults</h2>
            <button
              onClick={handleGetRecommendations}
              disabled={loadingRecommendations}
              className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-800 disabled:cursor-not-allowed text-white rounded-lg transition-colors text-sm"
            >
              <Sparkles className="w-4 h-4" />
              {loadingRecommendations ? 'Analyzing...' : 'Get AI Recommendations'}
            </button>
          </div>
          <p className="text-sm text-gray-400 mb-6">
            Set the default LLM model for each chat context. You can still override these
            per-session in the chat interface.
          </p>

          <div className="space-y-4">
            {defaults &&
              (Object.keys(CONTEXT_LABELS) as (keyof ModelDefaults)[]).map((context) => {
                const rec = recommendations?.[context]
                const showRecommendation = rec && rec.model !== defaults[context]

                return (
                  <div key={context} className="space-y-1">
                    <div className="flex items-center justify-between">
                      <label className="text-gray-300 font-medium">
                        {CONTEXT_LABELS[context]}
                      </label>
                      <div className="flex items-center gap-2">
                        <select
                          value={defaults[context]}
                          onChange={(e) => handleModelChange(context, e.target.value)}
                          className="bg-[#1a1a2e] text-white border border-gray-600 rounded-lg px-4 py-2 min-w-[200px] focus:outline-none focus:border-cyan-400"
                        >
                          {models.map((model) => (
                            <option key={model.name} value={model.name}>
                              {model.name}
                            </option>
                          ))}
                        </select>
                        {showRecommendation && (
                          <button
                            onClick={() => handleApplyRecommendation(context)}
                            className="p-2 bg-purple-600/20 hover:bg-purple-600/40 text-purple-400 rounded-lg transition-colors"
                            title={`Apply recommendation: ${rec.model}`}
                          >
                            <Check className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    </div>
                    {showRecommendation && (
                      <div className="flex items-center gap-2 ml-0 text-sm">
                        <Sparkles className="w-3 h-3 text-purple-400" />
                        <span className="text-purple-400">
                          Recommended: <span className="font-medium">{rec.model}</span>
                        </span>
                        <span className="text-gray-500">- {rec.reason}</span>
                      </div>
                    )}
                  </div>
                )
              })}
          </div>

          {/* Actions */}
          <div className="flex items-center justify-between mt-8 pt-6 border-t border-gray-700">
            <div>
              {hasAnyUnappliedRecommendations() && (
                <button
                  onClick={handleApplyAllRecommendations}
                  className="flex items-center gap-2 px-4 py-2 bg-purple-600/20 hover:bg-purple-600/40 text-purple-400 rounded-lg transition-colors text-sm"
                >
                  <Sparkles className="w-4 h-4" />
                  Apply All Recommendations
                </button>
              )}
            </div>
            <div className="flex items-center gap-4">
              <button
                onClick={handleReset}
                disabled={!hasChanges() || saving}
                className="px-4 py-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
              >
                Reset
              </button>
              <button
                onClick={handleSave}
                disabled={!hasChanges() || saving}
                className="magnetic-button-primary px-6 py-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>
        </div>

        {/* Additional Settings Placeholder */}
        <div className="magnetic-card p-6 mt-6 opacity-50">
          <h2 className="text-lg font-semibold text-white mb-2">Additional Settings</h2>
          <p className="text-sm text-gray-400">
            More settings coming soon...
          </p>
        </div>
      </div>
    </div>
  )
}
