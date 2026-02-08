import { Button } from "@/components/ui/button"
import { ScamDetector } from "@/components/dashboard/ScamDetector"
import { CompanyVerifier } from "@/components/dashboard/CompanyVerifier"
import { ReviewSentiment } from "@/components/dashboard/ReviewSentiment"
import { ResumeMatch } from "@/components/dashboard/ResumeMatch"
import { ArrowLeft, RefreshCw } from "lucide-react"
import { Link } from "react-router-dom"
import { useState, useEffect } from "react"

// Mock Data Analysis
const mockAnalysis = {
  scamAnalysis: {
    verdict: "High Risk / Likely Scam",
    score: 85,
    flags: ["Unusually High Salary Range", "Generic Email Domain (@gmail.com)", "Urgency and Grammatical Errors"]
  },
  companyVerification: {
    isVerified: false,
    domainAge: "5 Days",
    onlinePresence: "Not Found in Major Registries"
  },
  reviews: {
    sentiment: "No Data",
    score: 0,
    summary: "No employee reviews found for this entity.",
    pros: null,
    cons: null
  },
  resumeMatch: {
    matchPercentage: 45,
    missingSkills: ["Python (FastAPI)", "Vector Databases"]
  }
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    // Simulate loading data
    const timer = setTimeout(() => {
        setData(mockAnalysis)
        setLoading(false)
    }, 1000)
    return () => clearTimeout(timer)
  }, [])

  if (loading) {
    return (
        <div className="container py-8 flex items-center justify-center min-h-[50vh]">
            <div className="flex flex-col items-center gap-4">
                <RefreshCw className="h-8 w-8 animate-spin text-primary" />
                <p className="text-muted-foreground">Generating comprehensive analysis...</p>
            </div>
        </div>
    )
  }

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
        {/* Main Verdict - Spans 2 cols on LG */}
        <div className="lg:col-span-2">
            <ScamDetector data={data.scamAnalysis} />
        </div>

        {/* Quick Stats */}
        <div className="space-y-6">
            <CompanyVerifier data={data.companyVerification} />
            <ResumeMatch data={data.resumeMatch} />
        </div>
      </div>
      
      {/* Additional Details */}
      <div className="grid gap-6 md:grid-cols-2">
        <ReviewSentiment data={data.reviews} />
        {/* Placeholder for future detailed text analysis */}
      </div>
    </div>
  )
}
