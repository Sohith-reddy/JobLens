import { Button } from "@/components/ui/button"
import { ScamDetector } from "@/components/dashboard/ScamDetector"
import { CompanyVerifier } from "@/components/dashboard/CompanyVerifier"
import { ReviewSentiment } from "@/components/dashboard/ReviewSentiment"
import { ResumeMatch } from "@/components/dashboard/ResumeMatch"
import { ArrowLeft } from "lucide-react"
import { Link, useLocation } from "react-router-dom"

const fallbackAnalysis = {
  scamAnalysis: {
    verdict: "Not Analyzed",
    score: 0,
    flags: ["Run an analysis from the Analyze page to view API-powered results."],
    reason: null,
  },
  companyVerification: {
    isVerified: false,
    domainAge: "Unknown",
    onlinePresence: "Not Available",
  },
  reviews: {
    sentiment: "No Data",
    score: 0,
    summary: "No employee reviews found for this entity.",
    pros: null,
    cons: null
  },
  resumeMatch: {
    matchPercentage: 0,
    missingSkills: [],
  },
  apiMeta: {
    warnings: [],
  },
}

export default function Dashboard() {
  const location = useLocation()
  const data = location.state?.analysisData || fallbackAnalysis

  return (
    <div className="container py-8 space-y-6">
      <div className="flex items-center gap-4">
        <Link to="/">
            <Button variant="ghost" size="sm" className="gap-2">
                <ArrowLeft className="h-4 w-4" /> Back
            </Button>
        </Link>
        <h1 className="text-3xl font-bold tracking-tight">Analysis Report</h1>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div className="lg:col-span-2">
            <ScamDetector data={data.scamAnalysis} />
        </div>
        <div className="space-y-6">
            <CompanyVerifier data={data.companyVerification} />
            <ResumeMatch data={data.resumeMatch} />
        </div>
      </div>
      <div className="grid gap-6 md:grid-cols-2">
        <ReviewSentiment data={data.reviews} />
      </div>

      {data.scamAnalysis?.reason && (
        <div className="rounded-md border p-4 text-sm text-muted-foreground">
          <span className="font-medium text-foreground">Decision reason:</span> {data.scamAnalysis.reason}
        </div>
      )}

      {data.apiMeta?.warnings?.length > 0 && (
        <div className="rounded-md border border-yellow-200 bg-yellow-50 p-4 text-sm text-yellow-800 dark:border-yellow-900/50 dark:bg-yellow-950/30 dark:text-yellow-200">
          <p className="font-medium">Extraction warnings</p>
          <ul className="mt-2 list-disc list-inside space-y-1">
            {data.apiMeta.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
