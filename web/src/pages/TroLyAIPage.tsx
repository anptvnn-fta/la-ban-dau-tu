import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, Sparkles, MessageSquare, Wrench, Check, Square } from 'lucide-react'
import { agentApi } from '@/api/agent'
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
  const sessionRef = useRef<string | undefined>(undefined)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, busy])

  useEffect(() => () => abortRef.current?.abort(), [])

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
            if (evt.session_id) sessionRef.current = String(evt.session_id)
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
    }
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/15 text-primary">
          <Sparkles className="h-5 w-5" />
        </span>
        <h1 className="font-heading text-xl font-bold text-foreground">{VI.chat.title}</h1>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto rounded-2xl border border-border bg-card/40 p-4">
        {messages.length === 0 && !busy ? (
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
  )
}
