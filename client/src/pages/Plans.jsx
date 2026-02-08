import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { Check, Info } from "lucide-react"
import { cn } from "@/lib/utils"

export default function Plans() {
  const [isAnnual, setIsAnnual] = useState(false)

  const plans = [
    {
      name: "Free",
      description: "Essential tools for job seekers.",
      price: "0",
      features: [
        "3 Resume Scans per month",
        "Basic Scam Detection",
        "Community Support",
        "Limited Job History"
      ]
    },
    {
        name: "Pro",
        description: "Advanced analytics for serious candidates.",
        price: isAnnual ? "9" : "12",
        popular: true,
        features: [
          "Unlimited Resume Scans",
          "Advanced AI Matching",
          "Priority Scam Alerts",
          "Company Deep Dive",
          "24/7 Support"
        ]
      },
      {
        name: "Enterprise",
        description: "For recruitment agencies and teams.",
        price: isAnnual ? "49" : "59",
        features: [
          "Bulk Analysis API",
          "Team Dashboard",
          "Custom Integrations",
          "Dedicated Account Manager",
          "SLA Support"
        ]
      }
  ]

  return (
    <div className="container py-20 px-4 md:px-6">
      <div className="text-center mb-12 space-y-4">
        <h1 className="text-4xl font-bold tracking-tight lg:text-5xl bg-gradient-to-r from-primary to-purple-400 bg-clip-text text-transparent">
            Choose Your Plan
        </h1>
        <p className="text-muted-foreground text-lg max-w-2xl mx-auto">
            Unlock the full potential of JobLens AI with our flexible pricing options.
        </p>
        
        <div className="flex items-center justify-center gap-4 mt-8">
            <span className={cn("text-sm font-medium", !isAnnual && "text-primary")}>Monthly</span>
            <button 
                onClick={() => setIsAnnual(!isAnnual)}
                className="relative h-6 w-11 rounded-full bg-input transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
                <div className={cn(
                    "absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-primary shadow-sm transition-transform",
                    isAnnual ? "translate-x-5" : "translate-x-0"
                )} />
            </button>
            <span className={cn("text-sm font-medium", isAnnual && "text-primary")}>
                Yearly <span className="text-xs text-green-500 font-bold ml-1">-20%</span>
            </span>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-8 max-w-6xl mx-auto">
        {plans.map((plan) => (
            <Card key={plan.name} className={cn(
                "flex flex-col relative overflow-hidden transition-all duration-300 hover:shadow-2xl hover:scale-105",
                plan.popular ? "border-primary shadow-lg scale-105 z-10" : "border-border"
            )}>
                {plan.popular && (
                    <div className="absolute top-0 right-0 bg-primary text-primary-foreground text-xs font-bold px-3 py-1 rounded-bl-lg">
                        MOST POPULAR
                    </div>
                )}
                <CardHeader>
                    <CardTitle className="text-2xl">{plan.name}</CardTitle>
                    <CardDescription>{plan.description}</CardDescription>
                </CardHeader>
                <CardContent className="flex-1">
                    <div className="text-4xl font-bold mb-6">
                        ${plan.price}
                        <span className="text-lg font-normal text-muted-foreground">/mo</span>
                    </div>
                    <ul className="space-y-3">
                        {plan.features.map((feature) => (
                            <li key={feature} className="flex items-center gap-2 text-sm">
                                <Check className="h-4 w-4 text-green-500" />
                                {feature}
                            </li>
                        ))}
                    </ul>
                </CardContent>
                <CardFooter>
                    <Button className={cn("w-full", plan.popular ? "bg-primary" : "bg-secondary text-secondary-foreground hover:bg-secondary/80")}>
                        {plan.name === "Enterprise" ? "Contact Sales" : "Get Started"}
                    </Button>
                </CardFooter>
            </Card>
        ))}
      </div>
    </div>
  )
}
