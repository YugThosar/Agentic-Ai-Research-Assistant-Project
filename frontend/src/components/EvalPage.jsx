import { useEffect, useState } from 'react'

function MetricGauge({ label, value }) {
  const pct = Math.round((value || 0) * 100)
  const color = pct >= 80 ? 'var(--accent-success)' : pct >= 60 ? 'var(--accent-warn)' : 'var(--accent-error)'
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: 20, textAlign: 'center' }}>
      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: 8 }}>{label}</div>
      <div style={{ fontSize: '2.2rem', fontWeight: 800, color }}>{pct}%</div>
      <div style={{ height: 5, background: 'var(--bg-elevated)', borderRadius: 10, marginTop: 8, overflow: 'hidden' }}>
        <div style={{ height: '100%', width: `${pct}%`, background: color, borderRadius: 10, transition: 'width 0.6s ease' }} />
      </div>
    </div>
  )
}

export default function EvalPage() {
  const [report, setReport] = useState(null)

  useEffect(() => {
    fetch('/api/evaluation/reports').then(r => r.json()).then(setReport).catch(() => {})
  }, [])

  if (!report) return (
    <div className="page" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <div className="spinner" />
    </div>
  )

  const feedback = report.feedback_stats || {}

  return (
    <div className="page">
      <h1 className="page-title">📊 <span>Evaluation Reports</span></h1>
      <p style={{ color: 'var(--text-secondary)', marginBottom: 28, fontSize: '0.85rem' }}>
        Automated quality metrics computed across {report.total_evaluations} evaluated answers.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(180px, 1fr))', gap: 16, marginBottom: 32 }}>
        <MetricGauge label="Faithfulness" value={report.avg_faithfulness} />
        <MetricGauge label="Groundedness" value={report.avg_groundedness} />
        <MetricGauge label="Relevance" value={report.avg_relevance} />
      </div>

      {Object.keys(feedback).length > 0 && (
        <>
          <div className="section-title">User Feedback</div>
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 28 }}>
            {Object.entries(feedback).map(([key, val]) => (
              <div key={key} style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '12px 20px', textAlign: 'center' }}>
                <div style={{ fontSize: 28 }}>{key === 'thumbs_up' ? '👍' : '👎'}</div>
                <div style={{ fontSize: '1.5rem', fontWeight: 700, marginTop: 4 }}>{val}</div>
                <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', textTransform: 'uppercase' }}>{key.replace('_', ' ')}</div>
              </div>
            ))}
          </div>
        </>
      )}

      {report.total_evaluations === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 60 }}>
          No evaluation data yet. Start chatting to generate quality metrics automatically.
        </div>
      )}

      <div style={{ background: 'var(--bg-card)', borderRadius: 'var(--radius-md)', border: '1px solid var(--border-subtle)', padding: 20, marginTop: 16 }}>
        <div className="section-title">📐 Metric Definitions</div>
        {[
          ['Faithfulness', 'Fraction of answer sentences semantically grounded in retrieved evidence (no hallucinations).'],
          ['Groundedness', 'How well each answer claim maps back to specific document chunks.'],
          ['Relevance', 'Cosine similarity between the user query embedding and the generated answer embedding.'],
        ].map(([name, def]) => (
          <div key={name} style={{ display: 'flex', gap: 12, marginBottom: 10 }}>
            <span style={{ fontWeight: 600, color: 'var(--accent-primary)', minWidth: 120, fontSize: '0.85rem' }}>{name}</span>
            <span style={{ fontSize: '0.82rem', color: 'var(--text-secondary)' }}>{def}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
