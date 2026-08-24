import React, { createContext, useContext, useState, useEffect } from 'react'
import { login as apiLogin } from '../api/client'

const AuthContext = createContext(null)

// No login screen anymore - the frontend silently authenticates in the
// background using these credentials so API calls to protected admin
// endpoints keep working. Set these to your REAL admin credentials in
// frontend/.env (VITE_ADMIN_USERNAME / VITE_ADMIN_PASSWORD) - especially
// important if you've already changed the seeded default password.
const AUTO_USERNAME = import.meta.env.VITE_ADMIN_USERNAME || 'admin'
const AUTO_PASSWORD = import.meta.env.VITE_ADMIN_PASSWORD || 'changeme123'

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('qos_token'))
  const [ready, setReady] = useState(!!token)
  const [authError, setAuthError] = useState(null)

  useEffect(() => {
    if (token) { setReady(true); return }
    apiLogin(AUTO_USERNAME, AUTO_PASSWORD)
      .then((data) => {
        localStorage.setItem('qos_token', data.access_token)
        localStorage.setItem('qos_role', data.role)
        setToken(data.access_token)
      })
      .catch((err) => {
        console.error('Auto-login failed:', err)
        setAuthError(
          err.response
            ? `Authentification echouee (${err.response.status}) - verifiez VITE_ADMIN_USERNAME/PASSWORD dans frontend/.env`
            : 'Impossible de contacter le serveur backend.'
        )
      })
      .finally(() => setReady(true))
  }, [])

  return (
    <AuthContext.Provider value={{ isAuthenticated: !!token, ready, authError }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
