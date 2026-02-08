import { BrowserRouter as Router, Routes, Route } from 'react-router-dom'
import { Navbar } from '@/components/layout/Navbar'
import { Footer } from '@/components/layout/Footer'
import { ThemeProvider } from "@/components/theme-provider"
import Home from '@/pages/Home'
import Dashboard from '@/pages/Dashboard'
import Login from '@/pages/auth/Login'
import Signup from '@/pages/auth/Signup'

import { ChatWidget } from '@/components/layout/ChatWidget'

function App() {
  return (
    <ThemeProvider defaultTheme="system" storageKey="joblens-ui-theme">
      <Router>
        <div className="flex flex-col min-h-screen bg-background text-foreground transition-colors duration-300">
          <Navbar />
          <main className="flex-grow">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/dashboard" element={<Dashboard />} />
              <Route path="/login" element={<Login />} />
              <Route path="/signup" element={<Signup />} />
              <Route path="/about" element={<div className="p-10 text-center">About Page Placeholder</div>} />
            </Routes>
          </main>
          <Footer />
          <ChatWidget />
        </div>
      </Router>
    </ThemeProvider>
  )
}

export default App
