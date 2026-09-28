import { Copy, Check } from 'lucide-react'
import { useState } from 'react'

interface Props {
  text: string
  sourceLang: string
  targetLang: string
  model: string
  latencyMs: number
}

const LANG_LABELS: Record<string, string> = {
  en: 'English', hi: 'Hindi', mr: 'Marathi', bn: 'Bengali',
  ta: 'Tamil', te: 'Telugu', gu: 'Gujarati', kn: 'Kannada',
  ml: 'Malayalam', pa: 'Punjabi', ur: 'Urdu', or: 'Odia',
  as: 'Assamese', ne: 'Nepali',
}

export default function Translation({ text, sourceLang, targetLang, model, latencyMs }: Props) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!text) return null

  const fmtLatency = latencyMs < 1000
    ? `${latencyMs}ms`
    : `${(latencyMs / 1000).toFixed(1)}s`

  return (
    <div className="fade-in mt-3 bg-[#12141a] border border-[#2a2d3a] rounded-xl overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2d3a]">
        <div className="flex items-center gap-3 text-xs text-[#666]">
          <span className="text-amber-400 font-semibold uppercase tracking-wide">Translation</span>
          <span className="bg-[#0b0c10] px-2 py-0.5 rounded text-[#888]">
            {LANG_LABELS[sourceLang] ?? sourceLang} → {LANG_LABELS[targetLang] ?? targetLang}
          </span>
          <span className="bg-[#0b0c10] px-2 py-0.5 rounded text-[#888]">{model}</span>
          <span className="bg-[#0b0c10] px-2 py-0.5 rounded text-amber-400/70">{fmtLatency}</span>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg
                     bg-[#0b0c10] border border-[#2a2d3a] text-[#c5c6c7]
                     hover:border-amber-400/50 hover:text-amber-400 transition-colors"
        >
          {copied ? <Check className="w-3.5 h-3.5 text-green-400" /> : <Copy className="w-3.5 h-3.5" />}
          {copied ? 'Copied' : 'Copy'}
        </button>
      </div>
      <div className="p-5">
        <p className="text-[#c5c6c7] leading-relaxed whitespace-pre-wrap text-sm sm:text-base">
          {text}
        </p>
      </div>
    </div>
  )
}
