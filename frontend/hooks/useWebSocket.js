import { useEffect, useRef, useState, useCallback } from 'react'

const RECONNECT_DELAY = 1000

export function useWebSocket(url) {
  const [connected, setConnected] = useState(false)
  const wsRef = useRef(null)
  const handlersRef = useRef({})
  const reconnectTimer = useRef(null)

  const on = useCallback((type, handler) => {
    handlersRef.current[type] = handler
  }, [])

  useEffect(() => {
    let alive = true

    function connect() {
      if (!alive) return
      const ws = new WebSocket(url)
      wsRef.current = ws

      ws.onopen = () => {
        setConnected(true)
        // Keepalive ping
        const interval = setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send('ping')
        }, 15000)
        ws._pingInterval = interval
      }

      ws.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          const handler = handlersRef.current[msg.type]
          if (handler) handler(msg.data)
        } catch {}
      }

      ws.onclose = () => {
        setConnected(false)
        clearInterval(ws._pingInterval)
        if (alive) {
          reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY)
        }
      }

      ws.onerror = () => ws.close()
    }

    connect()

    return () => {
      alive = false
      clearTimeout(reconnectTimer.current)
      wsRef.current?.close()
    }
  }, [url])

  return { connected, on, ws: wsRef }
}
