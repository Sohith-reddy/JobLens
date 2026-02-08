import {
  Dialog,
  DialogContent,
  DialogTrigger,
  DialogClose
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { User, LogOut, Settings, Award, Calendar, ExternalLink, MapPin } from "lucide-react"
import { Link } from "react-router-dom"
import { Progress } from "@/components/ui/progress"

export function ProfileModal({ children, onLogout }) {
  return (
    <Dialog>
      <DialogTrigger asChild>
        {children}
      </DialogTrigger>
      <DialogContent className="sm:max-w-[400px] p-0 gap-0 overflow-hidden border-none shadow-2xl bg-card text-card-foreground">
        
        {/* Header Background */}
        <div className="h-24 bg-gradient-to-r from-primary/80 to-purple-600/80 relative">
            <DialogClose className="absolute right-4 top-4 text-white/80 hover:text-white transition-colors">
                {/* Close Icon handled by DialogContent default, just styling override if needed or invisible trigger */}
            </DialogClose>
        </div>

        {/* Profile Info */}
        <div className="px-6 pb-6 -mt-10 relative">
            <div className="h-20 w-20 rounded-xl bg-background p-1 shadow-lg mb-3">
                 {/* Avatar Placeholder */}
                 <div className="h-full w-full rounded-lg bg-gradient-to-br from-blue-100 to-blue-200 dark:from-blue-900 dark:to-slate-800 flex items-center justify-center text-2xl font-bold text-primary">
                    UN
                 </div>
            </div>
            
            <div className="flex justify-between items-start">
                <div>
                    <h2 className="text-xl font-bold truncate">User Name</h2>
                    <p className="text-sm text-muted-foreground">@username</p>
                </div>
                <div className="text-right">
                    <div className="inline-flex items-center rounded-md border border-transparent bg-secondary px-2 py-1 text-xs font-semibold text-secondary-foreground">
                        Rank 120
                    </div>
                </div>
            </div>

            <div className="mt-4 flex flex-wrap gap-y-2 gap-x-4 text-xs text-muted-foreground">
                <div className="flex items-center gap-1">
                    <MapPin className="h-3 w-3" /> San Francisco
                </div>
                <div className="flex items-center gap-1">
                    <Calendar className="h-3 w-3" /> Joined Feb 2024
                </div>
            </div>

            {/* Stats / Skills Quick View */}
            <div className="mt-6 space-y-4">
                <div className="flex justify-between items-center text-sm font-medium">
                    <span>Profile Completion</span>
                    <span className="text-primary">85%</span>
                </div>
                <Progress value={85} className="h-2" />
                
                <div className="grid grid-cols-2 gap-3 mt-4">
                    <div className="bg-secondary/30 rounded-lg p-3 text-center transition-colors hover:bg-secondary/50">
                        <div className="text-lg font-bold text-foreground">14</div>
                        <div className="text-xs text-muted-foreground">Scans</div>
                    </div>
                    <div className="bg-secondary/30 rounded-lg p-3 text-center transition-colors hover:bg-secondary/50">
                        <div className="text-lg font-bold text-foreground">6</div>
                        <div className="text-xs text-muted-foreground">Verified</div>
                    </div>
                </div>
            </div>

            {/* Footer Actions */}
            <div className="mt-8 flex flex-col gap-2">
                <DialogClose asChild>
                    <Link to="/profile" className="w-full">
                        <Button className="w-full justify-between group" variant="outline">
                            <span className="flex items-center gap-2">
                                <User className="h-4 w-4 text-muted-foreground group-hover:text-primary transition-colors" /> 
                                View Full Profile
                            </span>
                            <ExternalLink className="h-3 w-3 text-muted-foreground" />
                        </Button>
                    </Link>
                </DialogClose>
                
                <div className="grid grid-cols-2 gap-2">
                    <Button variant="ghost" className="justify-start text-sm text-muted-foreground hover:text-foreground">
                        <Settings className="h-4 w-4 mr-2" /> Settings
                    </Button>
                    <DialogClose asChild>
                         <Button variant="ghost" className="justify-start text-sm text-red-500 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-950/20" onClick={onLogout}>
                            <LogOut className="h-4 w-4 mr-2" /> Sign Out
                        </Button>
                    </DialogClose>
                </div>
            </div>
        </div>
      </DialogContent>
    </Dialog>
  )
}
