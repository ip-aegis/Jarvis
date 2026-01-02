import { useState, useEffect } from 'react'
import { ChevronDown } from 'lucide-react'
import ChatPanel from '../components/chat/ChatPanel'

const API_URL = import.meta.env.VITE_API_URL || ''

interface Model {
  name: string
  size: number
  parameter_size: string
  quantization: string
}

export default function Chat() {
  const [sessionId] = useState(() => `chat-${Date.now()}`)
  const [models, setModels] = useState<Model[]>([])
  const [selectedModel, setSelectedModel] = useState<string>('')
  const [isLoadingModels, setIsLoadingModels] = useState(true)

  useEffect(() => {
    const fetchModels = async () => {
      try {
        const response = await fetch(`${API_URL}/api/chat/models`)
        if (response.ok) {
          const data = await response.json()
          setModels(data.models)
          if (data.models.length > 0) {
            // Default to first model (usually the larger one)
            setSelectedModel(data.models[0].name)
          }
        }
      } catch (error) {
        console.error('Failed to fetch models:', error)
      } finally {
        setIsLoadingModels(false)
      }
    }
    fetchModels()
  }, [])

  const formatSize = (bytes: number): string => {
    const gb = bytes / (1024 * 1024 * 1024)
    return `${gb.toFixed(1)}GB`
  }

  return (
    <div className="h-full flex flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Chat</h1>
          <p className="text-surface-300 mt-1">General AI assistant with lab context</p>
        </div>

        {/* Model Selector */}
        <div className="flex items-center gap-2">
          <span className="text-sm text-surface-400">Model:</span>
          <div className="relative">
            <select
              value={selectedModel}
              onChange={(e) => setSelectedModel(e.target.value)}
              disabled={isLoadingModels || models.length === 0}
              className="appearance-none bg-surface-700 border border-surface-600 rounded-magnetic px-3 py-1.5 pr-8 text-sm text-white focus:outline-none focus:border-primary disabled:opacity-50"
            >
              {isLoadingModels ? (
                <option>Loading...</option>
              ) : models.length === 0 ? (
                <option>No models available</option>
              ) : (
                models.map((model) => (
                  <option key={model.name} value={model.name}>
                    {model.name} ({model.parameter_size || formatSize(model.size)})
                  </option>
                ))
              )}
            </select>
            <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-4 h-4 text-surface-400 pointer-events-none" />
          </div>
        </div>
      </div>

      <div className="flex-1 min-h-0">
        <ChatPanel
          sessionId={sessionId}
          context="general"
          placeholder="Ask me anything about the lab, servers, or projects..."
          model={selectedModel}
        />
      </div>
    </div>
  )
}
