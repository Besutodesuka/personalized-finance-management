'use client'
import { useState, useRef, useEffect, useCallback } from 'react'
import { api, BASE } from '@/lib/api'
import Markdown from '@/components/Markdown'

interface Action {
  ok: boolean
  action?: string
  error?: string
  description?: string
  amount?: number
  wallet?: string
  date?: string
  name?: string
  active?: boolean
  id?: string
  budget?: number
  total?: number
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  thinking?: string
  actions?: Action[]
}

interface Session {
  id: string
  title: string
  updated_at: string
  message_count: number
}

const ACTION_LABELS: Record<string, string> = {
  add_expense: '+ Expense added',
  add_subscription: '+ Subscription added',
  update_expense: '✎ Expense updated',
  update_subscription: '✎ Subscription updated',
  list_expenses: '🔍 Looked up expenses',
  list_subscriptions: '🔍 Looked up subscriptions',
  set_wallet_budget: '💰 Budget updated',
  set_total_budget: '💰 Total budget set',
}

function ActionChip({ action }: { action: Action }) {
  if (!action.ok) {
    return (
      <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700">
        ✗ {action.error}
      </span>
    )
  }
  const label = action.action ? ACTION_LABELS[action.action] ?? action.action : 'Done'
  const detail =
    action.action === 'add_expense' || action.action === 'update_expense'
      ? `${action.description} • ${action.amount?.toLocaleString('th-TH')} THB`
      : action.action === 'add_subscription' || action.action === 'update_subscription'
      ? `${action.name} • ${action.amount?.toLocaleString('th-TH')} THB/mo${action.active === false ? ' (paused)' : ''}`
      : action.action === 'set_wallet_budget'
      ? `${action.wallet} • ${action.budget?.toLocaleString('th-TH')} THB`
      : action.action === 'set_total_budget'
      ? `${action.total?.toLocaleString('th-TH')} THB total`
      : null

  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
      {label}{detail ? `: ${detail}` : ''}
    </span>
  )
}

function ThinkingBlock({ text, live }: { text: string; live?: boolean }) {
  const [open, setOpen] = useState(live ?? false)
  if (!text) return null
  return (
    <div className="max-w-[80%] mb-1">
      <button
        onClick={() => setOpen((o) => !o)}
        className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
      >
        {open ? '▾' : '▸'} {live ? 'Thinking…' : 'Thought process'}
      </button>
      {open && (
        <pre className="mt-1 text-xs text-gray-500 bg-gray-50 border border-gray-200 rounded-lg px-3 py-2 whitespace-pre-wrap font-sans leading-relaxed">
          {text}
        </pre>
      )}
    </div>
  )
}

const WELCOME: Message = {
  role: 'assistant',
  content:
    "Hi! I'm your finance assistant. Tell me about expenses (\"I spent 150 on coffee at Relax\") or ask about your spending. I can add and update records directly. (Requires vLLM running with --profile ai)",
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME])
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [model, setModel] = useState('Ollama')
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  const loadSessions = useCallback(async () => {
    try {
      const res = await api.get<{ sessions: Session[] }>('/chat/sessions')
      setSessions(res.sessions)
      return res.sessions
    } catch {
      return []
    }
  }, [])

  const openSession = useCallback(async (id: string) => {
    setSessionId(id)
    try {
      const res = await api.get<{ messages: Message[] }>(`/chat/sessions/${id}/messages`)
      setMessages([WELCOME, ...res.messages])
    } catch {
      setMessages([WELCOME])
    }
  }, [])

  // Model name from backend (env-driven) + most recent session on mount.
  useEffect(() => {
    api.get<{ model: string }>('/health').then((h) => h.model && setModel(h.model)).catch(() => {})
    loadSessions().then((list) => {
      if (list.length > 0) openSession(list[0].id)
    })
  }, [loadSessions, openSession])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const newChat = () => {
    if (loading) return
    setSessionId(null)
    setMessages([WELCOME])
  }

  const deleteSession = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await api.del(`/chat/sessions/${id}`)
    } catch {}
    const list = await loadSessions()
    if (id === sessionId) {
      if (list.length > 0) openSession(list[0].id)
      else newChat()
    }
  }

  const send = async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')
    setMessages((prev) => [...prev, { role: 'user', content: msg }])
    // Placeholder assistant message we stream into.
    setMessages((prev) => [...prev, { role: 'assistant', content: '', thinking: '', actions: [] }])
    setLoading(true)

    const patchLast = (fn: (m: Message) => Message) =>
      setMessages((prev) => prev.map((m, i) => (i === prev.length - 1 ? fn(m) : m)))

    try {
      const res = await fetch(`${BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: sessionId }),
      })
      if (!res.body) throw new Error('no stream')

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''
      let newSession = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() ?? ''
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          const ev = JSON.parse(line.slice(5).trim())
          if (ev.type === 'session') {
            if (ev.session_id !== sessionId) {
              newSession = true
              setSessionId(ev.session_id)
            }
          } else if (ev.type === 'thinking') {
            patchLast((m) => ({ ...m, thinking: (m.thinking ?? '') + ev.delta }))
          } else if (ev.type === 'content') {
            patchLast((m) => ({ ...m, content: m.content + ev.delta }))
          } else if (ev.type === 'action') {
            patchLast((m) => ({ ...m, actions: [...(m.actions ?? []), ev.data] }))
          } else if (ev.type === 'done') {
            patchLast((m) => ({ ...m, content: ev.reply || m.content, actions: ev.actions ?? m.actions }))
          } else if (ev.type === 'error') {
            patchLast((m) => ({ ...m, content: ev.message }))
          }
        }
      }
      if (newSession) loadSessions()
      else loadSessions() // refresh titles / ordering
    } catch {
      patchLast((m) => ({ ...m, content: 'Connection error. Is vLLM running?' }))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-4">
      {/* History sidebar */}
      <div className="w-56 shrink-0 card flex flex-col overflow-hidden">
        <button onClick={newChat} disabled={loading} className="btn btn-primary text-sm mb-2">
          + New Chat
        </button>
        <div className="text-xs font-semibold text-gray-400 px-1 mb-1">History</div>
        <div className="flex-1 overflow-y-auto space-y-1">
          {sessions.length === 0 && (
            <div className="text-xs text-gray-400 px-1">No past chats yet.</div>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              onClick={() => !loading && openSession(s.id)}
              className={`group flex items-center gap-1 px-2 py-1.5 rounded-lg cursor-pointer text-sm ${
                s.id === sessionId ? 'bg-indigo-100 text-indigo-800' : 'hover:bg-gray-100'
              }`}
            >
              <span className="flex-1 truncate">{s.title || 'New chat'}</span>
              <button
                onClick={(e) => deleteSession(s.id, e)}
                className="opacity-0 group-hover:opacity-100 text-gray-400 hover:text-red-500 text-xs"
                title="Delete chat"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Conversation */}
      <div className="flex-1 flex flex-col space-y-4 min-w-0">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold">AI Assistant</h1>
          <span className="badge">{model}</span>
          <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>Tool Calling</span>
        </div>

        <div className="flex-1 card overflow-y-auto space-y-4 min-h-0">
          {messages.map((m, i) => {
            const streamingLast = loading && i === messages.length - 1
            return (
              <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
                {m.role === 'assistant' && m.thinking ? (
                  <ThinkingBlock text={m.thinking} live={streamingLast} />
                ) : null}
                {m.actions && m.actions.length > 0 && (
                  <div className="flex flex-wrap gap-1 mb-1 max-w-[80%]">
                    {m.actions.map((a, j) => (
                      <ActionChip key={j} action={a} />
                    ))}
                  </div>
                )}
                {(m.content || !streamingLast) && (
                  <div
                    className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                      m.role === 'user'
                        ? 'bg-indigo-600 text-white whitespace-pre-wrap'
                        : 'bg-gray-100 text-gray-900'
                    }`}
                  >
                    {m.role === 'assistant'
                      ? m.content
                        ? <Markdown>{m.content}</Markdown>
                        : (streamingLast ? '…' : '')
                      : (m.content || (streamingLast ? '…' : ''))}
                  </div>
                )}
                {streamingLast && !m.content && !m.thinking && (
                  <span className="text-xs text-gray-400">thinking…</span>
                )}
              </div>
            )
          })}
          <div ref={bottomRef} />
        </div>

        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && send()}
            placeholder='Try: "I spent 200 on coffee" or "Set my budget to 36000"'
            className="form-input flex-1"
            disabled={loading}
          />
          <button onClick={send} disabled={loading || !input.trim()} className="btn btn-primary">
            Send
          </button>
        </div>
      </div>
    </div>
  )
}
