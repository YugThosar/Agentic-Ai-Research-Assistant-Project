import { useEffect, useState } from 'react'

export default function DashboardPage({ stats, onRefresh }) {
  useEffect(() => { onRefresh?.() }, [])

  const s = stats

  const STAT_CARDS = [
    { icon: '📄', label: 'Documents', value: s?.documents?.total ?? '—', color: 'var(--accent-primary)' },
    { icon: '📦', label: 'Chunks', value: s?.chunks?.total ?? '—', color: 'var(--accent-secondary)' },
    { icon: '💬', label: 'Conversations', value: s?.conversations?.total ?? '—', color: 'var(--accent-tertiary)' },
    { icon: '🤖', label: 'AI Answers', value: s?.conversations?.total_answers ?? '—', color: 'var(--accent-success)' },
    { icon: '🕸️', label: 'KG Nodes', value: s?.knowledge_graph?.nodes ?? '—', color: 'var(--accent-warn)' },
    { icon: '🔗', label: 'KG Edges', value: s?.knowledge_graph?.edges ?? '—', color: 'var(--accent-error)' },
  ]

  return (
    <div className="page">
      <h1 className="page-title">⬡ <span>Dashboard</span></h1>

      <div className="stat-grid">
        {STAT_CARDS.map(card => (
          <div className="stat-card" key={card.label}>
            <div className="stat-icon">{card.icon}</div>
            <div className="stat-label">{card.label}</div>
            <div className="stat-value" style={{ color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {s?.documents?.by_status && (
        <>
          <div className="section-title">Document Status Breakdown</div>
          <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap', marginBottom: 28 }}>
            {Object.entries(s.documents.by_status).map(([status, count]) => (
              <div key={status} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '10px 18px', textAlign: 'center' }}>
                <span className={`badge badge-${status}`}>{status}</span>
                <div style={{ fontSize: '1.4rem', fontWeight: 700, marginTop: 4 }}>{count}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {s?.documents?.recent?.length > 0 && (
        <>
          <div className="section-title">Recent Documents</div>
          <div className="doc-grid">
            {s.documents.recent.map(doc => (
              <div className="doc-card" key={doc.id}>
                <div className="doc-icon">📄</div>
                <div className="doc-info">
                  <div className="doc-name" title={doc.filename}>{doc.filename}</div>
                  <div className="doc-meta"><span className={`badge badge-${doc.status}`}>{doc.status}</span></div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {!s && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 60 }}>
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          <p>Connecting to backend...</p>
          <p style={{ fontSize: '0.8rem', marginTop: 6 }}>Make sure the FastAPI server is running on port 8000</p>
        </div>
      )}
    </div>
  )
}
