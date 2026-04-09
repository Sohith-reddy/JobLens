import { useState, useRef } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { UserCircle, Save, Plus, X, Upload, Mail, Calendar, Clock, ShieldCheck } from "lucide-react"
import { getAuthUserInfo } from "@/lib/authUser"

export default function Profile({ authUser }) {
    const profile = getAuthUserInfo(authUser)
  const [skills, setSkills] = useState(["React", "Node.js", "Python", "Job Analysis", "System Design"])
  const [newSkill, setNewSkill] = useState("")
  const [photo, setPhoto] = useState(null)
    const [firstName, setFirstName] = useState(profile.displayName.split(" ")[0] || "")
    const [lastName, setLastName] = useState(profile.displayName.split(" ").slice(1).join(" "))
    const [bio, setBio] = useState("")
  const fileInputRef = useRef(null)

  const handleAddSkill = () => {
    if (newSkill.trim() && !skills.includes(newSkill.trim())) {
      setSkills([...skills, newSkill.trim()])
      setNewSkill("")
    }
  }

  const handleRemoveSkill = (skillToRemove) => {
    setSkills(skills.filter(skill => skill !== skillToRemove))
  }

  const handlePhotoUpload = (e) => {
    const file = e.target.files[0]
    if (file) {
      const reader = new FileReader()
      reader.onloadend = () => {
        setPhoto(reader.result)
      }
      reader.readAsDataURL(file)
    }
  }

  const triggerFileInput = () => {
    fileInputRef.current.click()
  }
  return (
    <div className="container py-10 max-w-4xl space-y-8">
      <div className="flex flex-col md:flex-row gap-8">
        
        {/* Sidebar Info */}
        <div className="md:w-1/3 flex flex-col gap-6">
            <Card className="text-center card-hover overflow-hidden">
                <CardHeader>
                    <div className="mx-auto h-32 w-32 rounded-full bg-primary/10 flex items-center justify-center text-primary mb-4 relative group">
                        {photo ? (
                            <img src={photo} alt="Profile" className="h-full w-full rounded-full object-cover" />
                        ) : (
                            <span className="text-4xl font-bold">{profile.initials}</span>
                        )}
                        <div className="absolute inset-0 bg-black/40 rounded-full opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center cursor-pointer" onClick={triggerFileInput}>
                            <Upload className="h-8 w-8 text-white" />
                        </div>
                        <input 
                            type="file" 
                            ref={fileInputRef} 
                            className="hidden" 
                            accept="image/*"
                            onChange={handlePhotoUpload}
                        />
                    </div>
                    <CardTitle>{profile.displayName}</CardTitle>
                    <CardDescription>@{profile.username}</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-left space-y-2">
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Mail className="h-4 w-4" /> {profile.email}
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Calendar className="h-4 w-4" /> Joined {profile.joinedAt}
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <Clock className="h-4 w-4" /> Last login {profile.lastLoginAt}
                    </div>
                    <div className="flex items-center gap-2 text-muted-foreground">
                        <ShieldCheck className="h-4 w-4" /> {profile.emailConfirmed ? "Email verified" : "Email not verified"}
                    </div>
                </CardContent>
            </Card>

            <Card className="card-hover">
                <CardHeader>
                    <CardTitle className="text-lg">Skills</CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="flex flex-wrap gap-2">
                        {skills.map(skill => (
                            <div key={skill} className="group flex items-center gap-1 px-3 py-1 bg-secondary text-secondary-foreground rounded-full text-sm font-medium hover:bg-primary hover:text-primary-foreground transition-colors">
                                {skill}
                                <button onClick={() => handleRemoveSkill(skill)} className="opacity-0 group-hover:opacity-100 transition-opacity ml-1">
                                    <X className="h-3 w-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                    <div className="flex gap-2">
                        <Input 
                            placeholder="Add a new skill..." 
                            value={newSkill}
                            onChange={(e) => setNewSkill(e.target.value)}
                            onKeyDown={(e) => e.key === 'Enter' && handleAddSkill()}
                        />
                        <Button size="icon" onClick={handleAddSkill}>
                            <Plus className="h-4 w-4" />
                        </Button>
                    </div>
                </CardContent>
            </Card>
        </div>

        {/* Main Edit Form */}
        <div className="md:w-2/3 space-y-6">
            <Card className="card-hover">
                <CardHeader>
                    <CardTitle>Personal Information</CardTitle>
                    <CardDescription>Account details from your current session.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                    <div className="grid grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="firstName">First Name</Label>
                            <Input id="firstName" value={firstName} onChange={(e) => setFirstName(e.target.value)} />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="lastName">Last Name</Label>
                            <Input id="lastName" value={lastName} onChange={(e) => setLastName(e.target.value)} />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="email">Email</Label>
                        <Input id="email" type="email" value={profile.email} readOnly />
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div className="space-y-2">
                            <Label htmlFor="provider">Auth Provider</Label>
                            <Input id="provider" value={profile.provider.toUpperCase()} readOnly />
                        </div>
                        <div className="space-y-2">
                            <Label htmlFor="userId">User ID</Label>
                            <Input id="userId" value={profile.userId} readOnly />
                        </div>
                    </div>
                    <div className="space-y-2">
                        <Label htmlFor="bio">Bio</Label>
                        <Textarea
                          id="bio"
                          placeholder="Tell us about yourself..."
                          className="min-h-[120px]"
                          value={bio}
                          onChange={(e) => setBio(e.target.value)}
                        />
                    </div>
                </CardContent>
                <CardFooter className="justify-end">
                    <Button>
                      <Save className="h-4 w-4 mr-2" />
                      Save Changes
                    </Button>
                </CardFooter>
            </Card>

            <Card className="card-hover border-destructive/20">
                <CardHeader>
                    <CardTitle className="text-destructive">Danger Zone</CardTitle>
                    <CardDescription>Irreversible actions requiring confirmation.</CardDescription>
                </CardHeader>
                <CardContent>
                    <Button variant="outline" className="w-full sm:w-auto border-destructive text-destructive hover:bg-destructive hover:text-white">Delete Account</Button>
                </CardContent>
            </Card>
        </div>
      </div>
    </div>
  )
}
