import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Link } from "react-router-dom"
import { useState } from "react"
import { getSupabaseClient, hasSupabaseConfig } from "@/lib/supabaseClient"

export default function Login({ onLogin }) {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [errorMessage, setErrorMessage] = useState("")

  const handleSignIn = async (event) => {
    event.preventDefault()
    setErrorMessage("")

    if (!hasSupabaseConfig) {
      setErrorMessage("Supabase config is missing. Set VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY in client/.env.")
      return
    }

    try {
      setIsLoading(true)
      const client = getSupabaseClient()
      const { error } = await client.auth.signInWithPassword({
        email: email.trim(),
        password,
      })

      if (error) {
        setErrorMessage(error.message)
        return
      }

      if (onLogin) {
        onLogin()
      }
    } catch (error) {
      setErrorMessage(error.message || "Failed to sign in. Please try again.")
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="relative min-h-[calc(100vh-4rem)] overflow-hidden px-4 py-10">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_15%_20%,hsl(var(--primary)/0.22),transparent_38%),radial-gradient(circle_at_85%_0%,hsl(210_90%_55%/0.18),transparent_35%),linear-gradient(135deg,hsl(var(--background))_0%,hsl(var(--secondary)/0.35)_100%)]" />
      <div className="pointer-events-none absolute -left-24 top-10 -z-10 h-64 w-64 rounded-full bg-primary/20 blur-3xl" />
      <div className="pointer-events-none absolute -right-20 bottom-0 -z-10 h-72 w-72 rounded-full bg-blue-400/20 blur-3xl" />

      <div className="mx-auto flex w-full max-w-lg flex-col items-center justify-center gap-4">
        <div className="text-center">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-primary">JobLens AI</p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground">Welcome back</h1>
          <p className="mt-2 text-sm text-muted-foreground">Sign in to continue your job analysis workflow.</p>
        </div>

        <Card className="w-full border-primary/20 bg-card/95 shadow-xl shadow-primary/10 backdrop-blur">
          <CardHeader className="space-y-1 pb-3">
            <CardTitle className="text-xl font-semibold tracking-tight">Login to your account</CardTitle>
          <CardDescription>
            Enter your email to sign in to your account
          </CardDescription>
        </CardHeader>
        <form onSubmit={handleSignIn}>
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
              autoComplete="current-password"
              required
            />
          </div>
          {errorMessage ? (
            <p className="text-sm text-red-500" role="alert">
              {errorMessage}
            </p>
          ) : null}
          </CardContent>
        <CardFooter className="pt-1">
            <div className="flex flex-col w-full gap-4">
                <Button className="w-full" type="submit" disabled={isLoading}>
                  {isLoading ? "Signing in..." : "Sign In"}
                </Button>
                <p className="text-center text-sm text-muted-foreground">
                    Don&apos;t have an account?{" "}
                    <Link to="/signup" className="underline underline-offset-4 hover:text-primary">
                        Sign up
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
