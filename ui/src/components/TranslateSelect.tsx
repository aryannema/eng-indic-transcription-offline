const TRANSLATE_TARGETS = [
  { code: '',   label: 'No Translation' },
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

interface Props {
  value: string
  onChange: (v: string) => void
  disabled: boolean
}

export default function TranslateSelect({ value, onChange, disabled }: Props) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[#666] whitespace-nowrap">Translate to:</span>
      <select
        value={value}
        onChange={e => onChange(e.target.value)}
        disabled={disabled}
        className="bg-[#1a1c23] border border-[#2a2d3a] text-[#c5c6c7] text-sm
                   rounded-lg px-3 py-2 focus:outline-none focus:ring-1 focus:ring-amber-400/50
                   disabled:opacity-40 disabled:cursor-not-allowed"
      >
        {TRANSLATE_TARGETS.map(l => (
          <option key={l.code} value={l.code}>{l.label}</option>
        ))}
      </select>
    </div>
  )
}
