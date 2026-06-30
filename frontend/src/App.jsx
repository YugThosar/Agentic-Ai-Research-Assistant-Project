import { useState, useEffect } from 'react'
import './index.css'
import ChatPage from './components/ChatPage'
import DocumentsPage from './components/DocumentsPage'
import DashboardPage from './components/DashboardPage'
import GraphPage from './components/GraphPage'
import MemoryPage from './components/MemoryPage'
import EvalPage from './components/EvalPage'

const NAV_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: '⬡' },
  { id: 'chat', label: 'Knowledge Chat', icon: '💬' },
  { id: 'documents', label: 'Documents', icon: '📄' },
  { id: 'graph', label: 'Knowledge Graph', icon: '🕸️' },
  { id: 'memory', label: 'Agent Memory', icon: '🧠' },
  { id: 'eval', label: 'Evaluation', icon: '📊' },
]

export default function App() {
  const [page, setPage] = useState('dashboard')
  const [conversations, setConversations] = useState([])
  const [activeChatId, setActiveChatId] = useState(null)
  const [stats, setStats] = useState(null)

  useEffect(() => {
    fetchConversations()
    fetchStats()
  }, [])

  const fetchConversations = async () => {
    try {
      const r = await fetch('/api/conversations')
      if (r.ok) setConversations(await r.json())
    } catch {}
  }

  const fetchStats = async () => {
    try {
      const r = await fetch('/api/dashboard/stats')
      if (r.ok) setStats(await r.json())
    } catch {}
  }

  const handleNewChat = () => {
    setActiveChatId(null)
    setPage('chat')
  }

  return (
    <div className="app-shell">
      {/* Topbar */}
      <header className="topbar">
        <div className="topbar-brand">
          <div className="brand-icon">⚡</div>
          <span>APKS</span>
          <span style={{ color: 'var(--text-muted)', fontWeight: 400, fontSize: '0.85rem' }}>
            — Agentic Personal Knowledge System
          </span>
        </div>
        <div className="topbar-meta">
          {stats && (
            <>
              <span>📄 {stats.documents?.total ?? 0} docs</span>
              <span>💬 {stats.conversations?.total ?? 0} chats</span>
              <span>🕸 {stats.knowledge_graph?.nodes ?? 0} entities</span>
            </>
          )}
          <div className="pulse-dot" style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--accent-success)', animation: 'pulse-dot 1.2s ease infinite' }} />
          <span style={{ color: 'var(--accent-success)', fontSize: '0.75rem' }}>API Online</span>
        </div>
      </header>

      {/* Sidebar */}
      <nav className="sidebar">
        <div className="nav-section-label">Navigation</div>
        {NAV_ITEMS.map(item => (
          <button
            key={item.id}
            className={`nav-item ${page === item.id ? 'active' : ''}`}
            onClick={() => setPage(item.id)}
          >
            <span className="nav-icon">{item.icon}</span>
            {item.label}
          </button>
        ))}

        <div className="nav-section-label" style={{ marginTop: 12 }}>Conversations</div>
        <button className="btn-new-chat" onClick={handleNewChat}>
          <span>＋</span> New Chat
        </button>
        <div className="sidebar-conversations">
          {conversations.map(conv => (
            <button
              key={conv.id}
              className={`conv-item ${activeChatId === conv.id ? 'active' : ''}`}
              onClick={() => { setActiveChatId(conv.id); setPage('chat') }}
            >
              {conv.title || 'Untitled'}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className="main-content">
        {page === 'dashboard' && <DashboardPage stats={stats} onRefresh={() => { fetchStats(); fetchConversations() }} />}
        {page === 'chat' && (
          <ChatPage
            conversationId={activeChatId}
            onConversationCreated={(id) => { setActiveChatId(id); fetchConversations() }}
          />
        )}
        {page === 'documents' && <DocumentsPage onUpload={() => { fetchStats() }} />}
        {page === 'graph' && <GraphPage />}
        {page === 'memory' && <MemoryPage />}
        {page === 'eval' && <EvalPage />}
      </main>
    </div>
  )
}
