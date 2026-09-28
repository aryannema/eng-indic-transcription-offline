import { useState, useEffect, useCallback } from 'react'

interface HistoryItem {
  id: number
  created_at: string
  engine: string
  language: string
  duration_s: number | null
  meta: {
    filename: string
    text: string
    translated_text?: string
    target_lang?: string
    latency_stt_ms?: number
    latency_trans_ms?: number
    scratch_files?: string[]
  }
}

interface Props {
  token: string
}

export default function HistoryPanel({ token }: Props) {
  const [items, setItems]         = useState<HistoryItem[]>([])
  const [total, setTotal]         = useState(0)
  const [loading, setLoading]     = useState(false)
  const [clearing, setClearing]   = useState(false)
  const [expanded, setExpanded]   = useState<number | null>(null)

  const headers = { Authorization: `Bearer ${token}` }

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch('/v1/history?limit=50&offset=0', { headers })
      if (!res.ok) return
      const data = await res.json()
      setItems(data.items)
      setTotal(data.total)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => { load() }, [load])

  const deleteOne = async (id: number) => {
    await fetch(`/v1/history/${id}`, { method: 'DELETE', headers })
    setItems(prev => prev.filter(i => i.id !== id))
    setTotal(prev => prev - 1)
  }

  const clearAll = async () => {
    if (!confirm(`Delete all ${total} transcription(s) and their files?`)) return
    setClearing(true)
    try {
      await fetch('/v1/history', { method: 'DELETE', headers })
      setItems([])
      setTotal(0)
    } finally {
      setClearing(false)
    }
  }

  const fmt = (iso: string) =>
    new Date(iso).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' })

  const engineBadge = (engine: string) =>
    engine === 'indiconformer-600m'
      ? 'bg-blue-900/40 text-blue-300 border-blue-700/40'
      : 'bg-amber-900/40 text-amber-300 border-amber-700/40'

  return (
    <div className="flex flex-col gap-4">
      {/* Header row */}
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-white">
          History
          {total > 0 && (
            <span className="ml-2 text-xs text-[#666] font-normal">{total} record{total !== 1 ? 's' : ''}</span>
          )}
        </h2>
        <div className="flex gap-2">
          <button
            onClick={load}
            className="text-xs text-[#666] hover:text-white px-2 py-1 rounded border
                       border-[#1a1c23] hover:border-[#333] transition-colors"
          >
            Refresh
          </button>
          {total > 0 && (
            <button
              onClick={clearAll} disabled={clearing}
              className="text-xs text-red-400 hover:text-red-300 px-2 py-1 rounded border
                         border-red-900/40 hover:border-red-700/60 transition-colors disabled:opacity-50"
            >
              {clearing ? 'Clearing…' : 'Clear all'}
            </button>
          )}
        </div>
      </div>

      {/* List */}
      {loading && (
        <div className="text-xs text-[#666] text-center py-4">Loading…</div>
      )}

      {!loading && items.length === 0 && (
        <div className="text-xs text-[#555] text-center py-6 border border-dashed border-[#1a1c23] rounded-lg">
          No transcriptions yet
        </div>
      )}

      {items.map(item => (
        <div
          key={item.id}
          className="bg-[#13151c] border border-[#1a1c23] rounded-xl overflow-hidden"
        >
          {/* Row header */}
          <div
            className="flex items-center gap-3 px-4 py-3 cursor-pointer hover:bg-[#0d0f14]
                       transition-colors"
            onClick={() => setExpanded(expanded === item.id ? null : item.id)}
          >
            <span className={`text-[10px] px-1.5 py-0.5 rounded border font-mono ${engineBadge(item.engine)}`}>
              {item.engine === 'indiconformer-600m' ? 'indic' : 'whisper'}
            </span>
            <span className="text-xs text-[#888] uppercase tracking-wide">{item.language}</span>
            <span className="text-xs text-[#555] flex-1 truncate">{item.meta.filename}</span>
            <span className="text-xs text-[#555]">{fmt(item.created_at)}</span>
            <button
              onClick={e => { e.stopPropagation(); deleteOne(item.id) }}
              className="text-xs text-red-500/60 hover:text-red-400 border border-red-900/40
                         hover:border-red-500/60 rounded px-2 py-0.5 transition-colors ml-1"
              title="Delete"
            >
              Delete
            </button>
          </div>

          {/* Expanded content */}
          {expanded === item.id && (
            <div className="border-t border-[#1a1c23] px-4 py-3 flex flex-col gap-2">
              <p className="text-sm text-[#ccc] leading-relaxed whitespace-pre-wrap">
                {item.meta.text}
              </p>
              {item.meta.translated_text && (
                <div className="border-t border-[#1a1c23] pt-2">
                  <span className="text-[10px] text-[#666] uppercase tracking-wide">
                    → {item.meta.target_lang}
                  </span>
                  <p className="text-sm text-[#aaa] leading-relaxed mt-1 whitespace-pre-wrap">
                    {item.meta.translated_text}
                  </p>
                </div>
              )}
              <div className="flex gap-3 text-[10px] text-[#555] pt-1">
                {item.meta.latency_stt_ms != null && (
                  <span>STT {item.meta.latency_stt_ms < 1000
                    ? `${item.meta.latency_stt_ms}ms`
                    : `${(item.meta.latency_stt_ms / 1000).toFixed(1)}s`}
                  </span>
                )}
                {item.meta.latency_trans_ms != null && (
                  <span>Trans {item.meta.latency_trans_ms < 1000
                    ? `${item.meta.latency_trans_ms}ms`
                    : `${(item.meta.latency_trans_ms / 1000).toFixed(1)}s`}
                  </span>
                )}
                {item.meta.scratch_files && item.meta.scratch_files.length > 0 && (
                  <span className="text-[#444]">
                    {item.meta.scratch_files.length} file{item.meta.scratch_files.length > 1 ? 's' : ''} on disk
                  </span>
                )}
              </div>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
