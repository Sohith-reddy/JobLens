import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"
import { useEffect, useState } from "react"
import { getSystemHealth, getDetectionRules } from "@/lib/joblensApi"

export default function Docs() {
    const [health, setHealth] = useState(null)
    const [rulesResponse, setRulesResponse] = useState(null)
    const [apiError, setApiError] = useState("")
    const [activeSection, setActiveSection] = useState("introduction")

  const sections = [
    { id: "introduction", title: "Introduction" },
    // { id: "codebase", title: "Codebase" },
    // { id: "api-status", title: "API Status" },
    { id: "features", title: "Key Features" },
    { id: "usage", title: "How to Use" },
    { id: "privacy", title: "Privacy & Safety" },
  ]

    useEffect(() => {
        let isMounted = true

        async function loadApiDocsData() {
            try {
                const [healthData, rulesData] = await Promise.all([
                    getSystemHealth(),
                    getDetectionRules(),
                ])

                if (!isMounted) {
                    return
                }

                setHealth(healthData)
                setRulesResponse(rulesData)
            } catch (error) {
                if (!isMounted) {
                    return
                }
                setApiError(error.message || "Failed to load API metadata.")
            }
        }

        loadApiDocsData()

        return () => {
            isMounted = false
        }
    }, [])

    useEffect(() => {
        const sectionIds = sections.map((section) => section.id)
        const sectionElements = sectionIds
            .map((id) => document.getElementById(id))
            .filter(Boolean)

        if (!sectionElements.length) {
            return
        }

        const observer = new IntersectionObserver(
            (entries) => {
                const visibleEntries = entries
                    .filter((entry) => entry.isIntersecting)
                    .sort((a, b) => b.intersectionRatio - a.intersectionRatio)

                if (visibleEntries.length > 0) {
                    setActiveSection(visibleEntries[0].target.id)
                }
            },
            {
                root: null,
                rootMargin: "-30% 0px -55% 0px",
                threshold: [0.1, 0.3, 0.6],
            }
        )

        sectionElements.forEach((element) => observer.observe(element))

        return () => {
            sectionElements.forEach((element) => observer.unobserve(element))
            observer.disconnect()
        }
    }, [sections])

  return (
    <div className="container py-10 flex flex-col md:flex-row gap-8">
      <aside className="md:w-64 flex-shrink-0 hidden md:block">
        <div className="sticky top-24 space-y-4">
            <h4 className="font-semibold text-lg">Table of Contents</h4>
            <nav className="flex flex-col space-y-1 text-sm text-muted-foreground">
                {sections.map(section => (
                    <a 
                        key={section.id} 
                        href={`#${section.id}`} 
                        className={`transition-colors block py-1 ${
                            activeSection === section.id
                                ? "text-primary font-semibold underline"
                                : "hover:text-primary hover:underline"
                        }`}
                    >
                        {section.title}
                    </a>
                ))}
            </nav>
        </div>
      </aside>

      <main className="flex-1 space-y-8 max-w-3xl">
        <section id="introduction" className="space-y-4">
            <h1 className="text-4xl font-bold tracking-tight">Documentation</h1>
            <p className="text-xl text-muted-foreground">
                Welcome to JobLens AI. This guide will help you understand how to use our tools to verify jobs and analyze your resume.
            </p>
        </section>

        {/* <section id="codebase" className="space-y-4 pt-8">
            <h2 className="text-2xl font-bold border-b pb-2">Codebase</h2>
            <p className="text-muted-foreground">
                JobLens AI is organized as a React frontend and a FastAPI backend. The frontend handles input,
                validation, and visualization, while the backend provides scoring, scraping, and resume analysis APIs.
            </p>

            <div className="grid gap-4 md:grid-cols-2">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Frontend (client)</CardTitle>
                        <CardDescription>React + Vite + Tailwind application layer</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm space-y-2 text-muted-foreground">
                        <p>• <span className="font-medium text-foreground">pages/</span>: Home, Dashboard, Docs, Auth screens</p>
                        <p>• <span className="font-medium text-foreground">components/dashboard/</span>: Fraud, Company, Resume and review widgets</p>
                        <p>• <span className="font-medium text-foreground">lib/joblensApi.js</span>: API client for scoring, resume match, health, and rules</p>
                        <p>• Home uses a 2-step flow: validate posting first, then unlock resume analysis</p>
                    </CardContent>
                </Card>

                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">Backend (server)</CardTitle>
                        <CardDescription>FastAPI services and ML/rule engines</CardDescription>
                    </CardHeader>
                    <CardContent className="text-sm space-y-2 text-muted-foreground">
                        <p>• <span className="font-medium text-foreground">api/routes/</span>: REST endpoints for scoring, resume, and system metadata</p>
                        <p>• <span className="font-medium text-foreground">core/scoring/</span>: Rule + ML scoring logic</p>
                        <p>• <span className="font-medium text-foreground">core/scraping/</span>: URL extraction and fallback strategies</p>
                        <p>• <span className="font-medium text-foreground">core/matching/</span>: Resume parsing and fit/credibility scoring</p>
                    </CardContent>
                </Card>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle className="text-base">Current App Behavior</CardTitle>
                    <CardDescription>Important implementation details used in the UI</CardDescription>
                </CardHeader>
                <CardContent className="text-sm text-muted-foreground space-y-2">
                    <p>• Fraud risk score in dashboard is derived from <span className="font-medium text-foreground">extraction_confidence × 100</span>.</p>
                    <p>• Company trust score is currently shown as <span className="font-medium text-foreground">Unknown</span> until trust APIs are implemented.</p>
                    <p>• Resume uploads are restricted to <span className="font-medium text-foreground">PDF only</span> in the current frontend flow.</p>
                </CardContent>
            </Card>
        </section> */}

                {/* <section id="api-status" className="space-y-4 pt-8">
                        <h2 className="text-2xl font-bold border-b pb-2">API Status</h2>

                        {apiError && (
                            <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700 dark:border-red-900/50 dark:bg-red-950/30 dark:text-red-200">
                                {apiError}
                            </div>
                        )}

                        <div className="grid gap-4 md:grid-cols-2">
                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">System Health</CardTitle>
                                    <CardDescription>Live status from /health endpoint</CardDescription>
                                </CardHeader>
                                <CardContent className="text-sm space-y-1">
                                    <p><span className="font-medium">Status:</span> {health?.status || "Unknown"}</p>
                                    <p><span className="font-medium">Model Loaded:</span> {health?.model_loaded ? "Yes" : "No"}</p>
                                    <p><span className="font-medium">Model Path:</span> {health?.model_path || "N/A"}</p>
                                </CardContent>
                            </Card>

                            <Card>
                                <CardHeader>
                                    <CardTitle className="text-base">Detection Rules</CardTitle>
                                    <CardDescription>Live metadata from /rules endpoint</CardDescription>
                                </CardHeader>
                                <CardContent className="text-sm space-y-1">
                                    <p><span className="font-medium">Total Rules:</span> {rulesResponse?.total_rules ?? "N/A"}</p>
                                    <p><span className="font-medium">Critical Rules:</span> {(rulesResponse?.rules || []).filter((rule) => rule.severity === "CRITICAL").length}</p>
                                    <p><span className="font-medium">High Rules:</span> {(rulesResponse?.rules || []).filter((rule) => rule.severity === "HIGH").length}</p>
                                </CardContent>
                            </Card>
                        </div>

                        <Card>
                            <CardHeader>
                                <CardTitle className="text-base">Rule Catalog</CardTitle>
                                <CardDescription>Scrollable list of configured backend detection rules</CardDescription>
                            </CardHeader>
                            <CardContent>
                                <ScrollArea className="h-56 w-full rounded-md border p-3">
                                    <div className="space-y-2 text-sm">
                                        {(rulesResponse?.rules || []).map((rule) => (
                                            <div key={rule.rule_id} className="rounded border p-2">
                                                <p className="font-medium">{rule.rule_id} ({rule.severity})</p>
                                                <p className="text-muted-foreground">{rule.explanation}</p>
                                            </div>
                                        ))}
                                        {(rulesResponse?.rules || []).length === 0 && (
                                            <p className="text-muted-foreground">No rules loaded yet.</p>
                                        )}
                                    </div>
                                </ScrollArea>
                            </CardContent>
                        </Card>
                </section> */}

        <section id="features" className="space-y-4 pt-8">
            <h2 className="text-2xl font-bold border-b pb-2">Key Features</h2>
            <div className="grid gap-4 mt-4">
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">🛡️ Scam Detection</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        Our AI analyzes job descriptions for common fraud patterns, vague language, and suspicious requirements to give you a risk score.
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">🏢 Company Verification</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        We currently show extraction metadata and verification state. Trust score is displayed as Unknown until dedicated trust APIs are added.
                    </CardContent>
                </Card>
                <Card>
                    <CardHeader>
                        <CardTitle className="text-base">📝 Resume Matching</CardTitle>
                    </CardHeader>
                    <CardContent className="text-sm text-muted-foreground">
                        See how well your resume matches the job description and get suggestions for missing keywords.
                    </CardContent>
                </Card>
            </div>
        </section>

        <section id="usage" className="space-y-4 pt-8">
            <h2 className="text-2xl font-bold border-b pb-2">How to Use</h2>
            <div className="prose dark:prose-invert max-w-none">
                <ol className="list-decimal list-inside space-y-2">
                    <li><strong>Sign In</strong>: Create an account or log in to access the dashboard.</li>
                    <li><strong>Provide One Job Input</strong>: Enter either a job URL or job description text (not both).</li>
                    <li><strong>Validate Posting</strong>: Run validation first. Resume upload unlocks only when it is a valid job posting.</li>
                    <li><strong>Upload Resume (PDF)</strong>: Add your resume using PDF format.</li>
                    <li><strong>Analyze</strong>: Continue to dashboard after resume analysis completes.</li>
                    <li><strong>Review Results</strong>: Check risk score, company verification, and detailed resume-fit insights.</li>
                </ol>
            </div>
        </section>

        <section id="privacy" className="space-y-4 pt-8">
            <h2 className="text-2xl font-bold border-b pb-2">Privacy & Safety Tips</h2>
            <p className="text-muted-foreground">
                We take your privacy seriously. Your resume is processed securely and is not shared with third parties without your consent.
            </p>
            <div className="bg-yellow-500/10 border-l-4 border-yellow-500 p-4 rounded-r-md">
                <h4 className="font-bold text-yellow-500 mb-1">Safety Tip</h4>
                <p className="text-sm">
                    Never pay for a job application or equipment upfront. Legitimate employers will never ask for money during the hiring process.
                </p>
            </div>
        </section>
      </main>
    </div>
  )
}
