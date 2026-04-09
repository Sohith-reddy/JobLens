import { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"
import { UserCircle, Save, Plus, X, Upload, Mail, Calendar, Clock, ShieldCheck } from "lucide-react"
import { getAuthUserInfo } from "@/lib/authUser"
import { getSupabaseClient, hasSupabaseConfig } from "@/lib/supabaseClient"

export default function Profile({ authUser }) {
    const profile = getAuthUserInfo(authUser)
  const [skills, setSkills] = useState(["React", "Node.js", "Python", "Job Analysis", "System Design"])
  const [newSkill, setNewSkill] = useState("")
    const [photo, setPhoto] = useState(null)
    const [photoFile, setPhotoFile] = useState(null)
    const [firstName, setFirstName] = useState(profile.displayName.split(" ")[0] || "")
    const [lastName, setLastName] = useState(profile.displayName.split(" ").slice(1).join(" "))
    const [bio, setBio] = useState("")
    const [isSaving, setIsSaving] = useState(false)
    const [isLoadingProfile, setIsLoadingProfile] = useState(false)
    const [statusMessage, setStatusMessage] = useState("")
    const [errorMessage, setErrorMessage] = useState("")
    const [avatarStoragePath, setAvatarStoragePath] = useState(null)
  const fileInputRef = useRef(null)

    const resolveAvatarUrl = async (client, storagePath, fallbackUrl = null) => {
        if (!storagePath) {
            return fallbackUrl
        }

        const { data, error } = await client.storage.from("profilepics").createSignedUrl(storagePath, 60 * 60 * 24 * 30)
        if (error) {
            return fallbackUrl
        }

        return data?.signedUrl || fallbackUrl
    }

    useEffect(() => {
        if (!authUser) {
            return
        }

        setFirstName(profile.displayName.split(" ")[0] || "")
        setLastName(profile.displayName.split(" ").slice(1).join(" "))
    }, [authUser, profile.displayName])

    useEffect(() => {
        const loadProfile = async () => {
            if (!authUser || !hasSupabaseConfig) {
                return
            }

            setIsLoadingProfile(true)
            setErrorMessage("")

            try {
                const client = getSupabaseClient()
                const { data, error } = await client
                    .from("user_profiles")
                    .select("first_name, last_name, bio, skills, avatar_url, avatar_storage_path")
                    .eq("user_id", authUser.id)
                    .maybeSingle()

                if (error) {
                    throw error
                }

                if (data) {
                    const resolvedAvatarUrl = await resolveAvatarUrl(client, data.avatar_storage_path, data.avatar_url)
                    setFirstName(data.first_name || profile.displayName.split(" ")[0] || "")
                    setLastName(data.last_name || profile.displayName.split(" ").slice(1).join(" "))
                    setBio(data.bio || "")
                    setSkills(Array.isArray(data.skills) && data.skills.length > 0 ? data.skills : skills)
                    setPhoto(resolvedAvatarUrl || null)
                    setAvatarStoragePath(data.avatar_storage_path || null)
                }
            } catch (error) {
                setErrorMessage(error.message || "Failed to load profile information.")
            } finally {
                setIsLoadingProfile(false)
            }
        }

        loadProfile()
    }, [authUser])

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
        if (!file) {
            return
        }

        if (!file.type.startsWith("image/")) {
            setErrorMessage("Please upload a valid image file.")
            return
    }

        const maxFileSizeBytes = 5 * 1024 * 1024
        if (file.size > maxFileSizeBytes) {
            setErrorMessage("Image size must be under 5MB.")
            return
        }

        setErrorMessage("")
        setStatusMessage("")
        setPhotoFile(file)
        setPhoto(URL.createObjectURL(file))
  }

  const triggerFileInput = () => {
    fileInputRef.current.click()
  }

    const handleSaveProfile = async () => {
        if (!authUser) {
            setErrorMessage("You must be logged in to update your profile.")
            return
        }

        if (!hasSupabaseConfig) {
            setErrorMessage("Supabase config is missing. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in client/.env.")
            return
        }

        setIsSaving(true)
        setErrorMessage("")
        setStatusMessage("")

        try {
            const client = getSupabaseClient()
            let profilePhotoUrl = photo
            let newStoragePath = avatarStoragePath
            let avatarUrlForDb = profilePhotoUrl

            if (photoFile) {
                const fileExtension = photoFile.name.includes(".")
                    ? photoFile.name.split(".").pop()?.toLowerCase()
                    : "jpg"
                const safeExtension = fileExtension || "jpg"
                const uploadPath = `${authUser.id}/${Date.now()}-${Math.random().toString(36).slice(2)}.${safeExtension}`

                const { error: uploadError } = await client.storage
                    .from("profilepics")
                    .upload(uploadPath, photoFile, {
                        cacheControl: "3600",
                        upsert: false,
                    })

                if (uploadError) {
                    throw uploadError
                }

                const { data: publicUrlData } = client.storage.from("profilepics").getPublicUrl(uploadPath)
                avatarUrlForDb = publicUrlData.publicUrl
                profilePhotoUrl = await resolveAvatarUrl(client, uploadPath, avatarUrlForDb)
                newStoragePath = uploadPath

                try {
                    await client.from("profile_pictures").update({ is_current: false }).eq("user_id", authUser.id)

                    await client.from("profile_pictures").insert({
                        user_id: authUser.id,
                        bucket_name: "profilepics",
                        storage_path: uploadPath,
                        public_url: avatarUrlForDb,
                        file_name: photoFile.name,
                        file_size: photoFile.size,
                        mime_type: photoFile.type,
                        is_current: true,
                    })
                } catch {
                    // Metadata table is optional; profile update should continue.
                }
            }

            const payload = {
                user_id: authUser.id,
                first_name: firstName.trim(),
                last_name: lastName.trim(),
                bio: bio.trim(),
                skills,
                avatar_url: avatarUrlForDb,
                avatar_storage_path: newStoragePath,
                updated_at: new Date().toISOString(),
            }

            const { error: upsertError } = await client.from("user_profiles").upsert(payload, {
                onConflict: "user_id",
            })

            if (upsertError) {
                throw upsertError
            }

            await client.auth.updateUser({
                data: {
                    full_name: `${firstName} ${lastName}`.trim(),
                    avatar_url: profilePhotoUrl,
                },
            })

            setPhoto(profilePhotoUrl || null)
            setAvatarStoragePath(newStoragePath)
            setPhotoFile(null)
            setStatusMessage("Profile updated successfully.")
        } catch (error) {
            setErrorMessage(error.message || "Failed to save profile.")
        } finally {
            setIsSaving(false)
        }
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
                    <p className="text-xs text-muted-foreground">Click image to upload to your `profilepics` bucket.</p>
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
                                        <CardDescription>
                                            Account details from your current session.
                                            {isLoadingProfile ? " Loading your saved profile..." : ""}
                                        </CardDescription>
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
                                        {errorMessage ? <p className="text-sm text-red-500">{errorMessage}</p> : null}
                                        {statusMessage ? <p className="text-sm text-green-600">{statusMessage}</p> : null}
                </CardContent>
                <CardFooter className="justify-end">
                                        <Button onClick={handleSaveProfile} disabled={isSaving || isLoadingProfile}>
                      <Save className="h-4 w-4 mr-2" />
                                            {isSaving ? "Saving..." : "Save Changes"}
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
