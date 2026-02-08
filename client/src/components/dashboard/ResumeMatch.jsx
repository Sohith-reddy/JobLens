import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Briefcase } from "lucide-react"

export function ResumeMatch({ data }) {
  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Briefcase className="h-5 w-5" />
          Resume Compatibility
        </CardTitle>
        <CardDescription>Match score against job requirements.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="flex items-center justify-center">
          <div className="relative h-32 w-32 flex items-center justify-center rounded-full border-8 border-secondary">
             {/* Simple Ring Visualization */}
             <svg className="absolute inset-0 h-full w-full -rotate-90" viewBox="0 0 100 100">
                <circle 
                    cx="50" cy="50" r="46" 
                    className="fill-none stroke-primary" 
                    strokeWidth="8"
                    strokeDasharray="289" // 2 * pi * 46
                    strokeDashoffset={289 - (289 * data?.matchPercentage) / 100}
                    strokeLinecap="round"
                />
             </svg>
             <span className="text-3xl font-bold">{data?.matchPercentage}%</span>
          </div>
        </div>

        {data?.missingSkills && data.missingSkills.length > 0 && (
            <div className="space-y-2">
                <p className="text-sm font-medium">Missing Skills:</p>
                <div className="flex flex-wrap gap-2">
                    {data.missingSkills.map(skill => (
                        <span key={skill} className="px-2 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded text-xs">
                            {skill}
                        </span>
                    ))}
                </div>
            </div>
        )}
      </CardContent>
    </Card>
  )
}
