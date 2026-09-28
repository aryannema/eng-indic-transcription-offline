import { useState, useEffect } from 'react'

interface User {
  id: string
  email: string
  role: string
}

interface Props {
  token: string
  role: string
  users?: User[]   // initial list passed from App (admin only)
  onClose: () => void
}

export default function ChangePassword({ token, role, users: initialUsers, onClose }: Props) {
  const isAdmin = role === 'admin'
  const [tab, setTab] = useState<'own' | 'reset' | 'users'>('own')

  // own password
  const [current, setCurrent]   = useState('')
  const [next, setNext]         = useState('')
  const [confirm, setConfirm]   = useState('')

  // admin reset password
  const [targetId, setTargetId] = useState('')
  const [adminPw, setAdminPw]   = useState('')
  const [adminPwC, setAdminPwC] = useState('')

  // user management
  const [userList, setUserList]     = useState<User[]>(initialUsers ?? [])
  const [newEmail, setNewEmail]     = useState('')
  const [newPw, setNewPw]           = useState('')
  const [newPwC, setNewPwC]         = useState('')
  const [deleteId, setDeleteId]     = useState('')
  const [confirmDelete, setConfirmDelete] = useState(false)

  const [msg, setMsg]       = useState<{ ok: boolean; text: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const headers = { Authorization: `Bearer ${token}` }

  // Refresh user list whenever Users tab is selected
  useEffect(() => {
    if (tab === 'users' && isAdmin) fetchUsers()
  }, [tab])

  async function fetchUsers() {
    try {
      const res = await fetch('/v1/auth/users', { headers })
      if (res.ok) setUserList(await res.json())
    } catch {}
  }

  function switchTab(t: typeof tab) {
    setTab(t); setMsg(null)
    setConfirmDelete(false); setDeleteId('')
  }

  // ── Own password ──────────────────────────────────────────────────
  async function submitOwn(e: React.FormEvent) {
    e.preventDefault()
    if (next !== confirm) { setMsg({ ok: false, text: 'Passwords do not match' }); return }
    setLoading(true); setMsg(null)
    const form = new FormData()
    form.append('current_password', current)
    form.append('new_password', next)
    const res = await fetch('/v1/auth/me/password', { method: 'POST', headers, body: form })
    const data = await res.json()
    setLoading(false)
    if (res.ok) { setMsg({ ok: true, text: 'Password changed.' }); setCurrent(''); setNext(''); setConfirm('') }
    else setMsg({ ok: false, text: data.detail ?? 'Error' })
  }

  // ── Admin reset another user's password ──────────────────────────
  async function submitReset(e: React.FormEvent) {
    e.preventDefault()
    if (adminPw !== adminPwC) { setMsg({ ok: false, text: 'Passwords do not match' }); return }
    if (!targetId) { setMsg({ ok: false, text: 'Select a user' }); return }
    setLoading(true); setMsg(null)
    const form = new FormData()
    form.append('new_password', adminPw)
    const res = await fetch(`/v1/auth/users/${targetId}/password`, { method: 'POST', headers, body: form })
    const data = await res.json()
    setLoading(false)
    if (res.ok) { setMsg({ ok: true, text: 'Password reset.' }); setAdminPw(''); setAdminPwC(''); setTargetId('') }
    else setMsg({ ok: false, text: data.detail ?? 'Error' })
  }

  // ── Create user ───────────────────────────────────────────────────
  async function submitCreate(e: React.FormEvent) {
    e.preventDefault()
    if (newPw !== newPwC) { setMsg({ ok: false, text: 'Passwords do not match' }); return }
    setLoading(true); setMsg(null)
    const form = new URLSearchParams()
    form.append('email', newEmail)
    form.append('password', newPw)
    const res = await fetch('/v1/auth/users', {
      method: 'POST',
      headers: { ...headers, 'Content-Type': 'application/x-www-form-urlencoded' },
      body: form.toString(),
    })
    const data = await res.json()
    setLoading(false)
    if (res.ok) {
      setMsg({ ok: true, text: `User ${newEmail} created.` })
      setNewEmail(''); setNewPw(''); setNewPwC('')
      fetchUsers()
    } else setMsg({ ok: false, text: data.detail ?? 'Error' })
  }

  // ── Delete user ───────────────────────────────────────────────────
  async function submitDelete() {
    if (!deleteId) return
    setLoading(true); setMsg(null)
    const res = await fetch(`/v1/auth/users/${deleteId}`, { method: 'DELETE', headers })
    const data = await res.json()
    setLoading(false)
    if (res.ok) {
      setMsg({ ok: true, text: 'User deleted.' })
      setDeleteId(''); setConfirmDelete(false)
      fetchUsers()
    } else setMsg({ ok: false, text: data.detail ?? 'Error' })
  }

  const inputCls = `w-full bg-[#0d0f14] border border-[#1a1c23] rounded-lg px-3 py-2
                    text-sm text-white placeholder-[#444] focus:outline-none
                    focus:border-amber-400/60`

  const tabBtn = (t: typeof tab, label: string) => (
    <button
      onClick={() => switchTab(t)}
      className={`flex-1 py-1.5 text-xs font-semibold rounded-lg border transition-colors
        ${tab === t ? 'bg-amber-400 text-black border-amber-400' : 'border-[#1a1c23] text-[#888] hover:text-white'}`}
    >{label}</button>
  )

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 px-4">
      <div className="w-full max-w-sm bg-[#13151c] border border-[#1a1c23] rounded-xl p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-white font-semibold">Account</h2>
          <button onClick={onClose} className="text-[#666] hover:text-white text-lg leading-none">✕</button>
        </div>

        {/* Tab bar — admin sees all three tabs */}
        <div className="flex gap-2 mb-4">
          {tabBtn('own', 'My Password')}
          {isAdmin && tabBtn('reset', 'Reset User')}
          {isAdmin && tabBtn('users', 'Users')}
        </div>

        {/* ── Own password ── */}
        {tab === 'own' && (
          <form onSubmit={submitOwn} className="flex flex-col gap-3">
            <div>
              <label className="text-xs text-[#888] block mb-1">Current password</label>
              <input type="password" required value={current} onChange={e => setCurrent(e.target.value)} className={inputCls} placeholder="••••••••" />
            </div>
            <div>
              <label className="text-xs text-[#888] block mb-1">New password</label>
              <input type="password" required value={next} onChange={e => setNext(e.target.value)} className={inputCls} placeholder="min 8 characters" />
            </div>
            <div>
              <label className="text-xs text-[#888] block mb-1">Confirm new password</label>
              <input type="password" required value={confirm} onChange={e => setConfirm(e.target.value)} className={inputCls} placeholder="••••••••" />
            </div>
            {msg && <Msg m={msg} />}
            <button type="submit" disabled={loading} className="w-full bg-amber-400 hover:bg-amber-300 disabled:opacity-50 text-black font-semibold rounded-lg py-2 text-sm transition-colors">
              {loading ? 'Saving…' : 'Change Password'}
            </button>
          </form>
        )}

        {/* ── Admin: reset another user's password ── */}
        {tab === 'reset' && isAdmin && (
          <form onSubmit={submitReset} className="flex flex-col gap-3">
            <div>
              <label className="text-xs text-[#888] block mb-1">User</label>
              <select value={targetId} onChange={e => setTargetId(e.target.value)} className={inputCls}>
                <option value="">Select user…</option>
                {userList.map(u => (
                  <option key={u.id} value={u.id}>{u.email} ({u.role})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs text-[#888] block mb-1">New password</label>
              <input type="password" required value={adminPw} onChange={e => setAdminPw(e.target.value)} className={inputCls} placeholder="min 8 characters" />
            </div>
            <div>
              <label className="text-xs text-[#888] block mb-1">Confirm</label>
              <input type="password" required value={adminPwC} onChange={e => setAdminPwC(e.target.value)} className={inputCls} placeholder="••••••••" />
            </div>
            {msg && <Msg m={msg} />}
            <button type="submit" disabled={loading} className="w-full bg-amber-400 hover:bg-amber-300 disabled:opacity-50 text-black font-semibold rounded-lg py-2 text-sm transition-colors">
              {loading ? 'Saving…' : 'Reset Password'}
            </button>
          </form>
        )}

        {/* ── Admin: user management ── */}
        {tab === 'users' && isAdmin && (
          <div className="flex flex-col gap-4">

            {/* User list */}
            <div>
              <p className="text-xs text-[#555] uppercase tracking-wider mb-2">Provisioned Users</p>
              {userList.length === 0
                ? <p className="text-xs text-[#444] text-center py-2">No users yet</p>
                : <div className="flex flex-col gap-1">
                    {userList.map(u => (
                      <div key={u.id} className="flex items-center justify-between bg-[#0d0f14] border border-[#1a1c23] rounded-lg px-3 py-2">
                        <div>
                          <span className="text-xs text-white">{u.email}</span>
                          <span className={`ml-2 text-xs px-1.5 py-0.5 rounded ${u.role === 'admin' ? 'bg-amber-400/20 text-amber-400' : 'bg-[#1a1c23] text-[#666]'}`}>{u.role}</span>
                        </div>
                        <button
                          onClick={() => { setDeleteId(u.id); setConfirmDelete(true); setMsg(null) }}
                          className="text-xs text-[#555] hover:text-red-400 transition-colors ml-2"
                          title="Delete user"
                        >✕</button>
                      </div>
                    ))}
                  </div>
              }
            </div>

            {/* Delete confirmation */}
            {confirmDelete && deleteId && (
              <div className="bg-red-900/20 border border-red-500/30 rounded-lg p-3 flex flex-col gap-2">
                <p className="text-xs text-red-300">
                  Delete <strong>{userList.find(u => u.id === deleteId)?.email}</strong>? This cannot be undone.
                </p>
                <div className="flex gap-2">
                  <button onClick={submitDelete} disabled={loading}
                    className="flex-1 bg-red-600 hover:bg-red-500 disabled:opacity-50 text-white text-xs font-semibold rounded-lg py-1.5 transition-colors">
                    {loading ? 'Deleting…' : 'Delete'}
                  </button>
                  <button onClick={() => { setConfirmDelete(false); setDeleteId('') }}
                    className="flex-1 border border-[#1a1c23] text-[#888] text-xs rounded-lg py-1.5 hover:text-white transition-colors">
                    Cancel
                  </button>
                </div>
              </div>
            )}

            {/* Create user form */}
            <div>
              <p className="text-xs text-[#555] uppercase tracking-wider mb-2">Create User</p>
              <form onSubmit={submitCreate} className="flex flex-col gap-2">
                <input type="email" required value={newEmail} onChange={e => setNewEmail(e.target.value)}
                  className={inputCls} placeholder="user@example.com" />
                <input type="password" required value={newPw} onChange={e => setNewPw(e.target.value)}
                  className={inputCls} placeholder="Password (min 8 chars)" />
                <input type="password" required value={newPwC} onChange={e => setNewPwC(e.target.value)}
                  className={inputCls} placeholder="Confirm password" />
                {msg && <Msg m={msg} />}
                <button type="submit" disabled={loading}
                  className="w-full bg-amber-400 hover:bg-amber-300 disabled:opacity-50 text-black font-semibold rounded-lg py-2 text-sm transition-colors">
                  {loading ? 'Creating…' : 'Create User'}
                </button>
              </form>
            </div>

          </div>
        )}

      </div>
    </div>
  )
}

function Msg({ m }: { m: { ok: boolean; text: string } }) {
  return (
    <div className={`text-xs px-3 py-2 rounded-lg border ${m.ok ? 'text-green-400 bg-green-900/20 border-green-500/30' : 'text-red-400 bg-red-900/20 border-red-500/30'}`}>
      {m.text}
    </div>
  )
}
