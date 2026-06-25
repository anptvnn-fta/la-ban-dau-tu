import { useEffect, useRef, useState } from 'react'
import { Send, Loader2, Sparkles, MessageSquare } from 'lucide-react'
import { agentApi } from '@/api/agent'
import { ReportMarkdown } from '@/components/report/ReportMarkdown'
import { VI } from '@/strings/vi'
import { cn } from '@/lib/utils'

interface Msg {
  role: 'user' | 'assistant'
  content: string
}

export default function TroLyAIPage() {
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages, loading])

  const send = async () => {
    const text = input.trim()
    if (!text || loading) return
    setMessages((m) => [...m, { role: 'user', content: text }])
    setInput('')
    setLoading(true)
    try {
      const res = await agentApi.chat({ message: text })
      setMessages((m) => [...m, { role: 'assistant', content: res.content || VI.errors.generic }])
    } catch {
      setMessages((m) => [...m, { role: 'assistant', content: VI.errors.network }])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-[calc(100vh-3rem)] flex-col">
      <div className="mb-3 flex items-center gap-2">
        <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary/15 text-primary">
          <Sparkles className="h-5 w-5" />
        </span>
        <div>
          <h1 className="font-heading text-xl font-bold text-foreground">{VI.chat.title}</h1>
        </div>
      </div>

      <div ref={scrollRef} className="flex-1 space-y-4 overflow-y-auto rounded-2xl border border-border bg-card/40 p-4">
        {messages.length === 0 && !loading ? (
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
                m.role === 'user'
                  ? 'bg-primary text-primary-foreground'
                  : 'border border-border bg-card text-foreground',
              )}
            >
              {m.role === 'assistant' ? <ReportMarkdown content={m.content} /> : <p className="text-sm leading-6">{m.content}</p>}
            </div>
          </div>
        ))}

        {loading ? (
          <div className="flex justify-start">
            <div className="flex items-center gap-2 rounded-2xl border border-border bg-card px-4 py-2.5 text-sm text-muted-foreground">
              <Loader2 className="h-4 w-4 animate-spin" /> {VI.chat.thinking}
            </div>
          </div>
        ) : null}
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
          className="h-12 flex-1 rounded-xl border border-input bg-card px-4 text-[15px] text-foreground placeholder:text-muted-foreground focus-visible:border-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
        <button
          type="button"
          onClick={() => void send()}
          disabled={loading || !input.trim()}
          className="inline-flex h-12 items-center gap-2 rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          {VI.chat.send}
        </button>
      </div>
    </div>
  )
}
