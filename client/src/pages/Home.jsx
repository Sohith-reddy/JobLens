import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Upload, FileText, Search, AlertCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { scoreJobText, scoreJobUrl, matchResume } from '@/lib/joblensApi'

const defaultReviewData = {
  sentiment: 'No Data',
  score: 0,
  summary: 'No employee reviews found for this entity.',
  pros: null,
  cons: null,
}

const defaultCompanyData = {
  isVerified: false,
  domainAge: 'Unknown',
  onlinePresence: 'Not Available',
}

function normalizeScoringResult(scoringResult) {
  if (!scoringResult) {
    return {
      verdict: 'Not Analyzed',
      score: 0,
      flags: [],
      reason: null,
    }
  }

  if (scoringResult.is_job_posting === false) {
    return {
      verdict: 'Not a Job Posting',
      score: 0,
      flags: [scoringResult.message || 'The provided content is not a job posting.'],
      reason: scoringResult.message || null,
    }
  }

  const probability = Number(scoringResult.ml_probability || 0)
  return {
    verdict: scoringResult.final_label || 'Unknown',
    score: Math.round(probability * 100),
    flags: (scoringResult.rule_hits || []).map((rule) => `${rule.rule_id}: ${rule.explanation}`),
    reason: scoringResult.final_reason || null,
  }
}

function normalizeCompanyData(urlScoringResult) {
  if (!urlScoringResult || !urlScoringResult.extraction_method) {
    return defaultCompanyData
  }

  const confidencePercent = Math.round((urlScoringResult.extraction_confidence || 0) * 100)
  return {
    isVerified: confidencePercent >= 70,
    domainAge: 'N/A',
    onlinePresence: `${urlScoringResult.extraction_method} (${confidencePercent}% confidence)`,
  }
}

function normalizeResumeData(resumeResult) {
  if (!resumeResult) {
    return {
      matchPercentage: 0,
      missingSkills: [],
    }
  }

  if (resumeResult.is_valid_job_posting === false) {
    return {
      matchPercentage: 0,
      missingSkills: [resumeResult.message || 'Resume analysis failed due to invalid job description.'],
    }
  }

  return {
    matchPercentage: resumeResult.fit_score?.overall || 0,
    missingSkills: resumeResult.fit_score?.must_have_gaps || [],
  }
}

export default function Home() {
  const navigate = useNavigate()
  const [jobDescription, setJobDescription] = useState('')
  const [jobUrl, setJobUrl] = useState('')
  const [file, setFile] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  const [errorMessage, setErrorMessage] = useState('')

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleAnalyze = async () => {
    if (!jobDescription.trim() && !jobUrl.trim()) {
      setErrorMessage('Please provide either job text or a job URL to run analysis.')
      return
    }

    setErrorMessage('')
    setIsAnalyzing(true)

    try {
      const hasText = Boolean(jobDescription.trim())
      const hasUrl = Boolean(jobUrl.trim())

      const textPromise = hasText ? scoreJobText(jobDescription.trim()) : Promise.resolve(null)
      const urlPromise = hasUrl ? scoreJobUrl(jobUrl.trim()) : Promise.resolve(null)

      const [textResult, urlResult] = await Promise.all([textPromise, urlPromise])

      const primaryScoring =
        (textResult && textResult.is_job_posting !== false && textResult) ||
        (urlResult && urlResult.score_result) ||
        textResult ||
        urlResult ||
        null

      const resumeInputDescription =
        jobDescription.trim() || urlResult?.final_extracted_text || ''

      let resumeResult = null
      if (file && resumeInputDescription) {
        resumeResult = await matchResume({
          resumeFile: file,
          jobDescription: resumeInputDescription,
          useLlm: true,
          forceReparse: false,
        })
      }

      const dashboardData = {
        scamAnalysis: normalizeScoringResult(primaryScoring),
        companyVerification: normalizeCompanyData(urlResult),
        reviews: defaultReviewData,
        resumeMatch: normalizeResumeData(resumeResult),
        apiMeta: {
          scoringTextUsed: hasText,
          scoringUrlUsed: hasUrl,
          resumeUsed: Boolean(file && resumeInputDescription),
          warnings: urlResult?.warnings || [],
        },
      }

      navigate('/dashboard', {
        state: {
          analysisData: dashboardData,
        },
      })
    } catch (error) {
      setErrorMessage(error.message || 'Failed to analyze inputs. Please try again.')
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="container py-10 space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl">
          Detect Fake Jobs & Match Your Resume
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          JobLens AI uses advanced algorithms to verify job authenticity and check your fit.
        </p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Job Description Section */}
        <Card className="card-hover">
          <CardHeader>
            <CardTitle>Job Description</CardTitle>
            <CardDescription>
              Paste the job description or URL to analyze for potential scams.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="job-url">Job URL (Optional)</Label>
              <Input
                id="job-url"
                placeholder="https://linkedin.com/jobs/..."
                value={jobUrl}
                onChange={(e) => setJobUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="job-desc">Job Text</Label>
              <Textarea
                id="job-desc"
                placeholder="Paste the full job description here..."
                className="min-h-[200px]"
                value={jobDescription}
                onChange={(e) => setJobDescription(e.target.value)}
              />
            </div>
          </CardContent>
        </Card>

        {/* Resume Upload Section */}
        <Card className="card-hover">
          <CardHeader>
            <CardTitle>Your Resume</CardTitle>
            <CardDescription>
              Upload your resume (PDF/DOCX) to check compatibility.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col items-center justify-center border-2 border-dashed rounded-lg p-12 hover:bg-muted/50 transition-colors cursor-pointer relative">
              <Input 
                type="file" 
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer" 
                onChange={handleFileChange}
                accept=".pdf,.doc,.docx"
              />
              <div className="flex flex-col items-center gap-2 text-center">
                {file ? (
                  <>
                    <FileText className="h-10 w-10 text-primary" />
                    <span className="font-medium text-lg">{file.name}</span>
                    <span className="text-sm text-muted-foreground">{(file.size / 1024 / 1024).toFixed(2)} MB</span>
                  </>
                ) : (
                  <>
                    <Upload className="h-10 w-10 text-muted-foreground" />
                    <span className="font-medium text-lg">Click to Upload Resume</span>
                    <span className="text-sm text-muted-foreground">or drag and drop here</span>
                  </>
                )}
              </div>
            </div>
            
            <div className="bg-blue-50 dark:bg-blue-950/30 p-4 rounded-md flex gap-3 text-sm text-blue-700 dark:text-blue-300">
              <AlertCircle className="h-5 w-5 shrink-0" />
              <p>Your data is processed securely and not stored permanently.</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {errorMessage && (
        <div className="mx-auto max-w-3xl rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
          {errorMessage}
        </div>
      )}

      <div className="flex justify-center pt-6">
        <Button 
          size="lg" 
          className="text-lg px-8 py-6 w-full md:w-auto" 
          onClick={handleAnalyze} 
          disabled={isAnalyzing || (!jobDescription.trim() && !jobUrl.trim())}
        >
          {isAnalyzing ? (
            <>Analyzing...</>
          ) : (
            <>
              <Search className="mr-2 h-5 w-5" /> Analyze Job & Resume
            </>
          )}
        </Button>
      </div>
    </div>
  )
}
