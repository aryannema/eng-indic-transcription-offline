import { useRef, useState } from 'react'
import { Upload } from 'lucide-react'

interface Props {
  onFile: (f: File) => void
  disabled: boolean
}

export default function DropZone({ onFile, disabled }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragging(false)
    const f = e.dataTransfer.files[0]
    if (f) onFile(f)
  }

  function handleChange(e: React.ChangeEvent<HTMLInputElement>) {
    const f = e.target.files?.[0]
    if (f) onFile(f)
    e.target.value = ''
  }

  return (
    <div
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={e => { e.preventDefault(); setDragging(true) }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
      className={`
        relative flex flex-col items-center justify-center gap-3
        border-2 border-dashed rounded-xl p-10 cursor-pointer
        transition-all duration-200 select-none
        ${dragging ? 'drop-active' : 'border-[#2a2d3a] hover:border-amber-400/50'}
        ${disabled ? 'opacity-40 cursor-not-allowed' : ''}
      `}
    >
      <Upload className="w-10 h-10 text-amber-400 opacity-80" />
      <div className="text-center">
        <p className="text-[#c5c6c7] font-medium">Drop audio / video file here</p>
        <p className="text-sm text-[#666] mt-1">
          MP3, WAV, M4A, OGG, FLAC, MP4, MOV, MKV, WEBM
        </p>
      </div>
      <span className="text-xs text-amber-400/70 border border-amber-400/30 px-3 py-1 rounded-full">
        or click to browse
      </span>
      <input
        ref={inputRef}
        type="file"
        accept="audio/*,video/*,.mkv"
        className="hidden"
        onChange={handleChange}
        disabled={disabled}
      />
    </div>
  )
}
