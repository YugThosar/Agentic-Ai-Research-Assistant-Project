import { useState, useEffect, useRef, useCallback } from 'react'

const MODELS = [
  { provider: 'gemini', model: 'gemini-2.5-flash', label: '✦ Gemini 2.5 Flash' },
  { provider: 'gemini', model: 'gemini-2.5-pro', label: '✦ Gemini 2.5 Pro' },
  { provider: 'openai', model: 'gpt-4o-mini', label: '⬡ GPT-4o Mini' },
  { provider: 'ollama', model: 'llama3', label: '🦙 Llama3 (Local)' },
]

function AgentStepsPanel({ steps }) {
  const [open, setOpen] = useState(true)
  if (!steps.length) return null
  return (
    <div className="agent-steps">
      <div className="agent-steps-header" onClick={() => setOpen(o => !o)}>
        <span>🤖 Agent Pipeline</span>
        <span style={{ marginLeft: 'auto', fontSize: '0.7rem' }}>{open ? '▲ collapse' : '▼ expand'}</span>
      </div>
      {open && steps.map((s, i) => (
        <div className="agent-step-item" key={i}>
          <span className={`step-badge step-${s.type}`}>{s.type}</span>
          <div className="step-content">{s.text}</div>
        </div>
      ))}
    </div>
  )
}

function ConfidenceBar({ confidence }) {
  if (confidence == null) return null
  const pct = Math.round(confidence * 100)
  const color = confidence >= 0.8 ? 'var(--accent-success)' : confidence >= 0.6 ? 'var(--accent-warn)' : 'var(--accent-error)'
  return (
    <div className="confidence-bar">
      <span>Confidence:</span>
      <div className="conf-track">
        <div className="conf-fill" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ color, fontWeight: 600 }}>{pct}%</span>
    </div>
  )
}

function CitationsPanel({ citations }) {
  if (!citations?.length) return null
  return (
    <div className="citations-list">
      <div style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>📌 Citations</div>
      {citations.map((c, i) => (
        <div className="citation-item" key={i}>
          <div className="citation-source">{c.source} · Page {c.page}</div>
          {c.content && <div className="citation-content">{c.content}</div>}
        </div>
      ))}
    </div>
  )
}

function Message({ msg }) {
  return (
    <div className={`message-row ${msg.role} animate-fade-in`}>
      <div className={`message-avatar ${msg.role === 'user' ? 'user-av' : 'ai-av'}`}>
        {msg.role === 'user' ? '👤' : '⚡'}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="message-bubble">
          {msg.role === 'assistant' && msg.streaming ? (
            <span>{msg.content}<span className="typing-indicator" style={{ display: 'inline-flex', marginLeft: 4 }}><span/><span/><span/></span></span>
          ) : msg.content}
        </div>
        {msg.agentSteps && <AgentStepsPanel steps={msg.agentSteps} />}
        {msg.confidence != null && <ConfidenceBar confidence={msg.confidence} />}
        {msg.citations && <CitationsPanel citations={msg.citations} />}
      </div>
    </div>
  )
}

export default function ChatPage({ conversationId, onConversationCreated }) {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isStreaming, setIsStreaming] = useState(false)
  const [selectedModel, setSelectedModel] = useState(0)
  const messagesEndRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (conversationId) {
      fetch(`/api/conversations/${conversationId}`)
        .then(r => r.json())
        .then(conv => {
          if (conv.messages) {
            setMessages(conv.messages.map(m => ({
              role: m.role, content: m.content,
              confidence: m.confidence_score, citations: [],
            })))
          }
        }).catch(() => {})
    } else {
      setMessages([])
    }
  }, [conversationId])

  const sendMessage = useCallback(async () => {
    if (!input.trim() || isStreaming) return
    const query = input.trim()
    setInput('')
    setIsStreaming(true)

    const userMsg = { role: 'user', content: query }
    const aiMsg = { role: 'assistant', content: '', streaming: true, agentSteps: [], confidence: null, citations: [] }
    setMessages(prev => [...prev, userMsg, aiMsg])

    const model = MODELS[selectedModel]

    try {
      const resp = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          conversation_id: conversationId || undefined,
          query,
          model_provider: model.provider,
          model_name: model.model,
          stream: true,
        }),
      })

      const reader = resp.body.getReader()
      const decoder = new TextDecoder()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const lines = decoder.decode(value).split('\n')
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            const { type, data } = event

            setMessages(prev => {
              const updated = [...prev]
              const last = { ...updated[updated.length - 1] }

              if (type === 'token') {
                last.content = (last.content || '') + (data.text || '')
              } else if (type === 'metadata') {
                last.confidence = data.confidence
                last.citations = data.citations || []
                last.streaming = false
                if (data.conversation_id && onConversationCreated) {
                  onConversationCreated(data.conversation_id)
                }
              } else if (type === 'done') {
                last.streaming = false
              } else if (['planner', 'retriever', 'reasoner', 'critic', 'refinement', 'status'].includes(type)) {
                const stepText = type === 'planner'
                  ? `Type: ${data.plan?.query_type} | Subqueries: ${data.plan?.subqueries?.length ?? 0}`
                  : type === 'retriever'
                  ? `Found ${data.count ?? 0} chunks`
                  : type === 'reasoner'
                  ? (data.reasoning_steps?.slice(0, 120) || 'Reasoning complete')
                  : type === 'critic'
                  ? `Confidence: ${Math.round((data.confidence ?? 0) * 100)}% | Issues: ${data.issues?.length ?? 0}`
                  : type === 'refinement'
                  ? `Ran ${data.loops} loops → final confidence ${Math.round((data.final_confidence ?? 0) * 100)}%`
                  : data.message || ''
                last.agentSteps = [...(last.agentSteps || []), { type, text: stepText }]
              }

              updated[updated.length - 1] = last
              return updated
            })
          } catch {}
        }
      }
    } catch (err) {
      setMessages(prev => {
        const updated = [...prev]
        updated[updated.length - 1] = { role: 'assistant', content: `Error: ${err.message}`, streaming: false }
        return updated
      })
    } finally {
      setIsStreaming(false)
    }
  }, [input, isStreaming, conversationId, selectedModel, onConversationCreated])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  return (
    <div className="chat-layout">
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="chat-empty">
            <div className="empty-icon">⚡</div>
            <h3>Ask anything about your documents</h3>
            <p style={{ maxWidth: 400, fontSize: '0.85rem' }}>
              Upload PDFs, Word docs, research papers, and more. The multi-agent system will retrieve, reason, critique, and refine answers with citations.
            </p>
          </div>
        )}
        {messages.map((msg, i) => <Message key={i} msg={msg} />)}
        <div ref={messagesEndRef} />
      </div>

      <div className="chat-input-area">
        <div className="model-selector">
          {MODELS.map((m, i) => (
            <button key={i} className={`model-chip ${i === selectedModel ? 'active' : ''}`} onClick={() => setSelectedModel(i)}>
              {m.label}
            </button>
          ))}
        </div>
        <div className="input-row">
          <textarea
            ref={textareaRef}
            className="chat-textarea"
            placeholder="Ask a question across your knowledge base..."
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
          />
          <button className="btn-send" onClick={sendMessage} disabled={isStreaming || !input.trim()}>
            {isStreaming ? <div className="spinner" /> : '↑'}
          </button>
        </div>
      </div>
    </div>
  )
}
