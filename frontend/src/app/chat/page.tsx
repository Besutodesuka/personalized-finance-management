'use client'
import { useState, useRef, useEffect } from 'react'
import { api } from '@/lib/api'

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
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  actions?: Action[]
}

const ACTION_LABELS: Record<string, string> = {
  add_expense: '+ Expense added',
  add_subscription: '+ Subscription added',
  update_expense: '✎ Expense updated',
  update_subscription: '✎ Subscription updated',
  list_expenses: '🔍 Looked up expenses',
  list_subscriptions: '🔍 Looked up subscriptions',
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
      : null

  return (
    <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">
      {label}{detail ? `: ${detail}` : ''}
    </span>
  )
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content:
        "Hi! I'm your finance assistant. Tell me about expenses (\"I spent 150 on coffee at Relax\") or ask about your spending. I can add and update records directly. (Requires vLLM running with --profile ai)",
    },
  ])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const send = async () => {
    const msg = input.trim()
    if (!msg || loading) return
    setInput('')

    const userMsg: Message = { role: 'user', content: msg }
    setMessages((prev) => [...prev, userMsg])
    setLoading(true)

    // Build history excluding the initial welcome message and the new user message
    const history = messages
      .slice(1) // skip welcome
      .map((m) => ({ role: m.role, content: m.content }))

    try {
      const res = await api.post<{ reply: string; actions: Action[]; ok: boolean }>('/chat', {
        message: msg,
        history,
      })
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: res.reply, actions: res.actions ?? [] },
      ])
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Connection error. Is vLLM running?' },
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-3rem)] space-y-4">
      <div className="flex items-center gap-3">
        <h1 className="text-2xl font-bold">AI Assistant</h1>
        <span className="badge">Pathumma 8B via Ollama</span>
        <span className="badge" style={{ background: '#e0f2fe', color: '#0369a1' }}>Tool Calling</span>
      </div>

      <div className="flex-1 card overflow-y-auto space-y-4 min-h-0">
        {messages.map((m, i) => (
          <div key={i} className={`flex flex-col ${m.role === 'user' ? 'items-end' : 'items-start'}`}>
            {m.actions && m.actions.length > 0 && (
              <div className="flex flex-wrap gap-1 mb-1 max-w-[80%]">
                {m.actions.map((a, j) => (
                  <ActionChip key={j} action={a} />
                ))}
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-xl px-4 py-2.5 text-sm leading-relaxed ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-gray-100 text-gray-900'
              }`}
            >
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex flex-col items-start gap-1">
            <span className="text-xs text-gray-400">thinking…</span>
            <div className="bg-gray-100 text-gray-500 rounded-xl px-4 py-2.5 text-sm">…</div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="flex gap-2">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && send()}
          placeholder='Try: "I spent 200 on coffee" or "Add Netflix 299/mo on day 1 to Relax"'
          className="form-input flex-1"
          disabled={loading}
        />
        <button onClick={send} disabled={loading || !input.trim()} className="btn btn-primary">
          Send
        </button>
      </div>
    </div>
  )
}
