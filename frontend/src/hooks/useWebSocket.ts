import { useState, useEffect, useCallback, useRef } from 'react'

interface MetricUpdate {
  type: string
  server_id: number
  hostname: string
  cpu_usage: number | null
  memory_percent: number | null
  disk_percent: number | null
  gpu_utilization: number | null
  gpu_temperature: number | null
  timestamp: string
}

interface UseWebSocketOptions {
  serverIds?: number[]
  onMessage?: (data: MetricUpdate) => void
}

const MAX_RECONNECT_ATTEMPTS = 10
const BASE_RECONNECT_DELAY = 1000 // 1 second
const MAX_RECONNECT_DELAY = 30000 // 30 seconds

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const [connected, setConnected] = useState(false)
  const [metrics, setMetrics] = useState<Record<number, MetricUpdate>>({})
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const reconnectAttemptsRef = useRef(0)

  const connect = useCallback(() => {
    // Don't connect if we're already connecting or connected
    if (wsRef.current && wsRef.current.readyState === WebSocket.CONNECTING) {
      return
    }

    // Determine WebSocket URL based on current protocol
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const wsUrl = `${protocol}//${window.location.host}/api/monitoring/ws`

    try {
      const ws = new WebSocket(wsUrl)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setConnected(true)
        // Reset reconnect attempts on successful connection
        reconnectAttemptsRef.current = 0
        // Subscribe to specific servers if provided
        if (options.serverIds && options.serverIds.length > 0) {
          ws.send(JSON.stringify({
            action: 'subscribe',
            server_ids: options.serverIds,
          }))
        }
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as MetricUpdate
          if (data.type === 'metric') {
            setMetrics((prev) => ({
              ...prev,
              [data.server_id]: data,
            }))
            options.onMessage?.(data)
          }
        } catch (e) {
          // Silently ignore parse errors
        }
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setConnected(false)
        wsRef.current = null
        // Reconnect with exponential backoff
        if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          const delay = Math.min(
            BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
            MAX_RECONNECT_DELAY
          )
          console.log(`Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`)
          reconnectAttemptsRef.current++
          reconnectTimeoutRef.current = setTimeout(() => {
            connect()
          }, delay)
        } else {
          console.log('Max reconnect attempts reached, giving up')
        }
      }

      ws.onerror = () => {
        // Silently handle errors - onclose will be called after
        setConnected(false)
      }
    } catch (e) {
      console.log('Failed to connect to WebSocket')
      setConnected(false)
      // Retry connection with exponential backoff
      if (reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
        const delay = Math.min(
          BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttemptsRef.current),
          MAX_RECONNECT_DELAY
        )
        console.log(`Retrying in ${delay}ms (attempt ${reconnectAttemptsRef.current + 1}/${MAX_RECONNECT_ATTEMPTS})`)
        reconnectAttemptsRef.current++
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, delay)
      } else {
        console.log('Max reconnect attempts reached, giving up')
      }
    }
  }, [options.serverIds, options.onMessage])

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current)
      reconnectTimeoutRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    reconnectAttemptsRef.current = 0
    setConnected(false)
  }, [])

  const reconnect = useCallback(() => {
    disconnect()
    reconnectAttemptsRef.current = 0
    connect()
  }, [connect, disconnect])

  const subscribe = useCallback((serverIds: number[]) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        action: 'subscribe',
        server_ids: serverIds,
      }))
    }
  }, [])

  useEffect(() => {
    connect()
    return () => {
      disconnect()
    }
  }, [])

  // Re-subscribe when serverIds change
  useEffect(() => {
    if (connected && options.serverIds) {
      subscribe(options.serverIds)
    }
  }, [connected, options.serverIds, subscribe])

  return {
    connected,
    metrics,
    subscribe,
    disconnect,
    reconnect,
  }
}
