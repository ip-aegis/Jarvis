import { useState, useRef, useEffect } from 'react'
import { Send, Loader2, RotateCcw } from 'lucide-react'
import ReactMarkdown from 'react-markdown'
import { api } from '../../services/api'
import type { ChatContext } from '../../types'

interface Message {
  role: 'user' | 'assistant'
  content: string
}

interface ChatPanelProps {
  sessionId: string
  context: ChatContext
  placeholder?: string
  model?: string
  onModelLoaded?: (model: string) => void
  onNewChat?: () => void  // Callback when user wants a new chat
  onDataChanged?: () => void  // Callback when chat may have modified data (e.g., added contacts)
}

const API_URL = import.meta.env.VITE_API_URL || ''

export default function ChatPanel({ sessionId, context, placeholder, model, onModelLoaded, onNewChat, onDataChanged }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>(() => {
    // Only load persisted messages for work context (for "Learn from Chats" feature)
    if (context === 'work') {
      const stored = sessionStorage.getItem(`chat-${sessionId}`)
      return stored ? JSON.parse(stored) : []
    }
    return []
  })
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [defaultModel, setDefaultModel] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // Persist messages to sessionStorage (only for work context)
  useEffect(() => {
    if (context === 'work' && messages.length > 0) {
      sessionStorage.setItem(`chat-${sessionId}`, JSON.stringify(messages))
    }
  }, [messages, sessionId, context])

  const clearChat = () => {
    // Clear messages from state
    setMessages([])
    // Clear from sessionStorage
    sessionStorage.removeItem(`chat-${sessionId}`)
    // Notify parent if callback provided
    onNewChat?.()
  }

  // Fetch default model for this context if no model prop provided
  useEffect(() => {
    if (!model) {
      api.getModelDefaultForContext(context).then((res) => {
        setDefaultModel(res.model)
        onModelLoaded?.(res.model)
      }).catch((err) => {
        console.error('Failed to fetch default model:', err)
      })
    } else {
      // If model is provided via prop, notify parent
      onModelLoaded?.(model)
    }
  }, [context, model, onModelLoaded])

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = input.trim()
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: userMessage }])
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/chat/message/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: userMessage,
          session_id: sessionId,
          context: context,
          history: messages,
          model: model || defaultModel || undefined,
        }),
      })

      if (!response.ok) throw new Error('Failed to send message')

      const reader = response.body?.getReader()
      const decoder = new TextDecoder()
      let assistantMessage = ''

      setMessages((prev) => [...prev, { role: 'assistant', content: '' }])

      while (reader) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = line.slice(6)
            if (data === '[DONE]') continue

            try {
              const parsed = JSON.parse(data)
              if (parsed.content) {
                assistantMessage += parsed.content
                setMessages((prev) => {
                  const newMessages = [...prev]
                  newMessages[newMessages.length - 1] = {
                    role: 'assistant',
                    content: assistantMessage,
                  }
                  return newMessages
                })
              }
            } catch {
              // Ignore parse errors
            }
          }
        }
      }
    } catch (error) {
      console.error('Chat error:', error)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Sorry, I encountered an error. Please check that the backend is running.',
        },
      ])
    } finally {
      setIsLoading(false)
      // Notify parent that data may have changed (e.g., contacts added via chat)
      onDataChanged?.()
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="h-full flex flex-col bg-surface-700 rounded-magnetic border border-surface-600">
      {/* Header with New Chat button (only show when there are messages) */}
      {messages.length > 0 && (
        <div className="flex items-center justify-end px-3 py-2 border-b border-surface-600">
          <button
            onClick={clearChat}
            className="flex items-center gap-1.5 px-2 py-1 text-xs text-gray-400 hover:text-white hover:bg-surface-600 rounded transition-colors"
            title="Start new conversation"
          >
            <RotateCcw className="w-3 h-3" />
            New Chat
          </button>
        </div>
      )}
      {/* Messages */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-surface-400 py-8">
            <p>Start a conversation with Jarvis</p>
          </div>
        )}
        {messages.map((message, index) => (
          <div
            key={index}
            className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[80%] rounded-magnetic px-4 py-2 ${
                message.role === 'user'
                  ? 'bg-primary text-white'
                  : 'bg-surface-600 text-white'
              }`}
            >
              {message.role === 'assistant' ? (
                <div className="prose prose-invert prose-sm max-w-none">
                  <ReactMarkdown>{message.content}</ReactMarkdown>
                </div>
              ) : (
                <p className="text-sm whitespace-pre-wrap">{message.content}</p>
              )}
            </div>
          </div>
        ))}
        {isLoading && messages[messages.length - 1]?.role === 'user' && (
          <div className="flex justify-start">
            <div className="bg-surface-600 rounded-magnetic px-4 py-2">
              <Loader2 className="w-4 h-4 animate-spin text-primary" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="p-3 border-t border-surface-600">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder || 'Type a message...'}
            rows={4}
            className="flex-1 magnetic-input resize-none"
            disabled={isLoading}
          />
          <button
            onClick={sendMessage}
            disabled={!input.trim() || isLoading}
            className="magnetic-button-primary px-3 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  )
}
