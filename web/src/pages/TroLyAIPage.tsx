import { useEffect, useRef, useState, useCallback } from 'react'
import { Send, Loader2, Sparkles, MessageSquare, Wrench, Check, Square, Plus, Trash2 } from 'lucide-react'
import { agentApi, type ChatSessionItem } from '@/api/agent'
import { ReportMarkdown } from '@/components/report/ReportMarkdown'
import { VI } from '@/strings/vi'
import { cn } from '@/lib/utils'

interface Step {
  name: string
  done: boolean
}
interface Msg {
  role: 'user' | 'assistant'
  content: string
  steps?: Step[]
  status?: 'streaming' | 'done' | 'error'
}

export default function TroLyAIPage() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [sessions, setSessions] = useState<ChatSessionItem[]>([])
  const [currentSession, setCurrentSession] = useState<string | null>(null)
  const [loadingSession, setLoadingSession] = useState(false)
  const sessionRef = useRef<string | undefined>(undefined)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  const loadSessions = useCallback(async () => {
    try {
      setSessions(await agentApi.getChatSessions(50))
    } catch {
      /* im lặng — không chặn chat nếu danh sách phiên lỗi */
    }
  }, [])

  useEffect(() => { void loadSessions() }, [loadSessions])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  useEffect(() => () => abortRef.current?.abort(), [])

  const newChat = () => {
    abortRef.current?.abort()
    setBusy(false)
    setMessages([])
    sessionRef.current = undefined
    setCurrentSession(null)
  }

  const openSession = async (id: string) => {
    if (busy) return
    setLoadingSession(true)
    try {
      const msgs = await agentApi.getChatSessionMessages(id)
      setMessages(msgs.map((m) => ({ role: m.role, content: m.content, status: 'done' as const })))
      sessionRef.current = id
      setCurrentSession(id)
    } catch {
      /* im lặng */
    } finally {
      setLoadingSession(false)
    }
  }

  const removeSession = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    try {
      await agentApi.deleteChatSession(id)
      if (currentSession === id) newChat()
      void loadSessions()
    } catch {
      /* im lặng */
    }
  }

  const patchLast = (fn: (m: Msg) => Msg) =>
    setMessages((prev) => {
      const next = [...prev]
      for (let i = next.length - 1; i >= 0; i--) {
        if (next[i].role === 'assistant') {
          next[i] = fn(next[i])
          break
        }
      }
      return next
    })

  const stop = () => {
    abortRef.current?.abort()
    setBusy(false)
    patchLast((m) => ({ ...m, status: 'done' }))
  }

  const send = async () => {
    const text = input.trim()
    if (!text || busy) return
    setInput('')
    setBusy(true)
    setMessages((m) => [
      ...m,
      { role: 'user', content: text },
      { role: 'assistant', content: '', steps: [], status: 'streaming' },
    ])

    const ctrl = new AbortController()
    abortRef.current = ctrl
    try {
      const res = await agentApi.chatStream({ message: text, session_id: sessionRef.current }, { signal: ctrl.signal })
      const reader = res.body?.getReader()
      if (!reader) throw new Error('no stream')
      const dec = new TextDecoder()
      let buf = ''
      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buf += dec.decode(value, { stream: true })
        const parts = buf.split('\n\n')
        buf = parts.pop() || ''
        for (const part of parts) {
          const line = part.trim()
          if (!line.startsWith('data:')) continue
          let evt: Record<string, unknown>
          try {
            evt = JSON.parse(line.slice(5).trim())
          } catch {
            continue
          }
          const type = evt.type as string
          if (type === 'tool_start') {
            const name = String(evt.display_name || evt.tool || 'công cụ')
            patchLast((m) => ({ ...m, steps: [...(m.steps || []), { name, done: false }] }))
          } else if (type === 'tool_done') {
            patchLast((m) => {
              const steps = [...(m.steps || [])]
              for (let i = steps.length - 1; i >= 0; i--) if (!steps[i].done) { steps[i] = { ...steps[i], done: true }; break }
              return { ...m, steps }
            })
          } else if (type === 'done') {
            if (evt.session_id) { sessionRef.current = String(evt.session_id); setCurrentSession(String(evt.session_id)) }
            patchLast((m) => ({ ...m, content: String(evt.content || VI.errors.generic), status: 'done' }))
          } else if (type === 'error') {
            patchLast((m) => ({ ...m, content: String(evt.message || VI.errors.generic), status: 'error' }))
          }
        }
      }
    } catch (e) {
      if (!(e instanceof Error && e.name === 'AbortError')) {
        patchLast((m) => ({ ...m, content: VI.errors.network, status: 'error' }))
      }
    } finally {
      setBusy(false)
      patchLast((m) => (m.status === 'streaming' ? { ...m, status: 'done' } : m))
      // Cập nhật lại danh sách phiên để phiên mới/đang dùng xuất hiện ở sidebar
      void loadSessions()
    }
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] gap-4">
      {/* Sidebar lịch sử trò chuyện */}
      <aside className="hidden w-64 shrink-0 flex-col rounded-2xl border border-border bg-card/40 backdrop-blur-xl md:flex">
        <div className="p-3">
          <button
            type="button"
            onClick={newChat}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary px-3 py-2.5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <Plus className="h-4 w-4" /> {VI.chat.newChat}
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
          <p className="px-2 pb-1 pt-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{VI.chat.sessions}</p>
          {sessions.length === 0 ? (
            <p className="px-2 py-4 text-center text-xs text-muted-foreground">{VI.common.noData}</p>
          ) : (
            sessions.map((s) => (
              <button
                key={s.session_id}
                type="button"
                onClick={() => void openSession(s.session_id)}
                className={cn(
                  'group flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left transition-colors focus-visible:outline-none',
                  currentSession === s.session_id ? 'bg-primary/15 text-primary' : 'text-foreground hover:bg-white/5',
                )}
              >
                <MessageSquare className="h-4 w-4 shrink-0 opacity-60" />
                <span className="min-w-0 flex-1 truncate text-sm">{s.title || 'Cuộc trò chuyện'}</span>
                <span className="shrink-0 text-[11px] text-muted-foreground">{s.message_count}</span>
                <Trash2
                  role="button"
                  aria-label={VI.common.delete}
                  onClick={(e) => void removeSession(e, s.session_id)}
                  className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity hover:text-danger group-hover:opacity-60"
                />
              </button>
            ))
          )}
        </div>
      </aside>

      {/* Khu trò chuyện */}
      <div className="flex min-w-0 flex-1 flex-col">
        <div className="mb-3 flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/15 text-primary shadow-lg shadow-primary/20 ring-1 ring-primary/20">
              <Sparkles className="h-5 w-5" />
            </span>
            <h1 className="font-heading text-xl font-bold text-foreground">{VI.chat.title}</h1>
          </div>
          <button
            type="button"
            onClick={newChat}
            aria-label={VI.chat.newChat}
            className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-border bg-card px-3 text-sm font-medium text-foreground hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring md:hidden"
          >
            <Plus className="h-4 w-4" />
          </button>
        </div>

        <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto rounded-2xl border border-border bg-card/40 p-4">
          {loadingSession ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              <Loader2 className="h-6 w-6 animate-spin" />
            </div>
          ) : messages.length === 0 && !busy ? (
            <div className="flex h-full flex-col items-center justify-center text-center text-muted-foreground">
              <MessageSquare className="mb-3 h-10 w-10 opacity-40" />
              <p className="text-sm">{VI.chat.emptyState}</p>
            </div>
          ) : null}

          {messages.map((m, i) => (
            <div key={i} className={cn('flex', m.role === 'user' ? 'justify-end' : 'justify-start')}>
              <div
                className={cn(
                  'max-w-[85%] rounded-2xl px-4 py-2.5',
                  m.role === 'user' ? 'bg-primary text-primary-foreground' : 'border border-border bg-card text-foreground',
                )}
              >
                {m.role === 'assistant' ? (
                  <>
                    {m.steps && m.steps.length ? (
                      <div className="mb-2 space-y-1">
                        {m.steps.map((s, j) => (
                          <div key={j} className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            {s.done ? <Check className="h-3.5 w-3.5 text-up" /> : <Wrench className="h-3.5 w-3.5 animate-pulse" />}
                            {s.name}
                          </div>
                        ))}
                      </div>
                    ) : null}
                    {m.content ? (
                      <ReportMarkdown content={m.content} />
                    ) : m.status === 'streaming' ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" /> {VI.chat.thinking}
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="text-sm leading-6">{m.content}</p>
                )}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-3 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void send()
              }
            }}
            placeholder={VI.chat.placeholder}
            aria-label={VI.chat.placeholder}
            disabled={busy}
            className="h-12 flex-1 rounded-xl border border-input bg-card px-4 text-[15px] text-foreground placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
          />
          {busy ? (
            <button
              type="button"
              onClick={stop}
              className="inline-flex h-12 items-center gap-2 rounded-xl border border-border bg-card px-5 text-sm font-semibold text-foreground hover:bg-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Square className="h-4 w-4" /> Dừng
            </button>
          ) : (
            <button
              type="button"
              onClick={() => void send()}
              disabled={!input.trim()}
              className="inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <Send className="h-4 w-4" /> {VI.chat.send}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
