// 自研全局单例 WS 客户端（SDD-前端 §wsClient）
// - 统一信封 {v,type,conversation_id,task_id,seq,ts,payload}；业务事件带 seq（去重），ping 不带。
// - 客户端去重：维护 maxSeq；seq<=maxSeq 丢弃；==maxSeq+1 处理推进；>maxSeq+1 缓存 2s 按序补。
// - 心跳：收到 ping 回 pong（不带 seq）；60s 无任何消息判定异常 → 主动重连（指数退避）。
// - 断线重连：重新取 ws-token + REST 拉历史补偿（由上层 messageStore 完成）。

const HEARTBEAT_TIMEOUT = 60000
const REORDER_WAIT = 2000

class WsClient {
  constructor() {
    this.ws = null
    this.conversationId = null
    this.token = null
    this.maxSeq = 0
    this.pending = new Map() // seq -> envelope（乱序缓存）
    this.handlers = new Map() // type -> [fn]
    this.connected = false
    this.reconnecting = false
    this.retry = 0
    this._hbTimer = null
    this._reorderTimer = null
  }

  on(type, fn) {
    if (!this.handlers.has(type)) this.handlers.set(type, [])
    this.handlers.get(type).push(fn)
  }

  off(type, fn) {
    const arr = this.handlers.get(type) || []
    this.handlers.set(type, arr.filter((f) => f !== fn))
  }

  _emit(type, envelope) {
    ;(this.handlers.get(type) || []).forEach((fn) => {
      try { fn(envelope) } catch (e) { console.error('[ws] handler error', type, e) }
    })
  }

  async connect(conversationId, token) {
    this.conversationId = conversationId
    this.token = token
    await this._open()
  }

  _open() {
    return new Promise((resolve, reject) => {
      const url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/api/ws?token=${encodeURIComponent(this.token)}&conversation_id=${encodeURIComponent(this.conversationId)}`
      const ws = new WebSocket(url)
      ws.onopen = () => {
        this.ws = ws
        this.connected = true
        this.reconnecting = false
        this.retry = 0
        this._resetHeartbeat()
        this._emit('connected', {})
        resolve()
      }
      ws.onmessage = (e) => this._onMessage(e)
      ws.onclose = () => {
        this.connected = false
        this._emit('disconnected', {})
        this._scheduleReconnect()
      }
      ws.onerror = (err) => reject(err)
    })
  }

  _onMessage(e) {
    this._resetHeartbeat()
    let env
    try { env = JSON.parse(e.data) } catch { return }
    if (env.type === 'ping') { this._sendRaw('pong'); return }
    if (env.seq === undefined) { this._emit(env.type, env); return }
    if (env.seq <= this.maxSeq) return // 去重
    if (env.seq === this.maxSeq + 1) {
      this._process(env)
    } else {
      this.pending.set(env.seq, env) // 乱序 → 缓存
      if (!this._reorderTimer) {
        this._reorderTimer = setTimeout(() => this._flushPending(), REORDER_WAIT)
      }
    }
  }

  _process(env) {
    this.maxSeq = Math.max(this.maxSeq, env.seq)
    this._emit(env.type, env)
    this._flushPending()
  }

  _flushPending() {
    while (this.pending.has(this.maxSeq + 1)) {
      const env = this.pending.get(this.maxSeq + 1)
      this.pending.delete(this.maxSeq + 1)
      this._process(env)
    }
    if (this.pending.size === 0 && this._reorderTimer) {
      clearTimeout(this._reorderTimer)
      this._reorderTimer = null
    }
  }

  _sendRaw(text) {
    if (this.ws && this.connected) this.ws.send(text)
  }

  _resetHeartbeat() {
    clearTimeout(this._hbTimer)
    this._hbTimer = setTimeout(() => {
      // 60s 无消息 → 判定异常，主动关闭触发重连
      try { this.ws && this.ws.close() } catch {}
    }, HEARTBEAT_TIMEOUT)
  }

  _scheduleReconnect() {
    if (this.reconnecting) return
    this.reconnecting = true
    const delay = Math.min(30000, 1000 * 2 ** this.retry)
    this.retry += 1
    setTimeout(() => {
      this.reconnecting = false
      if (this.token && this.conversationId) {
        this._emit('reconnecting', {})
        this._open().catch(() => this._scheduleReconnect())
      }
    }, delay)
  }

  close() {
    clearTimeout(this._hbTimer)
    clearTimeout(this._reorderTimer)
    this.reconnecting = true // 阻止自动重连
    try { this.ws && this.ws.close() } catch {}
    this.ws = null
    this.connected = false
    this.conversationId = null
    this.token = null
    this.maxSeq = 0
    this.pending.clear()
  }
}

export const wsClient = new WsClient()
