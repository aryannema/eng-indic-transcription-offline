import { useState, useEffect } from 'react'

interface Props {
  onLogin: (token: string, role: string) => void
}

export default function LoginPage({ onLogin }: Props) {
  const [email, setEmail]       = useState('')
  const [password, setPassword] = useState('')
  const [error, setError]       = useState('')
  const [loading, setLoading]   = useState(false)
  const [isFirst, setIsFirst]   = useState<boolean | null>(null)

  // Check on mount if this is first-user registration
  useEffect(() => {
    fetch('/v1/auth/status')
      .then(r => r.json())
      .then(d => setIsFirst(!d.has_users))
      .catch(() => setIsFirst(false))
  }, [])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    try {
      const endpoint = isFirst ? '/v1/auth/register' : '/v1/auth/login'
      const form = new FormData()
      form.append('email', email.trim())
      form.append('password', password)
      const res = await fetch(endpoint, { method: 'POST', body: form })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? res.statusText)
      onLogin(data.access_token, data.role)
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex justify-center mb-8">
          <img src="logo-nav@2x.webp" alt="VigyanBytes" className="h-10 object-contain" />
        </div>

        <div className="bg-[#13151c] border border-[#1a1c23] rounded-xl p-6">
          <h1 className="text-lg font-semibold text-white mb-1">
            {isFirst === null ? 'Loading…' : isFirst ? 'Create admin account' : 'Sign in'}
          </h1>
          <p className="text-xs text-[#666] mb-6">
            {isFirst === null
              ? 'Checking server…'
              : isFirst
              ? 'First account becomes admin.'
              : 'Vigyan Voice Lane — local, offline, Indic-first.'}
          </p>

          <form onSubmit={submit} className="flex flex-col gap-4">
            <div>
              <label className="text-xs text-[#888] block mb-1">Email</label>
              <input
                type="email" required value={email}
                onChange={e => setEmail(e.target.value)}
                className="w-full bg-[#0d0f14] border border-[#1a1c23] rounded-lg px-3 py-2
                           text-sm text-white placeholder-[#444] focus:outline-none
                           focus:border-amber-400/60"
                placeholder="you@example.com"
              />
            </div>
            <div>
              <label className="text-xs text-[#888] block mb-1">Password</label>
              <input
                type="password" required value={password}
                onChange={e => setPassword(e.target.value)}
                className="w-full bg-[#0d0f14] border border-[#1a1c23] rounded-lg px-3 py-2
                           text-sm text-white placeholder-[#444] focus:outline-none
                           focus:border-amber-400/60"
                placeholder="••••••••"
              />
            </div>

            {error && (
              <div className="text-xs text-red-400 bg-red-900/20 border border-red-500/30
                              rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button
              type="submit" disabled={loading || isFirst === null}
              className="w-full bg-amber-400 hover:bg-amber-300 disabled:opacity-50
                         text-black font-semibold rounded-lg py-2 text-sm transition-colors"
            >
              {loading ? 'Please wait…' : isFirst === null ? '…' : isFirst ? 'Create account' : 'Sign in'}
            </button>
          </form>
        </div>
      </div>
    </div>
  )
}
