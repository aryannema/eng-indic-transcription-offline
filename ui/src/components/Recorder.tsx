import { useEffect, useRef, useState } from 'react'
import { Mic, Square } from 'lucide-react'

interface Props {
  onRecording: (f: File) => void
  disabled: boolean
}

export default function Recorder({ onRecording, disabled }: Props) {
  const [recording, setRecording] = useState(false)
  const [seconds, setSeconds]     = useState(0)
  const mediaRef    = useRef<MediaRecorder | null>(null)
  const chunksRef   = useRef<Blob[]>([])
  const timerRef    = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => () => stopAll(), [])

  function stopAll() {
    if (timerRef.current) clearInterval(timerRef.current)
    mediaRef.current?.stop()
  }

  async function toggle() {
    if (recording) {
      stopAll()
      return
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' })
      chunksRef.current = []
      mr.ondataavailable = e => chunksRef.current.push(e.data)
      mr.onstop = () => {
        stream.getTracks().forEach(t => t.stop())
        setRecording(false)
        setSeconds(0)
        if (timerRef.current) clearInterval(timerRef.current)
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' })
        const file = new File([blob], `recording-${Date.now()}.webm`, { type: 'audio/webm' })
        onRecording(file)
      }
      mr.start()
      mediaRef.current = mr
      setRecording(true)
      setSeconds(0)
      timerRef.current = setInterval(() => setSeconds(s => s + 1), 1000)
    } catch {
      alert('Microphone access denied')
    }
  }

  const fmt = (s: number) => `${String(Math.floor(s / 60)).padStart(2,'0')}:${String(s % 60).padStart(2,'0')}`

  return (
    <button
      onClick={toggle}
      disabled={disabled}
      className={`
        flex items-center gap-2 px-5 py-2.5 rounded-lg font-semibold text-sm
        transition-all duration-200
        ${recording
          ? 'bg-red-500/20 border border-red-400 text-red-300 recording-pulse'
          : 'bg-[#1a1c23] border border-[#2a2d3a] text-[#c5c6c7] hover:border-amber-400/50'}
        ${disabled ? 'opacity-40 cursor-not-allowed' : 'cursor-pointer'}
      `}
    >
      {recording ? (
        <><Square className="w-4 h-4" /> Stop &nbsp;<span className="font-mono text-red-300">{fmt(seconds)}</span></>
      ) : (
        <><Mic className="w-4 h-4 text-amber-400" /> Record</>
      )}
    </button>
  )
}
