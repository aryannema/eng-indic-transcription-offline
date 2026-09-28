import { useState } from 'react'

const TARGETS = [
  { code: 'en', label: 'English' },
  { code: 'hi', label: 'Hindi (हिन्दी)' },
  { code: 'mr', label: 'Marathi (मराठी)' },
  { code: 'bn', label: 'Bengali (বাংলা)' },
  { code: 'ta', label: 'Tamil (தமிழ்)' },
  { code: 'te', label: 'Telugu (తెలుగు)' },
  { code: 'gu', label: 'Gujarati (ગુજરાતી)' },
  { code: 'kn', label: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ml', label: 'Malayalam (മലയാളം)' },
  { code: 'pa', label: 'Punjabi (ਪੰਜਾਬੀ)' },
  { code: 'ur', label: 'Urdu (اردو)' },
  { code: 'or', label: 'Odia (ଓଡ଼ିଆ)' },
  { code: 'as', label: 'Assamese (অসমীয়া)' },
  { code: 'ne', label: 'Nepali (नेपाली)' },
]

interface TranslateResult {
  text: string
  sourceLang: string
  targetLang: string
  model: string
  latencyMs: number
}

interface Props {
  sourceText: string
  sourceLang: string
  token: string
  authHeaders: () => HeadersInit
  onResult: (r: TranslateResult) => void
  onError: (msg: string) => void
}

export default function TranslateBar({ sourceText, sourceLang, token: _token, authHeaders, onResult, onError }: Props) {
  const [target, setTarget]   = useState('')
  const [loading, setLoading] = useState(false)

  const translate = async () => {
    if (!target || !sourceText) return
    setLoading(true)
    try {
      const form = new FormData()
      form.append('text', sourceText)
      form.append('source_lang', sourceLang)
      form.append('target_lang', target)
      const t0  = performance.now()
      const res = await fetch('/v1/translate', { method: 'POST', body: form, headers: authHeaders() })
      const latencyMs = Math.round(performance.now() - t0)
      if (!res.ok) throw new Error(`Translation error ${res.status}`)
      const data = await res.json()
      onResult({
        text: data.translated_text ?? '',
        sourceLang,
        targetLang: target,
        model: data.model ?? 'nllb-200',
        latencyMs,
      })
    } catch (e: unknown) {
      onError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center gap-2 mt-2">
      <span className="text-xs text-[#666] whitespace-nowrap">Translate to:</span>
      <select
        value={target}
        onChange={e => setTarget(e.target.value)}
        disabled={loading}
        className="bg-[#1a1c23] border border-[#2a2d3a] text-[#c5c6c7] text-sm
                   rounded-lg px-3 py-1.5 focus:outline-none focus:ring-1
                   focus:ring-amber-400/50 disabled:opacity-40"
      >
        <option value="">Select language…</option>
        {TARGETS.filter(t => t.code !== sourceLang).map(l => (
          <option key={l.code} value={l.code}>{l.label}</option>
        ))}
      </select>
      <button
        onClick={translate}
        disabled={!target || loading}
        className="text-xs px-3 py-1.5 rounded-lg bg-amber-400 hover:bg-amber-300
                   disabled:opacity-40 disabled:cursor-not-allowed text-black
                   font-semibold transition-colors"
      >
        {loading ? 'Translating…' : 'Translate'}
      </button>
    </div>
  )
}
