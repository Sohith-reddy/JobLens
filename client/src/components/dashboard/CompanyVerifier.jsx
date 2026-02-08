import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Building2, Globe, Shield } from "lucide-react"

export function CompanyVerifier({ data }) {
  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Building2 className="h-5 w-5" />
          Company Verification
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="p-3 bg-secondary/50 rounded-lg">
            <div className="flex items-center gap-2 mb-1 text-sm text-muted-foreground">
              <Globe className="h-4 w-4" /> Domain Age
            </div>
            <p className="font-semibold">{data?.domainAge || "Unknown"}</p>
          </div>
          <div className="p-3 bg-secondary/50 rounded-lg">
            <div className="flex items-center gap-2 mb-1 text-sm text-muted-foreground">
              <Shield className="h-4 w-4" /> Trust Score
            </div>
            <p className="font-semibold">{data?.onlinePresence || "N/A"}</p>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 border rounded-md">
          <div className={`h-3 w-3 rounded-full ${data?.isVerified ? 'bg-green-500' : 'bg-gray-300'}`} />
          <span className="font-medium">
            {data?.isVerified ? "Verified Business Entity" : "Unverified Entity"}
          </span>
        </div>
      </CardContent>
    </Card>
  )
}
