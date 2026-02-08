import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from '@/components/ui/card'
import { Upload, FileText, Search, AlertCircle } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export default function Home() {
  const navigate = useNavigate()
  const [jobDescription, setJobDescription] = useState('')
  const [file, setFile] = useState(null)
  const [isAnalyzing, setIsAnalyzing] = useState(false)

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      setFile(e.target.files[0])
    }
  }

  const handleAnalyze = () => {
    setIsAnalyzing(true)
    // Simulate API call
    setTimeout(() => {
      setIsAnalyzing(false)
      navigate('/dashboard')
    }, 2000)
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
              <Input id="job-url" placeholder="https://linkedin.com/jobs/..." />
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

      <div className="flex justify-center pt-6">
        <Button 
          size="lg" 
          className="text-lg px-8 py-6 w-full md:w-auto" 
          onClick={handleAnalyze} 
          disabled={!jobDescription && !file}
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
