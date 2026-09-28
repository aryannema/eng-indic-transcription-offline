import { Download } from 'lucide-react'

interface Props {
  text: string
  filename: string
}

// ~150 words per minute → 0.4 seconds per word
const WORDS_PER_SECOND = 150 / 60

function toSrtTime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 1000)
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')},${String(ms).padStart(3,'0')}`
}

function buildSrt(text: string): string {
  // Split on sentence boundaries
  const sentences = text.match(/[^.!?]+[.!?]+|\s*[^.!?]+$/g) ?? [text]
  let cursor = 0
  return sentences
    .map((s, i) => {
      const clean = s.trim()
      if (!clean) return ''
      const wordCount = clean.split(/\s+/).length
      const duration = wordCount / WORDS_PER_SECOND
      const start = cursor
      const end = cursor + duration
      cursor = end + 0.5 // 0.5s gap between sentences
      return `${i + 1}\n${toSrtTime(start)} --> ${toSrtTime(end)}\n${clean}\n`
    })
    .filter(Boolean)
    .join('\n')
}

function buildVtt(text: string): string {
  const sentences = text.match(/[^.!?]+[.!?]+|\s*[^.!?]+$/g) ?? [text]
  let cursor = 0
  const cues = sentences
    .map((s) => {
      const clean = s.trim()
      if (!clean) return ''
      const wordCount = clean.split(/\s+/).length
      const duration = wordCount / WORDS_PER_SECOND
      const start = cursor
      const end = cursor + duration
      cursor = end + 0.5
      // VTT uses . not , for ms
      const fmt = (sec: number) => toSrtTime(sec).replace(',', '.')
      return `${fmt(start)} --> ${fmt(end)}\n${clean}\n`
    })
    .filter(Boolean)
    .join('\n')
  return `WEBVTT\n\n${cues}`
}

function download(content: string, name: string, mime: string) {
  const url = URL.createObjectURL(new Blob([content], { type: mime }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

export default function ExportBar({ text, filename }: Props) {
  if (!text) return null

  const base = filename.replace(/\.[^.]+$/, '') || 'transcript'

  return (
    <div className="flex flex-wrap items-center gap-2 mt-3">
      <span className="text-xs text-[#666] mr-1 flex items-center gap-1">
        <Download className="w-3.5 h-3.5" /> Export:
      </span>

      <button
        onClick={() => download(text, `${base}.txt`, 'text/plain')}
        className="text-xs px-3 py-1.5 rounded-lg bg-[#1a1c23] border border-[#2a2d3a]
                   text-[#c5c6c7] hover:border-amber-400/50 hover:text-amber-400 transition-colors"
      >
        TXT
      </button>

      <button
        onClick={() => download(buildSrt(text), `${base}.srt`, 'text/plain')}
        className="text-xs px-3 py-1.5 rounded-lg bg-[#1a1c23] border border-[#2a2d3a]
                   text-[#c5c6c7] hover:border-amber-400/50 hover:text-amber-400 transition-colors"
      >
        SRT
      </button>

      <button
        onClick={() => download(buildVtt(text), `${base}.vtt`, 'text/vtt')}
        className="text-xs px-3 py-1.5 rounded-lg bg-[#1a1c23] border border-[#2a2d3a]
                   text-[#c5c6c7] hover:border-amber-400/50 hover:text-amber-400 transition-colors"
      >
        VTT
      </button>
    </div>
  )
}
