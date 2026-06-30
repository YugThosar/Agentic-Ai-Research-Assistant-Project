import { useEffect, useState } from 'react'

const FILE_ICONS = { pdf: '📕', docx: '📘', doc: '📘', pptx: '📙', ppt: '📙', xlsx: '📗', xls: '📗', csv: '📊', txt: '📄', md: '📝', markdown: '📝' }
const fmt = (bytes) => bytes > 1e6 ? `${(bytes/1e6).toFixed(1)} MB` : `${(bytes/1e3).toFixed(0)} KB`

export default function DocumentsPage({ onUpload }) {
  const [docs, setDocs] = useState([])
  const [dragging, setDragging] = useState(false)
  const [uploading, setUploading] = useState(false)
  const [strategy, setStrategy] = useState('recursive')

  const fetchDocs = async () => {
    const r = await fetch('/api/documents')
    if (r.ok) setDocs(await r.json())
  }

  useEffect(() => { fetchDocs(); const t = setInterval(fetchDocs, 5000); return () => clearInterval(t) }, [])

  const handleFiles = async (files) => {
    setUploading(true)
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      fd.append('chunking_strategy', strategy)
      await fetch('/api/documents/upload', { method: 'POST', body: fd }).catch(() => {})
    }
    setUploading(false)
    fetchDocs()
    onUpload?.()
  }

  const handleDelete = async (id) => {
    if (!confirm('Delete this document and all associated data?')) return
    await fetch(`/api/documents/${id}`, { method: 'DELETE' })
    fetchDocs()
    onUpload?.()
  }

  return (
    <div className="page">
      <h1 className="page-title">📄 <span>Document Library</span></h1>

      {/* Chunking strategy selector */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <span style={{ color: 'var(--text-muted)', fontSize: '0.8rem', alignSelf: 'center' }}>Chunking:</span>
        {['fixed', 'recursive', 'semantic'].map(s => (
          <button key={s} className={`model-chip ${strategy === s ? 'active' : ''}`} onClick={() => setStrategy(s)}>
            {s}
          </button>
        ))}
      </div>

      {/* Drop Zone */}
      <div
        className={`upload-zone ${dragging ? 'dragging' : ''}`}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={e => { e.preventDefault(); setDragging(false); handleFiles([...e.dataTransfer.files]) }}
        onClick={() => document.getElementById('file-input').click()}
      >
        <div className="upload-icon">⬆</div>
        <p><strong>Click to upload</strong> or drag & drop files here</p>
        <p style={{ fontSize: '0.78rem', marginTop: 4, color: 'var(--text-muted)' }}>
          Supports PDF, DOCX, PPTX, XLSX, CSV, MD, TXT
        </p>
        {uploading && <p style={{ color: 'var(--accent-primary)', marginTop: 8 }}>⏳ Uploading & processing...</p>}
      </div>
      <input id="file-input" type="file" multiple hidden accept=".pdf,.docx,.doc,.pptx,.ppt,.xlsx,.xls,.csv,.txt,.md,.markdown"
        onChange={e => handleFiles([...e.target.files])} />

      {/* Documents Table */}
      {docs.length > 0 && (
        <table className="docs-table">
          <thead>
            <tr>
              <th>Document</th>
              <th>Type</th>
              <th>Size</th>
              <th>Status</th>
              <th>Uploaded</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {docs.map(doc => (
              <tr key={doc.id}>
                <td>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                    <span style={{ fontSize: 20 }}>{FILE_ICONS[doc.file_type] || '📄'}</span>
                    <span style={{ fontWeight: 500 }}>{doc.filename}</span>
                  </div>
                </td>
                <td style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>.{doc.file_type}</td>
                <td style={{ color: 'var(--text-muted)' }}>{fmt(doc.file_size)}</td>
                <td><span className={`badge badge-${doc.status}`}>{doc.status}</span></td>
                <td style={{ color: 'var(--text-muted)', fontSize: '0.78rem' }}>{new Date(doc.upload_date).toLocaleDateString()}</td>
                <td><button className="btn-icon" onClick={() => handleDelete(doc.id)} title="Delete">🗑</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {docs.length === 0 && !uploading && (
        <div style={{ textAlign: 'center', color: 'var(--text-muted)', marginTop: 40, fontSize: '0.9rem' }}>
          No documents yet. Upload your first document above.
        </div>
      )}
    </div>
  )
}
