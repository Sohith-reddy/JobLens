import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { ThemeProvider } from "@/components/theme-provider"
import { ChatWidget } from '@/components/layout/ChatWidget'
import Home from '@/pages/Home'
import Dashboard from '@/pages/Dashboard'
import Login from '@/pages/auth/Login'
import Signup from '@/pages/auth/Signup'
import Profile from '@/pages/Profile'
import Plans from '@/pages/Plans'
import About from '@/pages/About'
import Docs from '@/pages/Docs'
import { getSupabaseClient, hasSupabaseConfig } from '@/lib/supabaseClient'

import { useState, useEffect } from 'react'

// Layout wrapper to handle conditional Navbar/Footer/Chat visibility
function Layout({ children, isAuthenticated, isAuthReady, onLogout, authUser }) {
  const location = useLocation()
  const isAuthPage = ['/login', '/signup'].includes(location.pathname)

  if (!isAuthReady) {
    return (
      <div className="flex min-h-screen items-center justify-center text-muted-foreground">
        Loading...
      </div>
    )
  }

  // Redirect if not authenticated (simple protection)
  if (!isAuthenticated && !isAuthPage) {
    return <Navigate to="/login" replace />
  }

  // Redirect if authenticated and trying to access auth pages
  if (isAuthenticated && isAuthPage) {
     return <Navigate to="/" replace />
  }

  return (
    <div className="flex flex-col min-h-screen bg-background text-foreground transition-colors duration-300">
      {!isAuthPage && <Navbar onLogout={onLogout} authUser={authUser} />}
      <main className="flex-grow">
        {children}
      </main>
      {!isAuthPage && <Footer />}
      {/* {!isAuthPage && <ChatWidget />} */}
    </div>
  )
}

function App() {
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [isAuthReady, setIsAuthReady] = useState(false)
  const [authUser, setAuthUser] = useState(null)

  useEffect(() => {
    if (!hasSupabaseConfig) {
      setIsAuthenticated(false)
      setAuthUser(null)
      setIsAuthReady(true)
      return
    }

    const client = getSupabaseClient()

    client.auth.getSession().then(({ data }) => {
      setIsAuthenticated(Boolean(data.session))
      setAuthUser(data.session?.user || null)
      setIsAuthReady(true)
    })

    const {
      data: { subscription },
    } = client.auth.onAuthStateChange((_event, session) => {
      setIsAuthenticated(Boolean(session))
      setAuthUser(session?.user || null)
    })

    return () => {
      subscription.unsubscribe()
    }
  }, [])

  const login = () => {
    setIsAuthenticated(true)
  }

  const logout = async () => {
    if (hasSupabaseConfig) {
      const client = getSupabaseClient()
      await client.auth.signOut()
    }

    setIsAuthenticated(false)
    setAuthUser(null)
  }

  return (
    <ThemeProvider defaultTheme="system" storageKey="joblens-ui-theme">
      <Router>
        <Layout isAuthenticated={isAuthenticated} isAuthReady={isAuthReady} onLogout={logout} authUser={authUser}>
          <Routes>
            <Route path="/" element={<About />} />
            <Route path="/analyze" element={<Home />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/profile" element={<Profile authUser={authUser} />} />
            <Route path="/plans" element={<Plans />} />
            <Route path="/about" element={<About />} />
            <Route path="/docs" element={<Docs />} />
            <Route path="/login" element={<Login onLogin={login} />} />
            <Route path="/signup" element={<Signup onLogin={login} />} />
            <Route path="/about" element={<div className="p-10 text-center">About Page Placeholder</div>} />
          </Routes>
        </Layout>
      </Router>
    </ThemeProvider>
  )
}

export default App
