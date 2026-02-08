import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ShieldCheck, User } from 'lucide-react'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { cn } from "@/lib/utils"

export function Navbar({ onLogout }) {
  const location = useLocation()
  
  const navItems = [
    { name: 'Analyze', path: '/' },
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'About', path: '/about' },
  ]

  return (
    <nav className="border-b bg-background/80 backdrop-blur-md sticky top-0 z-50 w-full transition-all duration-300 shadow-sm custom-navbar-gradient">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-8">
          <Link to="/" className="flex items-center space-x-2 group">
            <div className="bg-primary/10 p-2 rounded-full group-hover:bg-primary/20 transition-colors">
                <ShieldCheck className="h-6 w-6 text-primary" />
            </div>
            <span className="hidden font-bold sm:inline-block text-xl bg-gradient-to-r from-primary to-purple-600 bg-clip-text text-transparent">
                JobLens AI
            </span>
          </Link>
          
          {/* Tab-based Navigation */}
          <div className="hidden md:flex items-center space-x-1">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "relative px-4 py-2 text-sm font-medium transition-colors hover:text-primary",
                  location.pathname === item.path
                    ? "text-primary"
                    : "text-muted-foreground"
                )}
              >
                {item.name}
                {location.pathname === item.path && (
                    <span className="absolute bottom-0 left-0 h-0.5 w-full bg-primary rounded-full" />
                )}
              </Link>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <ThemeToggle />
          <div className="hidden sm:flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={onLogout}>Sign Out</Button>
            <Button size="icon" variant="ghost" className="rounded-full">
                <User className="h-5 w-5" />
            </Button>
          </div>
           {/* Mobile Menu Placeholder */}
           <Button variant="ghost" size="icon" className="md:hidden">
              <User className="h-5 w-5" />
           </Button>
        </div>
      </div>
    </nav>
  )
}
