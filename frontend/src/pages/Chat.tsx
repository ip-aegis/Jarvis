import { useState, useCallback } from 'react'
import { Bot, Settings } from 'lucide-react'
import { Link } from 'react-router-dom'
import ChatPanel from '../components/chat/ChatPanel'

export default function Chat() {
  const [sessionId] = useState(() => `chat-${Date.now()}`)
  const [currentModel, setCurrentModel] = useState<string | null>(null)

  const handleModelLoaded = useCallback((model: string) => {
    setCurrentModel(model)
  }, [])

  return (
    <div className="h-full flex flex-col">
      <div className="mb-4 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-white">Chat</h1>
          <p className="text-surface-300 mt-1">General AI assistant with lab context</p>
        </div>

        {/* Model Badge */}
        <Link
          to="/settings"
          className="flex items-center gap-2 px-3 py-1.5 bg-surface-700 border border-surface-600 rounded-magnetic text-sm text-surface-300 hover:border-primary hover:text-white transition-colors"
          title="Configure in Settings"
        >
          <Bot className="w-4 h-4" />
          <span>{currentModel || 'Loading...'}</span>
          <Settings className="w-3 h-3 opacity-50" />
        </Link>
      </div>

      <div className="flex-1 min-h-0">
        <ChatPanel
          sessionId={sessionId}
          context="general"
          placeholder="Ask me anything about the lab, servers, or projects..."
          onModelLoaded={handleModelLoaded}
        />
      </div>
    </div>
  )
}
