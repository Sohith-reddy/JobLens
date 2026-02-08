import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { ScrollArea } from "@/components/ui/scroll-area"

export default function Docs() {
  const sections = [
    { id: "introduction", title: "Introduction" },
    { id: "features", title: "Key Features" },
    { id: "usage", title: "How to Use" },
    { id: "privacy", title: "Privacy & Safety" },
  ]

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
                        className="hover:text-primary hover:underline transition-colors block py-1"
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
                        We check domain age, online presence, and employee reviews to verify if a company is legitimate.
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
                    <li><strong>Paste Job Description</strong>: Copy the text from any job board (LinkedIn, Indeed, etc.) into the input field on the home page.</li>
                    <li><strong>Upload Resume</strong>: Drag and drop your PDF resume into the upload zone.</li>
                    <li><strong>Analyze</strong>: Click the "Analyze" button.</li>
                    <li><strong>Review Results</strong>: Check the Dashboard for the Risk Score, Company Verification, and Resume Match percentage.</li>
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
