import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { MessageSquare, ThumbsUp, ThumbsDown } from "lucide-react"

export function ReviewSentiment({ data }) {
  return (
    <Card className="card-hover">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <MessageSquare className="h-5 w-5" />
          Employee Sentiment
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-2xl font-bold">{data?.score}/5</span>
          <span className="text-sm px-2 py-1 bg-secondary rounded-full">{data?.sentiment}</span>
        </div>
        
        <p className="text-sm text-muted-foreground italic">"{data?.summary}"</p>

        {data?.pros && (
            <div className="flex items-start gap-2 text-sm text-green-600 dark:text-green-400">
                <ThumbsUp className="h-4 w-4 mt-0.5" />
                <p>{data.pros}</p>
            </div>
        )}
        {data?.cons && (
            <div className="flex items-start gap-2 text-sm text-red-600 dark:text-red-400">
                <ThumbsDown className="h-4 w-4 mt-0.5" />
                <p>{data.cons}</p>
            </div>
        )}
      </CardContent>
    </Card>
  )
}
