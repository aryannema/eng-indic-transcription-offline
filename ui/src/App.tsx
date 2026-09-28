import { useState, useCallback, useEffect } from 'react'
import DropZone from './components/DropZone'
import Recorder from './components/Recorder'
import LanguageSelect from './components/LanguageSelect'
import Transcript from './components/Transcript'
import Translation from './components/Translation'
import TranslateBar from './components/TranslateBar'
import ExportBar from './components/ExportBar'
import LoginPage from './components/LoginPage'
import HistoryPanel from './components/HistoryPanel'
import ChangePassword from './components/ChangePassword'

type Status = 'idle' | 'uploading' | 'transcribing' | 'translating' | 'done' | 'error'

interface STTResult {
  text: string
  engine: string
  language: string
  filename: string
  latencyMs: number
}

interface TranslateResult {
  text: string
  sourceLang: string
  targetLang: string
  model: string
  latencyMs: number
}

export default function App() {
  const [language, setLanguage]       = useState('hi')
  const [status, setStatus]           = useState<Status>('idle')
  const [sttResult, setSttResult]     = useState<STTResult | null>(null)
  const [transResult, setTransResult] = useState<TranslateResult | null>(null)
  const [error, setError]             = useState('')
  const [showHistory, setShowHistory]   = useState(false)

  const [showChangePw, setShowChangePw] = useState(false)
  const [userList, setUserList]         = useState<{ id: string; email: string; role: string }[]>([])

  // Auth state
  const [token, setToken]         = useState<string | null>(() => localStorage.getItem('vv_token'))
  const [role, setRole]           = useState<string | null>(() => localStorage.getItem('vv_role'))
  const [laptopMode, setLaptopMode] = useState(false)

  // Detect laptop_mode from /health on mount
  useEffect(() => {
    fetch('/health').then(r => r.json()).then(d => {
      setLaptopMode(!!d.laptop_mode)
    }).catch(() => {})
  }, [])

  // Validate stored token on mount — only clears on confirmed 401, not on network errors
  useEffect(() => {
    if (laptopMode || !token) return
    fetch('/v1/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    }).then(r => {
      if (r.status === 401) logout()
    }).catch(() => {})
  }, [laptopMode])

  const onLogin = (t: string, r: string) => {
    localStorage.setItem('vv_token', t)
    localStorage.setItem('vv_role', r)
    // Reload so the app mounts fresh with the token already in localStorage.
    // This avoids a React concurrent-mode edge case where the post-login
    // render produces a blank screen even though state was updated.
    window.location.reload()
  }

  const logout = () => {
    localStorage.removeItem('vv_token')
    localStorage.removeItem('vv_role')
    setToken(null)
    setRole(null)
  }

  // Auth headers — empty in laptop mode or when no token
  const authHeaders = (): HeadersInit =>
    token ? { Authorization: `Bearer ${token}` } : {}

  const busy = status === 'uploading' || status === 'transcribing' || status === 'translating'

  // Show login page in server mode if not authenticated
  if (!laptopMode && !token) {
    return <LoginPage onLogin={onLogin} />
  }

  const transcribe = useCallback(async (file: File) => {
    setStatus('uploading')
    setError('')
    setSttResult(null)
    setTransResult(null)

    let stt: STTResult
    try {
      const form = new FormData()
      form.append('file', file)
      form.append('model', 'whisper-1')
      if (language !== 'auto') form.append('language', language)
      form.append('response_format', 'verbose_json')

      setStatus('transcribing')
      const t0  = performance.now()
      const res = await fetch('/v1/audio/transcriptions', {
        method: 'POST', body: form, headers: authHeaders(),
      })
      const latencyMs = Math.round(performance.now() - t0)

      if (res.status === 401) { logout(); return }
      if (!res.ok) {
        const msg = await res.text().catch(() => res.statusText)
        throw new Error(`STT error ${res.status}: ${msg}`)
      }

      const data = await res.json()
      stt = {
        text: data.text ?? '',
        engine: data.engine ?? 'whisper',
        language: data.language ?? language,
        filename: file.name,
        latencyMs,
      }
      setSttResult(stt)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
      setStatus('error')
      return
    }

    setStatus('done')
  }, [language, token])

  const statusMessage = {
    uploading:    'Uploading…',
    transcribing: 'Transcribing…',
    translating:  'Translating…',
  }[status as 'uploading' | 'transcribing' | 'translating']

  return (
    <div className="min-h-screen flex flex-col">
      {/* Nav */}
      <header className="border-b border-[#1a1c23] px-5 py-3 flex items-center gap-3">
        <img src="logo-nav@2x.webp" alt="VigyanBytes" className="h-8 object-contain" />

        {/* Breadcrumb — shows current section with back arrow */}
        <div className="flex items-center gap-1 text-xs text-[#666]">
          {showHistory ? (
            <>
              <button
                onClick={() => setShowHistory(false)}
                className="hover:text-amber-400 transition-colors flex items-center gap-1"
              >
                ← Transcribe
              </button>
              <span className="text-[#333]">/</span>
              <span className="text-white">History</span>
            </>
          ) : (
            <span className="hidden sm:inline">/ Transcribe</span>
          )}
        </div>

        <div className="ml-auto flex items-center gap-3">
          {/* History toggle (server mode only) */}
          {!laptopMode && (
            <button
              onClick={() => setShowHistory(h => !h)}
              className={`text-xs px-3 py-1 rounded border transition-colors
                ${showHistory
                  ? 'border-amber-400/60 text-amber-400'
                  : 'border-[#1a1c23] text-[#666] hover:text-white hover:border-[#333]'}`}
            >
              {showHistory ? '← Back' : 'History'}
            </button>
          )}
          {/* User info + logout (server mode only) */}
          {!laptopMode && token && (
            <>
              <button
                onClick={() => {
                  if (role === 'admin') {
                    fetch('/v1/auth/users', { headers: { Authorization: `Bearer ${token}` } })
                      .then(r => r.json()).then(setUserList).catch(() => {})
                  }
                  setShowChangePw(true)
                }}
                className="text-xs text-[#555] hover:text-amber-400 transition-colors"
                title="Change password"
              >
                Password
              </button>
              <button
                onClick={logout}
                className="text-xs text-[#555] hover:text-red-400 transition-colors"
                title="Sign out"
              >
                Sign out
              </button>
            </>
          )}
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 w-full max-w-2xl mx-auto px-4 py-10 flex flex-col gap-6">
        {showHistory && !laptopMode ? (
          <HistoryPanel token={token ?? ''} />
        ) : (
          <>
            <div>
              <h1 className="text-2xl font-bold text-white">Transcribe</h1>
              <p className="text-sm text-[#666] mt-1">
                Local · Offline · Hindi-first — powered by Whisper &amp; IndicConformer
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-3">
              <LanguageSelect value={language} onChange={setLanguage} />
              <Recorder onRecording={transcribe} disabled={busy} />
            </div>

            <DropZone onFile={transcribe} disabled={busy} />

            {busy && statusMessage && (
              <div className="fade-in flex items-center gap-3 text-sm text-[#888]">
                <span className="inline-block w-4 h-4 rounded-full border-2 border-amber-400
                                 border-t-transparent animate-spin" />
                {statusMessage}
              </div>
            )}

            {error && (
              <div className="fade-in bg-red-900/20 border border-red-500/40 rounded-lg
                              px-4 py-3 text-sm text-red-300">
                {error}
              </div>
            )}

            {sttResult && (
              <>
                <Transcript
                  text={sttResult.text}
                  engine={sttResult.engine}
                  language={sttResult.language}
                  filename={sttResult.filename}
                  latencyMs={sttResult.latencyMs}
                />
                <ExportBar text={sttResult.text} filename={sttResult.filename} />
                <TranslateBar
                  sourceText={sttResult.text}
                  sourceLang={sttResult.language}
                  token={token ?? ''}
                  authHeaders={authHeaders}
                  onResult={setTransResult}
                  onError={setError}
                />
              </>
            )}

            {transResult && (
              <>
                <Translation
                  text={transResult.text}
                  sourceLang={transResult.sourceLang}
                  targetLang={transResult.targetLang}
                  model={transResult.model}
                  latencyMs={transResult.latencyMs}
                />
                <ExportBar text={transResult.text} filename={`${transResult.targetLang}_${sttResult?.filename ?? 'translation'}`} />
              </>
            )}
          </>
        )}
      </main>

      <footer className="border-t border-[#1a1c23] px-5 py-3 flex items-center
                         justify-between text-xs text-[#444]">
        <span>VigyanBytes — Vigyan Virtual Cloud</span>
        <img src="wordmark.webp" alt="" className="h-4 opacity-30 object-contain" />
      </footer>

      {showChangePw && token && role && (
        <ChangePassword
          token={token}
          role={role}
          users={role === 'admin' ? userList : undefined}
          onClose={() => setShowChangePw(false)}
        />
      )}
    </div>
  )
}
