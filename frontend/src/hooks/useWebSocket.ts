import { useEffect, useRef, useCallback, useState } from 'react'
import { WEBSOCKET_RECONNECT_DELAY, WEBSOCKET_MAX_RETRIES } from '@utils/constants'

interface UseWebSocketOptions {
  onMessage?: (data: unknown) => void
  onError?: (error: Event) => void
  onOpen?: () => void
  onClose?: () => void
  reconnect?: boolean
}

export const useWebSocket = (
  url: string,
  options: UseWebSocketOptions = {}
) => {
  const { onMessage, onError, onOpen, onClose, reconnect = true } = options
  const wsRef = useRef<WebSocket | null>(null)
  const retriesRef = useRef(0)
  const [isConnected, setIsConnected] = useState(false)

  const connect = useCallback(() => {
    try {
      const ws = new WebSocket(url)

      ws.onopen = () => {
        console.log('WebSocket connected')
        setIsConnected(true)
        retriesRef.current = 0
        onOpen?.()
      }

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)
          onMessage?.(data)
        } catch (err) {
          // Log error but don't pass raw string to onMessage
          // Callbacks expect parsed JSON objects, passing raw strings causes crashes
          console.error('Failed to parse WebSocket message:', err, 'Raw data:', event.data)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        onError?.(error)
      }

      ws.onclose = () => {
        console.log('WebSocket closed')
        setIsConnected(false)
        onClose?.()

        // Attempt to reconnect
        if (reconnect && retriesRef.current < WEBSOCKET_MAX_RETRIES) {
          retriesRef.current += 1
          setTimeout(() => {
            connect()
          }, WEBSOCKET_RECONNECT_DELAY)
        }
      }

      wsRef.current = ws
    } catch (err) {
      console.error('Failed to create WebSocket:', err)
    }
  }, [url, onMessage, onError, onOpen, onClose, reconnect])

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }, [])

  const send = useCallback((data: unknown) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data))
    }
  }, [])

  useEffect(() => {
    connect()

    return () => {
      disconnect()
    }
  }, [connect, disconnect])

  return {
    isConnected,
    send,
    disconnect
  }
}
