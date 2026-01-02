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

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const [connected, setConnected] = useState(false)
  const [metrics, setMetrics] = useState<Record<number, MetricUpdate>>({})
  const wsRef = useRef<WebSocket | null>(null)
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null)

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
        // Reconnect after 5 seconds
        reconnectTimeoutRef.current = setTimeout(() => {
          connect()
        }, 5000)
      }

      ws.onerror = () => {
        // Silently handle errors - onclose will be called after
        setConnected(false)
      }
    } catch (e) {
      console.log('Failed to connect to WebSocket, retrying...')
      setConnected(false)
      // Retry connection after 5 seconds
      reconnectTimeoutRef.current = setTimeout(() => {
        connect()
      }, 5000)
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
    setConnected(false)
  }, [])

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
  }
}
