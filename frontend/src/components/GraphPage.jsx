import { useEffect, useRef, useState } from 'react'

// Simple force-directed graph using SVG
function ForceGraph({ nodes, edges }) {
  const svgRef = useRef(null)
  const [positions, setPositions] = useState({})
  const [dragging, setDragging] = useState(null)

  useEffect(() => {
    if (!nodes.length) return
    // Random initial placement
    const pos = {}
    nodes.forEach((n, i) => {
      const angle = (i / nodes.length) * 2 * Math.PI
      const r = Math.min(300, 80 + nodes.length * 8)
      pos[n.id] = { x: 500 + r * Math.cos(angle), y: 300 + r * Math.sin(angle) }
    })
    setPositions(pos)
  }, [nodes])

  const TYPE_COLORS = {
    Entity: 'var(--accent-primary)',
    Document: 'var(--accent-success)',
    Concept: 'var(--accent-secondary)',
  }

  return (
    <svg ref={svgRef} className="graph-svg">
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="8" refY="3" orient="auto">
          <path d="M0,0 L0,6 L8,3 z" fill="rgba(99,102,241,0.6)" />
        </marker>
      </defs>
      {/* Edges */}
      {edges.map((e, i) => {
        const s = positions[e.source], t = positions[e.target]
        if (!s || !t) return null
        const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2
        return (
          <g key={i}>
            <line x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="rgba(99,102,241,0.3)" strokeWidth={1.5} markerEnd="url(#arrow)" />
            <text x={mx} y={my} fill="var(--text-muted)" fontSize={10} textAnchor="middle" dy={-4}>{e.label}</text>
          </g>
        )
      })}
      {/* Nodes */}
      {nodes.map(n => {
        const p = positions[n.id]
        if (!p) return null
        const color = TYPE_COLORS[n.type] || 'var(--accent-tertiary)'
        return (
          <g key={n.id}
            onMouseDown={e => setDragging({ id: n.id, ox: e.clientX - p.x, oy: e.clientY - p.y })}
          >
            <circle cx={p.x} cy={p.y} r={22} fill={`rgba(99,102,241,0.15)`} stroke={color} strokeWidth={2} />
            <text x={p.x} y={p.y + 4} fill={color} fontSize={9} textAnchor="middle" fontWeight={600}>
              {n.label.length > 12 ? n.label.slice(0, 12) + '…' : n.label}
            </text>
          </g>
        )
      })}
    </svg>
  )
}

export default function GraphPage() {
  const [graph, setGraph] = useState({ nodes: [], edges: [] })
  const [search, setSearch] = useState('')
  const [searchResults, setSearchResults] = useState([])

  useEffect(() => {
    fetch('/api/graph').then(r => r.json()).then(setGraph).catch(() => {})
  }, [])

  const handleSearch = async () => {
    if (!search.trim()) return
    const r = await fetch(`/api/graph/search?query=${encodeURIComponent(search)}&limit=20`)
    if (r.ok) {
      const data = await r.json()
      setSearchResults(data.results || [])
    }
  }

  return (
    <div className="graph-page">
      <div>
        <h1 className="page-title">🕸️ <span>Knowledge Graph</span></h1>
        <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
          <input
            style={{ flex: 1, background: 'var(--bg-input)', border: '1px solid var(--border-subtle)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', color: 'var(--text-primary)', fontSize: '0.85rem', outline: 'none' }}
            placeholder="Search entities..."
            value={search}
            onChange={e => setSearch(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && handleSearch()}
          />
          <button onClick={handleSearch} style={{ padding: '8px 16px', background: 'var(--accent-primary)', color: 'white', border: 'none', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontWeight: 600 }}>
            Search
          </button>
          <span style={{ color: 'var(--text-muted)', alignSelf: 'center', fontSize: '0.8rem' }}>
            {graph.nodes.length} nodes · {graph.edges.length} edges
          </span>
        </div>
        {searchResults.length > 0 && (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
            {searchResults.map(r => (
              <span key={r.id} style={{ padding: '3px 10px', background: 'rgba(99,102,241,0.15)', color: 'var(--accent-primary)', borderRadius: 20, fontSize: '0.78rem', fontWeight: 600 }}>
                {r.label} <span style={{ opacity: 0.6 }}>({r.type})</span>
              </span>
            ))}
          </div>
        )}
      </div>

      <div className="graph-container">
        {graph.nodes.length === 0 ? (
          <div className="graph-empty">
            <span style={{ fontSize: 40, opacity: 0.4 }}>🕸️</span>
            <p>No knowledge graph data yet.</p>
            <p style={{ fontSize: '0.8rem' }}>Upload and process documents to build the graph.</p>
          </div>
        ) : (
          <ForceGraph nodes={graph.nodes} edges={graph.edges} />
        )}
      </div>
    </div>
  )
}
