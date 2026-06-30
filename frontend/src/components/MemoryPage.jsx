import { useEffect, useState } from 'react'

const CATEGORIES = ['semantic', 'episodic', 'working']
const CAT_COLORS = { semantic: 'var(--accent-primary)', episodic: 'var(--accent-tertiary)', working: 'var(--accent-warn)' }
const CAT_ICONS = { semantic: '🧬', episodic: '📖', working: '⚙️' }

export default function MemoryPage() {
  const [memories, setMemories] = useState([])
  const [filter, setFilter] = useState('all')
  const [newKey, setNewKey] = useState('')
  const [newVal, setNewVal] = useState('')
  const [newCat, setNewCat] = useState('semantic')

  const fetchMemory = async () => {
    const r = await fetch('/api/memory')
    if (r.ok) setMemories(await r.json())
  }

  useEffect(() => { fetchMemory() }, [])

  const handleAdd = async () => {
    if (!newKey || !newVal) return
    await fetch('/api/memory/update', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ category: newCat, key: newKey, value: newVal }),
    })
    setNewKey(''); setNewVal('')
    fetchMemory()
  }

  const handleDelete = async (id) => {
    await fetch(`/api/memory/${id}`, { method: 'DELETE' })
    fetchMemory()
  }

  const filtered = filter === 'all' ? memories : memories.filter(m => m.category === filter)

  return (
    <div className="page">
      <h1 className="page-title">🧠 <span>Agent Memory</span></h1>

      {/* Category tabs */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {['all', ...CATEGORIES].map(c => (
          <button key={c} className={`model-chip ${filter === c ? 'active' : ''}`} onClick={() => setFilter(c)}>
            {c === 'all' ? '📋 All' : `${CAT_ICONS[c]} ${c}`}
          </button>
        ))}
      </div>

      {/* Add memory form */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-md)', padding: 16, marginBottom: 24 }}>
        <div style={{ fontWeight: 600, fontSize: '0.85rem', marginBottom: 12, color: 'var(--text-secondary)' }}>➕ Add Memory Entry</div>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <select value={newCat} onChange={e => setNewCat(e.target.value)}
            style={{ background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '8px 10px', color: 'var(--text-primary)', fontSize: '0.82rem', outline: 'none' }}>
            {CATEGORIES.map(c => <option key={c}>{c}</option>)}
          </select>
          <input placeholder="Key" value={newKey} onChange={e => setNewKey(e.target.value)}
            style={{ flex: 1, minWidth: 140, background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', color: 'var(--text-primary)', fontSize: '0.82rem', outline: 'none' }} />
          <input placeholder="Value" value={newVal} onChange={e => setNewVal(e.target.value)}
            style={{ flex: 2, minWidth: 200, background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', color: 'var(--text-primary)', fontSize: '0.82rem', outline: 'none' }} />
          <button onClick={handleAdd}
            style={{ padding: '8px 16px', background: 'linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600, fontSize: '0.85rem' }}>
            Save
          </button>
        </div>
      </div>

      {/* Memory list grouped by category */}
      {CATEGORIES.filter(c => filter === 'all' || filter === c).map(cat => {
        const catMemories = filtered.filter(m => m.category === cat)
        if (!catMemories.length) return null
        return (
          <div className="memory-section" key={cat}>
            <div className="section-title" style={{ color: CAT_COLORS[cat] }}>
              {CAT_ICONS[cat]} {cat.charAt(0).toUpperCase() + cat.slice(1)} Memory
              <span style={{ color: 'var(--text-muted)', fontWeight: 400, marginLeft: 8, fontSize: '0.8rem' }}>({catMemories.length})</span>
            </div>
            {catMemories.map(m => (
              <div className="memory-card" key={m.id}>
                <span className="memory-key">{m.key}</span>
                <span className="memory-value">{m.value}</span>
                <span style={{ color: 'var(--text-muted)', fontSize: '0.72rem', flexShrink: 0 }}>
                  {new Date(m.updated_at).toLocaleDateString()}
                </span>
                <button className="btn-icon" onClick={() => handleDelete(m.id)}>🗑</button>
              </div>
            ))}
          </div>
        )
      })}

      {filtered.length === 0 && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 60 }}>
          No memory entries yet. Start chatting to build up agent memory.
        </div>
      )}
    </div>
  )
}
