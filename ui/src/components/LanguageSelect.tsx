const LANGUAGES = [
  { code: 'auto', label: 'Auto Detect' },
  { code: 'hi',   label: 'Hindi / Hinglish (हिन्दी) — forces Devanagari script' },
  { code: 'en',   label: 'English' },
  { code: 'ta',   label: 'Tamil (தமிழ்)' },
  { code: 'te',   label: 'Telugu (తెలుగు)' },
  { code: 'bn',   label: 'Bengali (বাংলা)' },
  { code: 'mr',   label: 'Marathi (मराठी)' },
  { code: 'gu',   label: 'Gujarati (ગુજરાતી)' },
  { code: 'kn',   label: 'Kannada (ಕನ್ನಡ)' },
  { code: 'ml',   label: 'Malayalam (മലയാളം)' },
  { code: 'pa',   label: 'Punjabi (ਪੰਜਾਬੀ)' },
  { code: 'ur',   label: 'Urdu (اردو)' },
  { code: 'or',   label: 'Odia (ଓଡ଼ିଆ)' },
  { code: 'as',   label: 'Assamese (অসমীয়া)' },
  { code: 'ne',   label: 'Nepali (नेपाली)' },
  { code: 'zh',   label: 'Chinese' },
  { code: 'ja',   label: 'Japanese' },
  { code: 'ko',   label: 'Korean' },
  { code: 'de',   label: 'German' },
  { code: 'fr',   label: 'French' },
  { code: 'es',   label: 'Spanish' },
  { code: 'ar',   label: 'Arabic' },
]

interface Props {
  value: string
  onChange: (v: string) => void
}

export default function LanguageSelect({ value, onChange }: Props) {
  return (
    <select
      value={value}
      onChange={e => onChange(e.target.value)}
      className="bg-[#1a1c23] border border-[#2a2d3a] text-[#c5c6c7] rounded-lg px-3 py-2
                 text-sm focus:outline-none focus:border-amber-400 focus:ring-1 focus:ring-amber-400
                 cursor-pointer w-full sm:w-auto"
    >
      {LANGUAGES.map(l => (
        <option key={l.code} value={l.code}>{l.label}</option>
      ))}
    </select>
  )
}
