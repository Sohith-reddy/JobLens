import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { AlertTriangle, CheckCircle, XCircle } from "lucide-react"

export function ScamDetector({ data }) {
  const isSafe = data?.score < 30
  const isSuspicious = data?.score >= 30 && data?.score < 70
  
  let statusColor = "text-green-500"
  let StatusIcon = CheckCircle
  if (isSuspicious) {
    statusColor = "text-yellow-500"
    StatusIcon = AlertTriangle
  } else if (!isSafe) {
    statusColor = "text-red-500"
    StatusIcon = XCircle
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <StatusIcon className={`h-6 w-6 ${statusColor}`} />
          Fraud Verdict
        </CardTitle>
        <CardDescription>AI-driven analysis of job posting authenticity.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <span className="font-semibold text-lg">Verdict:</span>
            <span className={`font-bold text-xl ${statusColor}`}>{data?.verdict}</span>
          </div>
          
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span>Risk Score</span>
              <span>{data?.score}%</span>
            </div>
            <div className="h-2 w-full rounded-full bg-secondary">
              <div 
                className={`h-2 rounded-full ${isSafe ? 'bg-green-500' : isSuspicious ? 'bg-yellow-500' : 'bg-red-500'}`} 
                style={{ width: `${data?.score}%` }}
              />
            </div>
          </div>

          {data?.flags && data.flags.length > 0 && (
            <div className="rounded-md border p-3 bg-muted/50">
              <p className="text-sm font-medium mb-2">Red Flags Detected:</p>
              <ul className="list-disc list-inside text-sm text-muted-foreground space-y-1">
                {data.flags.map((flag, i) => (
                  <li key={i}>{flag}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  )
}
