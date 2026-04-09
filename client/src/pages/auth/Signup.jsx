import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Link } from "react-router-dom"
import { useState } from "react"
import { getSupabaseClient, hasSupabaseConfig } from "@/lib/supabaseClient"

export default function Signup({ onLogin }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")
  const [successMessage, setSuccessMessage] = useState("")

  const handleSignup = async (event) => {
    event.preventDefault()
    setErrorMessage("")
    setSuccessMessage("")

    if (!hasSupabaseConfig) {
      setErrorMessage("Supabase config is missing. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in client/.env.")
      return
    }

    if (password !== confirmPassword) {
      setErrorMessage("Passwords do not match.")
      return
    }

    try {
      setIsLoading(true)
      const client = getSupabaseClient()
      const { data, error } = await client.auth.signUp({
        email: email.trim(),
        password,
        options: {
          emailRedirectTo: window.location.origin,
        },
      })

      if (error) {
        setErrorMessage(error.message)
        return
      }

      if (data.session) {
        if (onLogin) {
          onLogin()
        }
      } else {
        setSuccessMessage("Account created. Please check your email to confirm your account before signing in.")
      }
    } catch (error) {
      setErrorMessage(error.message || "Failed to create account. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_5%_10%,hsl(var(--primary)/0.18),transparent_40%),radial-gradient(circle_at_90%_10%,hsl(190_90%_45%/0.17),transparent_34%),linear-gradient(145deg,hsl(var(--background))_0%,hsl(var(--secondary)/0.38)_100%)]" />
      <div className="pointer-events-none absolute -left-20 bottom-0 -z-10 h-72 w-72 rounded-full bg-primary/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-24 top-4 -z-10 h-72 w-72 rounded-full bg-cyan-400/20 blur-3xl" />

      <div className="mx-auto flex w-full max-w-lg flex-col items-center justify-center gap-4">
        <div className="text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">JobLens AI</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground">Create your account</h1>
          <p className="mt-2 text-sm text-muted-foreground">Start analyzing opportunities with a secure account.</p>
        </div>

        <Card className="w-full border-primary/20 bg-card/95 shadow-xl shadow-primary/10 backdrop-blur">
          <CardHeader className="space-y-1 pb-3">
            <CardTitle className="text-xl font-semibold tracking-tight">Sign up</CardTitle>
          <CardDescription>
            Enter your email below to create your account
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSignup}>
          <CardContent className="grid gap-4">
          <div className="grid gap-2">
            <Label htmlFor="email">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="m@example.com"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              required
              minLength={6}
            />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="confirm-password">Confirm Password</Label>
            <Input
              id="confirm-password"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              required
              minLength={6}
            />
          </div>
          {/* <p className="text-xs text-muted-foreground">
            Passwords are securely hashed by Supabase Auth before storage.
          </p> */}
          {errorMessage ? (
            <p className="text-sm text-red-500" role="alert">
              {errorMessage}
            </p>
          ) : null}
          {successMessage ? (
            <p className="text-sm text-green-600" role="status">
              {successMessage}
            </p>
          ) : null}
          </CardContent>
        <CardFooter className="pt-1">
            <div className="flex flex-col w-full gap-4">
                <Button className="w-full" type="submit" disabled={isLoading}>
                  {isLoading ? "Creating account..." : "Sign Up"}
                </Button>
                <p className="text-center text-sm text-muted-foreground">
                    Already have an account?{" "}
                    <Link to="/login" className="underline underline-offset-4 hover:text-primary">
                        Sign in
                    </Link>
                </p>
            </div>
        </CardFooter>
        </form>
        </Card>
      </div>
    </div>
  )
}
