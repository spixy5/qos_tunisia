import React, { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { useTheme } from '../context/ThemeContext.jsx'
import SignalMark from '../components/SignalMark.jsx'

export default function LoginPage() {
  const { login } = useAuth()
  const { theme, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)
    setLoading(true)
    try {
      const role = await login(username, password)
      navigate(role === 'admin' ? '/admin' : '/dashboard')
    } catch (err) {
      if (err.response?.status === 401) {
        setError('Identifiants incorrects.')
      } else {
        setError(
          `Erreur serveur (${err.response?.status ?? 'reseau'}) : ${
            err.response?.data?.detail || err.message
          }`
        )
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      style={{
        minHeight: '100vh',
        position: 'relative',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background:
          'radial-gradient(ellipse at top, rgba(51,214,192,0.06), transparent 60%), var(--bg)',
      }}
    >
      <button
        className="btn-ghost"
        onClick={toggleTheme}
        style={{ position: 'absolute', top: 20, right: 20 }}
      >
        {theme === 'dark' ? '☀' : '🌙'}
      </button>
      <form onSubmit={handleSubmit} className="panel" style={{ width: 360, padding: 32 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 28 }}>
          <SignalMark bars={4} size={30} color="var(--signal-good)" />
          <div>
            <h1 style={{ fontSize: 18 }}>QoS Tunisie</h1>
            <div className="eyebrow">Supervision reseaux mobiles</div>
          </div>
        </div>

        <label style={{ display: 'block', marginBottom: 14 }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Utilisateur</div>
          <input
            type="text"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            style={{ width: '100%' }}
            autoFocus
          />
        </label>

        <label style={{ display: 'block', marginBottom: 20 }}>
          <div className="eyebrow" style={{ marginBottom: 6 }}>Mot de passe</div>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: '100%' }}
          />
        </label>

        {error && (
          <div style={{ color: 'var(--signal-poor)', fontSize: 13, marginBottom: 16 }}>{error}</div>
        )}

        <button type="submit" className="btn-primary" style={{ width: '100%' }} disabled={loading}>
          {loading ? 'Connexion...' : 'Se connecter'}
        </button>
      </form>
    </div>
  )
}
