import { useEffect, useRef, useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Upload, FileText, Search, AlertCircle, CheckCircle2, XCircle, Info } from 'lucide-react'
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
  const [isJobPosting, setIsJobPosting] = useState(false)
  const [scoringPayload, setScoringPayload] = useState(null)
  const [urlScoringPayload, setUrlScoringPayload] = useState(null)
  const [jobDescriptionForResume, setJobDescriptionForResume] = useState('')
  const [showNotJobModal, setShowNotJobModal] = useState(false)
  const [notJobMessage, setNotJobMessage] = useState('')
  const [toast, setToast] = useState({
    open: false,
    title: '',
    description: '',
    variant: 'info',
  })
  const toastTimerRef = useRef(null)

  const showToast = (title, description, variant = 'info') => {
    if (toastTimerRef.current) {
      clearTimeout(toastTimerRef.current)
    }

    setToast({
      open: true,
      title,
      description,
      variant,
    })

    toastTimerRef.current = setTimeout(() => {
      setToast((prev) => ({ ...prev, open: false }))
    }, 2800)
  }

  useEffect(() => {
    return () => {
      if (toastTimerRef.current) {
        clearTimeout(toastTimerRef.current)
      }
    }
  }, [])

  const resetAnalysisState = () => {
    setIsJobPosting(false)
    setScoringPayload(null)
    setUrlScoringPayload(null)
    setJobDescriptionForResume('')
    setFile(null)
  }

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleValidatePosting = async () => {
    const trimmedText = jobDescription.trim()
    const trimmedUrl = jobUrl.trim()

    if (!trimmedText && !trimmedUrl) {
      setErrorMessage('Please provide either job text or a job URL to run analysis.')
      return
    }

    if (trimmedText && trimmedUrl) {
      setErrorMessage('Please provide only one input at a time: either job text or job URL.')
      return
    }

    setErrorMessage('')
    setIsAnalyzing(true)
    showToast('Submitting job posting', 'Checking whether this content is a valid job posting.', 'info')

    try {
      const hasUrl = Boolean(trimmedUrl)

      let selectedResult = null
      let selectedUrlResult = null

      if (hasUrl) {
        selectedUrlResult = await scoreJobUrl(trimmedUrl)
        selectedResult = selectedUrlResult?.score_result || selectedUrlResult
        setJobDescriptionForResume(selectedUrlResult?.final_extracted_text || '')
      } else {
        selectedResult = await scoreJobText(trimmedText)
        setJobDescriptionForResume(trimmedText)
      }

      if (selectedResult?.is_job_posting === false) {
        const responseMessage =
          selectedResult?.message ||
          selectedResult?.final_reason ||
          'This content is not recognized as a job posting.'

        setIsJobPosting(false)
        setScoringPayload(null)
        setUrlScoringPayload(null)
        setNotJobMessage(responseMessage)
        setShowNotJobModal(true)
        showToast('Not a job posting', 'Please provide a valid job posting and try again.', 'error')
        return
      }

      setIsJobPosting(true)
      setScoringPayload(selectedResult)
      setUrlScoringPayload(selectedUrlResult)
      showToast('Valid job posting detected', 'Resume section is now unlocked.', 'success')

      if (!hasUrl) {
        setUrlScoringPayload(null)
      }
    } catch (error) {
      setErrorMessage(error.message || 'Failed to analyze inputs. Please try again.')
      showToast('Submission failed', error.message || 'Please try again.', 'error')
    } finally {
      setIsAnalyzing(false)
    }
  }

  const handleAnalyze = async () => {
    if (!isJobPosting || !scoringPayload) {
      setErrorMessage('Please validate a job posting before running resume analysis.')
      return
    }

    setErrorMessage('')
    setIsAnalyzing(true)
    showToast('Processing analysis', 'Preparing your dashboard insights.', 'info')

    try {
      let resumeResult = null
      if (file && jobDescriptionForResume) {
        resumeResult = await matchResume({
          resumeFile: file,
          jobDescription: jobDescriptionForResume,
          useLlm: true,
          forceReparse: false,
        })
      }

      const dashboardData = {
        scamAnalysis: normalizeScoringResult(scoringPayload),
        companyVerification: normalizeCompanyData(urlScoringPayload),
        reviews: defaultReviewData,
        resumeMatch: normalizeResumeData(resumeResult),
        apiMeta: {
          scoringTextUsed: Boolean(jobDescription.trim() && !jobUrl.trim()),
          scoringUrlUsed: Boolean(jobUrl.trim()),
          resumeUsed: Boolean(file && jobDescriptionForResume),
          warnings: urlScoringPayload?.warnings || [],
        },
      }

      navigate('/dashboard', {
        state: {
          analysisData: dashboardData,
        },
      })
    } catch (error) {
      setErrorMessage(error.message || 'Failed to analyze inputs. Please try again.')
      showToast('Analysis failed', error.message || 'Please try again.', 'error')
    } finally {
      setIsAnalyzing(false)
    }
  }

  return (
    <div className="container py-10 space-y-8">
      <div className="text-center space-y-4">
        <h1 className="text-4xl font-extrabold tracking-tight lg:text-5xl">
          Verify The Job First, Then Match Your Resume
        </h1>
        <p className="text-xl text-muted-foreground max-w-2xl mx-auto">
          Step 1 validates that your input is a real job posting. Step 2 unlocks resume matching.
        </p>
      </div>

      <div className={`grid gap-6 ${isJobPosting ? 'lg:grid-cols-2' : 'lg:grid-cols-1'}`}>
        <Card className="card-hover">
          <CardHeader>
            <CardTitle>Step 1: Job Posting Input</CardTitle>
            <CardDescription>
              Enter either job text or a job URL. We will call the matching scoring endpoint.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="job-url">Job URL</Label>
              <Input
                id="job-url"
                placeholder="https://linkedin.com/jobs/..."
                value={jobUrl}
                onChange={(e) => {
                  setJobUrl(e.target.value)
                  resetAnalysisState()
                }}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="job-desc">Job Text</Label>
              <Textarea
                id="job-desc"
                placeholder="Paste the full job description here..."
                className="min-h-[200px]"
                value={jobDescription}
                onChange={(e) => {
                  setJobDescription(e.target.value)
                  resetAnalysisState()
                }}
              />
            </div>
            {/* <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800 dark:border-emerald-900/50 dark:bg-emerald-950/30 dark:text-emerald-300">
              Resume upload stays hidden until the API confirms <span className="font-semibold">is_job_posting=true</span>.
            </div> */}
          </CardContent>
        </Card>

        {isJobPosting && (
        <Card className="card-hover">
          <CardHeader>
            <CardTitle>Step 2: Resume Upload</CardTitle>
            <CardDescription>
              Job posting verified. Upload your resume (PDF/DOCX) to check compatibility.
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
        )}
      </div>

      {errorMessage && (
        <div className="mx-auto max-w-3xl rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-300">
          {errorMessage}
        </div>
      )}

      <div className="flex flex-col md:flex-row justify-center gap-4 pt-6">
        <Button
          size="lg"
          className="text-lg px-8 py-6 w-full md:w-auto"
          onClick={handleValidatePosting}
          disabled={isAnalyzing || (!jobDescription.trim() && !jobUrl.trim())}
        >
          {isAnalyzing ? (
            <>Validating...</>
          ) : (
            <>
              <Search className="mr-2 h-5 w-5" /> Validate Job Posting
            </>
          )}
        </Button>

        {isJobPosting && (
          <Button
            size="lg"
            className="text-lg px-8 py-6 w-full md:w-auto"
            onClick={handleAnalyze}
            disabled={isAnalyzing}
          >
            {isAnalyzing ? 'Analyzing...' : 'Continue To Dashboard'}
          </Button>
        )}
      </div>

      <Dialog open={showNotJobModal} onOpenChange={setShowNotJobModal}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-red-600 dark:text-red-400">
              <XCircle className="h-5 w-5" /> Not a Job Posting
            </DialogTitle>
            <DialogDescription className="pt-2 text-sm leading-relaxed">
              {notJobMessage || 'The provided content was not identified as a job posting.'}
            </DialogDescription>
          </DialogHeader>
        </DialogContent>
      </Dialog>

      {toast.open && (
        <div className="fixed bottom-5 right-5 z-[70] w-[min(92vw,380px)] rounded-lg border bg-background p-4 shadow-xl">
          <div className="flex items-start gap-3">
            {toast.variant === 'success' && <CheckCircle2 className="h-5 w-5 text-emerald-600" />}
            {toast.variant === 'error' && <XCircle className="h-5 w-5 text-red-600" />}
            {toast.variant === 'info' && <Info className="h-5 w-5 text-blue-600" />}
            <div className="space-y-1">
              <p className="text-sm font-semibold leading-none">{toast.title}</p>
              <p className="text-sm text-muted-foreground">{toast.description}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
