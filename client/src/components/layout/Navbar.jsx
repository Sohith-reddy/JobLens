import { Link, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { ShieldCheck, User } from 'lucide-react'
import { ThemeToggle } from '@/components/layout/ThemeToggle'
import { cn } from "@/lib/utils"

export function Navbar() {
  const location = useLocation()
  
  const navItems = [
    { name: 'Analyze', path: '/' },
    { name: 'Dashboard', path: '/dashboard' },
    { name: 'About', path: '/about' },
  ]

  return (
    <nav className="border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 sticky top-0 z-50 w-full transition-colors duration-300">
      <div className="container flex h-16 items-center justify-between">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center space-x-2">
            <ShieldCheck className="h-6 w-6 text-primary" />
            <span className="hidden font-bold sm:inline-block text-lg">JobLens AI</span>
          </Link>
          
          {/* Tab-based Navigation */}
          <div className="hidden md:flex h-10 items-center justify-center rounded-md bg-muted p-1 text-muted-foreground">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={cn(
                  "inline-flex items-center justify-center whitespace-nowrap rounded-sm px-3 py-1.5 text-sm font-medium ring-offset-background transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
                  location.pathname === item.path
                    ? "bg-background text-foreground shadow-sm"
                    : "hover:bg-background/50 hover:text-foreground"
                )}
              >
                {item.name}
              </Link>
            ))}
          </div>
        </div>

        <div className="flex items-center gap-4">
          <ThemeToggle />
          <div className="hidden sm:flex items-center gap-2">
            <Link to="/login">
                <Button variant="ghost" size="sm">Sign In</Button>
            </Link>
            <Link to="/signup">
                <Button size="sm">Get Started</Button>
            </Link>
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
