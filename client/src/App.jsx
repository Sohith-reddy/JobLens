import { BrowserRouter as Router, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { ThemeProvider } from "@/components/theme-provider"
import { ChatWidget } from '@/components/layout/ChatWidget'
import Home from '@/pages/Home'
import Dashboard from '@/pages/Dashboard'
import Login from '@/pages/auth/Login'
import Signup from '@/pages/auth/Signup'
import { useState, useEffect } from 'react'

// Layout wrapper to handle conditional Navbar/Footer/Chat visibility
function Layout({ children, isAuthenticated, onLogout }) {
  const location = useLocation()
  const isAuthPage = ['/login', '/signup'].includes(location.pathname)

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
      {!isAuthPage && <Navbar onLogout={onLogout} />}
      <main className="flex-grow">
        {children}
      </main>
      {!isAuthPage && <Footer />}
      {!isAuthPage && <ChatWidget />}
    </div>
  )
}

function App() {
  // Persist auth state (mock)
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem('joblens_auth') === 'true'
  })

  const login = () => {
    setIsAuthenticated(true)
    localStorage.setItem('joblens_auth', 'true')
  }

  const logout = () => {
    setIsAuthenticated(false)
    localStorage.removeItem('joblens_auth')
  }

  return (
    <ThemeProvider defaultTheme="system" storageKey="joblens-ui-theme">
      <Router>
        <Layout isAuthenticated={isAuthenticated} onLogout={logout}>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/login" element={<Login onLogin={login} />} />
            <Route path="/signup" element={<Signup />} />
            <Route path="/about" element={<div className="p-10 text-center">About Page Placeholder</div>} />
          </Routes>
        </Layout>
      </Router>
    </ThemeProvider>
  )
}

export default App
