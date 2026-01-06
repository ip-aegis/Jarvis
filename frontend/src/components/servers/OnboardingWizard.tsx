import { useState } from 'react'
import { X, Check, Loader2, Server, Key, Download, Search, Bot } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import type { Server as ServerType, OnboardingResult } from '../../types'

interface OnboardingWizardProps {
  onClose: () => void
  onComplete: (server: ServerType) => void
}

type Step = 'credentials' | 'connecting' | 'keys' | 'agent' | 'review' | 'complete'

const API_URL = import.meta.env.VITE_API_URL || ''

export default function OnboardingWizard({ onClose, onComplete }: OnboardingWizardProps) {
  const [step, setStep] = useState<Step>('credentials')
  const [error, setError] = useState<string | null>(null)
  const [serverInfo, setServerInfo] = useState<OnboardingResult | null>(null)

  const [credentials, setCredentials] = useState({
    hostname: '',
    ip_address: '',
    username: '',
    password: '',
    port: 22,
  })

  const steps = [
    { id: 'credentials', label: 'Credentials', icon: Server },
    { id: 'connecting', label: 'Connect', icon: Loader2 },
    { id: 'keys', label: 'SSH Keys', icon: Key },
    { id: 'agent', label: 'Agent', icon: Download },
    { id: 'review', label: 'Review', icon: Search },
  ]

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)
    setStep('connecting')

    try {
      const response = await fetch(`${API_URL}/api/servers/onboard`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          credentials,
          install_agent: true,
        }),
      })

      if (!response.ok) {
        const data = await response.json()
        throw new Error(data.detail || 'Failed to connect')
      }

      const data = await response.json()
      setServerInfo(data)
      setStep('complete')
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unexpected error occurred'
      setError(errorMessage)
      setStep('credentials')
    }
  }

  const handleComplete = () => {
    if (!serverInfo) return

    const server: ServerType = {
      id: serverInfo.server_id,
      hostname: credentials.hostname,
      ip_address: credentials.ip_address,
      status: 'online',
      os_info: serverInfo.system_info?.os,
      cpu_info: serverInfo.system_info?.cpu,
      cpu_cores: serverInfo.system_info?.cpu_cores,
      memory_total: serverInfo.system_info?.memory_total,
      disk_total: serverInfo.system_info?.disk_total,
      gpu_info: serverInfo.system_info?.gpu,
      agent_installed: serverInfo.agent_installed,
    }
    onComplete(server)
  }

  const currentStepIndex = steps.findIndex((s) => s.id === step)

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      role="dialog"
      aria-modal="true"
      aria-labelledby="wizard-title"
    >
      <div
        className="bg-surface-700 rounded-magnetic w-full max-w-xl m-4 border border-surface-600"
        role="document"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-surface-600">
          <h2 id="wizard-title" className="text-lg font-medium text-white">Add New Server</h2>
          <button
            onClick={onClose}
            className="text-surface-400 hover:text-white"
            aria-label="Close dialog"
          >
            <X className="w-5 h-5" aria-hidden="true" />
          </button>
        </div>

        {/* Progress */}
        <div className="px-4 py-3 border-b border-surface-600">
          <div className="flex items-center gap-2">
            {steps.map((s, i) => (
              <div key={s.id} className="flex items-center">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center text-sm
                    ${
                      i < currentStepIndex
                        ? 'bg-success text-white'
                        : i === currentStepIndex
                        ? 'bg-primary text-white'
                        : 'bg-surface-600 text-surface-400'
                    }`}
                >
                  {i < currentStepIndex ? (
                    <Check className="w-4 h-4" />
                  ) : step === 'connecting' && s.id === 'connecting' ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <s.icon className="w-4 h-4" />
                  )}
                </div>
                {i < steps.length - 1 && (
                  <div
                    className={`w-8 h-0.5 ${
                      i < currentStepIndex ? 'bg-success' : 'bg-surface-600'
                    }`}
                  />
                )}
              </div>
            ))}
          </div>
        </div>

        {/* Content */}
        <div className="p-4">
          {step === 'credentials' && (
            <form onSubmit={handleSubmit} className="space-y-4">
              {error && (
                <div className="p-3 bg-error/20 border border-error rounded-magnetic text-error text-sm">
                  {error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-surface-300 mb-1">Hostname</label>
                  <input
                    type="text"
                    value={credentials.hostname}
                    onChange={(e) =>
                      setCredentials({ ...credentials, hostname: e.target.value })
                    }
                    className="magnetic-input"
                    placeholder="server-01"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-300 mb-1">IP Address</label>
                  <input
                    type="text"
                    value={credentials.ip_address}
                    onChange={(e) =>
                      setCredentials({ ...credentials, ip_address: e.target.value })
                    }
                    className="magnetic-input"
                    placeholder="10.10.20.x"
                    required
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-surface-300 mb-1">Username</label>
                  <input
                    type="text"
                    value={credentials.username}
                    onChange={(e) =>
                      setCredentials({ ...credentials, username: e.target.value })
                    }
                    className="magnetic-input"
                    placeholder="root"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm text-surface-300 mb-1">Port</label>
                  <input
                    type="number"
                    value={credentials.port}
                    onChange={(e) =>
                      setCredentials({ ...credentials, port: parseInt(e.target.value) })
                    }
                    className="magnetic-input"
                    required
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm text-surface-300 mb-1">Password</label>
                <input
                  type="password"
                  value={credentials.password}
                  onChange={(e) =>
                    setCredentials({ ...credentials, password: e.target.value })
                  }
                  className="magnetic-input"
                  placeholder="••••••••"
                  required
                />
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button type="button" onClick={onClose} className="magnetic-button-secondary">
                  Cancel
                </button>
                <button type="submit" className="magnetic-button-primary">
                  Connect
                </button>
              </div>
            </form>
          )}

          {step === 'connecting' && (
            <div className="text-center py-8">
              <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
              <p className="text-white font-medium">Connecting to server...</p>
              <p className="text-surface-400 text-sm mt-1">
                Exchanging SSH keys and installing agent
              </p>
            </div>
          )}

          {step === 'complete' && serverInfo && (
            <div className="space-y-4">
              <div className="text-center py-4">
                <div className="w-12 h-12 bg-success rounded-full flex items-center justify-center mx-auto mb-3">
                  <Check className="w-6 h-6 text-white" />
                </div>
                <p className="text-white font-medium">Server Added Successfully</p>
              </div>

              <div className="bg-surface-800 rounded-magnetic p-4 space-y-2">
                <div className="flex justify-between">
                  <span className="text-surface-400">Hostname</span>
                  <span className="text-white">{serverInfo.system_info?.hostname}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-400">OS</span>
                  <span className="text-white text-sm truncate max-w-xs">
                    {serverInfo.system_info?.os?.split('\n')[0]}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-400">CPU</span>
                  <span className="text-white">{serverInfo.system_info?.cpu}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-400">Memory</span>
                  <span className="text-white">{serverInfo.system_info?.memory_total}</span>
                </div>
                {serverInfo.system_info?.gpu && (
                  <div className="flex justify-between">
                    <span className="text-surface-400">GPU</span>
                    <span className="text-primary">{serverInfo.system_info?.gpu}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span className="text-surface-400">SSH Keys</span>
                  <span className={serverInfo.key_exchanged ? 'text-success' : 'text-error'}>
                    {serverInfo.key_exchanged ? 'Exchanged' : 'Failed'}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-surface-400">Agent</span>
                  <span className={serverInfo.agent_installed ? 'text-success' : 'text-error'}>
                    {serverInfo.agent_installed ? 'Installed' : 'Failed'}
                  </span>
                </div>
              </div>

              {/* LLM Analysis Section */}
              {serverInfo.llm_analysis && (
                <div className="bg-surface-800 rounded-magnetic p-4">
                  <div className="flex items-center gap-2 mb-3">
                    <Bot className="w-5 h-5 text-primary" />
                    <h3 className="text-white font-medium">AI Analysis</h3>
                  </div>
                  <div className="prose prose-invert prose-sm max-w-none text-surface-300">
                    <ReactMarkdown>{serverInfo.llm_analysis}</ReactMarkdown>
                  </div>
                </div>
              )}

              <div className="flex justify-end">
                <button onClick={handleComplete} className="magnetic-button-primary">
                  Done
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
