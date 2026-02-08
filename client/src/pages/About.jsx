import { motion } from "framer-motion"
import { Button } from "@/components/ui/button"
import { Link } from "react-router-dom"
import { ShieldCheck, Target, Users, Zap } from "lucide-react"

export default function About() {
  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { 
        opacity: 1,
        transition: { staggerChildren: 0.3 }
    }
  }

  const itemVariants = {
    hidden: { y: 20, opacity: 0 },
    visible: { y: 0, opacity: 1, transition: { duration: 0.6 } }
  }

  return (
    <div className="overflow-hidden">
      <section className="relative h-[60vh] flex items-center justify-center bg-gradient-to-b from-background to-accent/20">
        <motion.div 
            className="container text-center space-y-6"
            initial="hidden"
            animate="visible"
            variants={containerVariants}
        >
            <motion.div variants={itemVariants} className="inline-block rounded-full bg-primary/10 px-4 py-1.5 text-sm font-medium text-primary mb-4">
                Redefining Job Security
            </motion.div>
            <motion.h1 variants={itemVariants} className="text-5xl md:text-7xl font-bold tracking-tight bg-gradient-to-r from-primary via-purple-500 to-blue-500 bg-clip-text text-transparent">
                JobLens AI
            </motion.h1>
            <motion.p variants={itemVariants} className="text-xl text-muted-foreground max-w-2xl mx-auto">
                We empower job seekers with AI-driven tools to verify companies, analyze descriptions, and land their dream jobs safely.
            </motion.p>
             <motion.div variants={itemVariants}>
                <Link to="/analyze">
                    <Button size="lg" className="rounded-full px-8 text-lg shadow-lg hover:shadow-primary/25">
                        Start Analyzing
                    </Button>
                </Link>
            </motion.div>
        </motion.div>
        
        <div className="absolute top-0 left-0 w-full h-full overflow-hidden -z-10">
            <div className="absolute top-1/4 left-1/4 w-96 h-96 bg-primary/20 rounded-full blur-[100px] animate-pulse" />
            <div className="absolute bottom-1/4 right-1/4 w-96 h-96 bg-purple-500/20 rounded-full blur-[100px] animate-pulse delay-1000" />
        </div>
      </section>

      <section className="py-24 bg-background">
        <div className="container">
            <motion.div 
                className="grid md:grid-cols-3 gap-12"
                initial={{ opacity: 0, y: 50 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.8 }}
            >
                <div className="space-y-4 text-center p-6 rounded-2xl bg-secondary/30 hover:bg-secondary/50 transition-colors">
                    <div className="mx-auto w-12 h-12 bg-primary/10 rounded-xl flex items-center justify-center text-primary">
                        <ShieldCheck className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold">Scam Detection</h3>
                    <p className="text-muted-foreground">Advanced algorithms analyze job postings for red flags, protecting you from fraud.</p>
                </div>
                <div className="space-y-4 text-center p-6 rounded-2xl bg-secondary/30 hover:bg-secondary/50 transition-colors">
                    <div className="mx-auto w-12 h-12 bg-purple-500/10 rounded-xl flex items-center justify-center text-purple-500">
                        <Target className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold">Smart Matching</h3>
                    <p className="text-muted-foreground">Our AI compares your resume against job requirements to find your perfect fit.</p>
                </div>
                <div className="space-y-4 text-center p-6 rounded-2xl bg-secondary/30 hover:bg-secondary/50 transition-colors">
                    <div className="mx-auto w-12 h-12 bg-blue-500/10 rounded-xl flex items-center justify-center text-blue-500">
                        <Zap className="w-6 h-6" />
                    </div>
                    <h3 className="text-xl font-bold">Instant Insights</h3>
                    <p className="text-muted-foreground">Get real-time feedback on company reputation and employee sentiment.</p>
                </div>
            </motion.div>
        </div>
      </section>


      <section className="py-24 border-t bg-muted/30">
        <div className="container flex flex-col md:flex-row items-center gap-12">
            <div className="md:w-1/2 space-y-6">
                <h2 className="text-4xl font-bold">Our Mission</h2>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    In a world where digital opportunities are abundant, so are the risks. JobLens AI was born from a simple idea: that every job seeker deserves to feel safe and confident in their search.
                </p>
                <p className="text-lg text-muted-foreground leading-relaxed">
                    We're building the trust layer of the employment market, one analyzed job description at a time.
                </p>
            </div>
            <div className="md:w-1/2 flex justify-center">
                <div className="relative w-full max-w-sm aspect-square bg-gradient-to-tr from-primary to-purple-500 rounded-3xl rotate-3 opacity-90 shadow-2xl flex items-center justify-center text-background">
                     <Users className="w-32 h-32" />
                </div>
            </div>
        </div>
      </section>
    </div>
  )
}
