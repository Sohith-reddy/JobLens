import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { Briefcase, ShieldCheck, Clock3 } from "lucide-react"

function renderTagList(items = [], tone = "default") {
  if (!items?.length) {
    return <p className="text-sm text-muted-foreground">None</p>
  }

  const toneClass =
    tone === "danger"
      ? "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300"
      : tone === "success"
      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-300"
      : "bg-secondary text-secondary-foreground"

  return (
    <div className="flex flex-wrap gap-2">
      {items.map((item, index) => (
        <span key={`${item}-${index}`} className={`px-2 py-1 rounded text-xs ${toneClass}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

function ScoreRow({ label, value }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-sm">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value}%</span>
      </div>
      <Progress value={value} className="h-2" />
    </div>
  )
}

export function ResumeMatch({ data }) {
  const fit = data?.fit_score
  const credibility = data?.credibility_score
  const suggestions = data?.suggestions
  const timings = data?.timings_ms
  const parseWarnings = data?.resume_parse?.parse_warnings || []

  const overallFit = Number(fit?.overall || 0)
  const missingSkills = fit?.must_have_gaps || []

  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Briefcase className="h-5 w-5" />
          Resume Match Insights
        </CardTitle>
        <CardDescription>Detailed fit, credibility, and ATS guidance from your uploaded resume.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-center">
          <div className="relative h-32 w-32 flex items-center justify-center rounded-full border-8 border-secondary">
             <svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 100 100">
                <circle 
                    cx="50" cy="50" r="46" 
                    className="fill-none stroke-primary" 
                    strokeWidth="8"
                    strokeDasharray="289" // 2 * pi * 46
                    strokeDashoffset={289 - (289 * overallFit) / 100}
                    strokeLinecap="round"
                />
             </svg>
             <span className="text-3xl font-bold">{overallFit}%</span>
          </div>
        </div>

        <div className="grid gap-4">
          <ScoreRow label="Skill Match" value={Number(fit?.components?.skill_match || 0)} />
          <ScoreRow label="Experience Match" value={Number(fit?.components?.experience_match || 0)} />
          <ScoreRow label="ATS Keyword Match" value={Number(fit?.components?.ats_keyword_match || 0)} />
          <ScoreRow label="Role Alignment" value={Number(fit?.components?.role_alignment || 0)} />
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium">Must-have gaps</p>
          {renderTagList(missingSkills, "danger")}
        </div>

        {credibility && (
          <div className="rounded-md border p-4 space-y-3">
            <p className="font-medium flex items-center gap-2">
              <ShieldCheck className="h-4 w-4" /> Credibility score: {credibility.overall || 0}%
            </p>
            <div className="grid grid-cols-2 gap-3">
              <ScoreRow label="Specificity" value={Number(credibility.signals?.specificity || 0)} />
              <ScoreRow label="Consistency" value={Number(credibility.signals?.consistency || 0)} />
              <ScoreRow label="Verifiability" value={Number(credibility.signals?.verifiability || 0)} />
              <ScoreRow label="Clarity" value={Number(credibility.signals?.clarity || 0)} />
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Boosters</p>
              {renderTagList(credibility.boosters, "success")}
            </div>
            <div className="space-y-2">
              <p className="text-sm font-medium">Flags</p>
              {renderTagList(credibility.flags, "danger")}
            </div>
          </div>
        )}

        {suggestions && (
          <div className="rounded-md border p-4 space-y-3">
            <p className="font-medium">Suggestions</p>

            <div className="space-y-2">
              <p className="text-sm font-medium">Missing requirements</p>
              {renderTagList(suggestions.missing_requirements, "danger")}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium">ATS improvements</p>
              {renderTagList(suggestions.ats_improvements)}
            </div>

            <div className="space-y-2">
              <p className="text-sm font-medium">Project recommendations</p>
              {renderTagList(suggestions.project_recommendations)}
            </div>
          </div>
        )}

        {parseWarnings.length > 0 && (
          <div className="rounded-md border border-yellow-200 bg-yellow-50 p-3 text-sm text-yellow-800 dark:border-yellow-900/50 dark:bg-yellow-950/30 dark:text-yellow-200">
            <p className="font-medium">Resume parse warnings</p>
            <ul className="mt-2 list-disc list-inside space-y-1">
              {parseWarnings.map((warning, index) => (
                <li key={`${warning}-${index}`}>{warning}</li>
              ))}
            </ul>
          </div>
        )}

        {timings && (
          <div className="rounded-md border p-4 space-y-2">
            <p className="font-medium flex items-center gap-2">
              <Clock3 className="h-4 w-4" /> Processing timings
            </p>
            <div className="grid grid-cols-2 gap-2 text-sm text-muted-foreground">
              <p>PDF extract: {timings.pdf_extract || 0} ms</p>
              <p>Parse: {timings.parse || 0} ms</p>
              <p>Embedding: {timings.embed || 0} ms</p>
              <p>Scoring: {timings.scoring || 0} ms</p>
              <p>LLM: {timings.llm || 0} ms</p>
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  )
}
