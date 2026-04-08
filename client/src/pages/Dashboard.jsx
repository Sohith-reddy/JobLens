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
    fit_score: {
      overall: 0,
      components: {
        skill_match: 0,
        experience_match: 0,
        ats_keyword_match: 0,
        role_alignment: 0,
      },
      must_have_gaps: [],
    },
    credibility_score: {
      overall: 0,
      signals: {
        specificity: 0,
        consistency: 0,
        verifiability: 0,
        clarity: 0,
      },
      boosters: [],
      flags: [],
    },
    suggestions: {
      missing_requirements: [],
      ats_improvements: [],
      project_recommendations: [],
    },
    resume_parse: {
      parse_warnings: [],
    },
    timings_ms: {
      pdf_extract: 0,
      parse: 0,
      embed: 0,
      scoring: 0,
      llm: 0,
    },
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

      <div className="grid gap-6">
        <ScamDetector data={data.scamAnalysis} />
      </div>

      <div className="grid gap-6 lg:grid-cols-10">
        <div className="lg:col-span-7">
          <ResumeMatch data={data.resumeMatch} />
        </div>
        <div className="lg:col-span-3">
          <CompanyVerifier data={data.companyVerification} />
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
