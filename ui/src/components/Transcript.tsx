import { Copy, Check } from 'lucide-react'
import { useState } from 'react'

interface Props {
  text: string
  engine: string
  language: string
  filename: string
  latencyMs: number
}

export default function Transcript({ text, engine, language, filename, latencyMs }: Props) {
  const [copied, setCopied] = useState(false)

  function copy() {
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  if (!text) return null

  return (
    <div className="fade-in mt-6 bg-[#1a1c23] border border-[#2a2d3a] rounded-xl overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-[#2a2d3a]">
        <div className="flex items-center gap-3 text-xs text-[#666]">
          <span className="text-amber-400 font-semibold uppercase tracking-wide">Transcript</span>
          <span className="bg-[#0b0c10] px-2 py-0.5 rounded text-[#888]">{engine}</span>
          <span className="bg-[#0b0c10] px-2 py-0.5 rounded text-[#888]">lang: {language}</span>
          <span className="bg-[#0b0c10] px-2 py-0.5 rounded text-amber-400/70">{latencyMs < 1000 ? `${latencyMs}ms` : `${(latencyMs / 1000).toFixed(1)}s`}</span>
          {filename && <span className="hidden sm:inline text-[#555] truncate max-w-[200px]">{filename}</span>}
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

      {/* Text */}
      <div className="p-5">
        <p className="text-[#c5c6c7] leading-relaxed whitespace-pre-wrap text-sm sm:text-base">
          {text}
        </p>
      </div>
    </div>
  )
}
