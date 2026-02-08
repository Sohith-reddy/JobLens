import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { MessageCircle, X, Send } from "lucide-react"
import { cn } from "@/lib/utils"

export function ChatWidget() {
  const [isOpen, setIsOpen] = useState(false)
  const [messages, setMessages] = useState([
    { id: 1, text: "Hi! How can I help you check a job today?", sender: "bot" }
  ])
  const [input, setInput] = useState("")

  const toggleChat = () => setIsOpen(!isOpen)

  const handleSend = () => {
    if (!input.trim()) return
    
    setMessages([...messages, { id: Date.now(), text: input, sender: "user" }])
    setInput("")
    
    // Simulate bot response
    setTimeout(() => {
        setMessages(prev => [...prev, { 
            id: Date.now() + 1, 
            text: "I'm a demo bot. I can't analyze real jobs yet, but the main dashboard can!", 
            sender: "bot" 
        }])
    }, 1000)
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 flex flex-col items-end gap-2">
      {/* Chat Window */}
      <div
        className={cn(
          "transition-all duration-300 ease-in-out origin-bottom-right",
          isOpen 
            ? "scale-100 opacity-100 w-[350px]" 
            : "scale-0 opacity-0 w-0 h-0 overflow-hidden"
        )}
      >
        <Card className="border-primary/20 shadow-xl">
            <CardHeader className="bg-primary text-primary-foreground rounded-t-lg p-4 flex flex-row items-center justify-between space-y-0">
                <CardTitle className="text-base flex items-center gap-2">
                    <MessageCircle className="h-5 w-5" /> JobLens Assistant
                </CardTitle>
                <Button variant="ghost" size="icon" className="h-8 w-8 hover:bg-primary-foreground/20 text-primary-foreground" onClick={toggleChat}>
                    <X className="h-4 w-4" />
                </Button>
            </CardHeader>
            <CardContent className="h-[300px] p-4 overflow-y-auto space-y-4">
                {messages.map((msg) => (
                    <div 
                        key={msg.id} 
                        className={cn(
                            "max-w-[80%] rounded-2xl px-4 py-2 text-sm",
                            msg.sender === "user" 
                                ? "ml-auto bg-primary text-primary-foreground rounded-br-none" 
                                : "bg-muted text-foreground rounded-bl-none"
                        )}
                    >
                        {msg.text}
                    </div>
                ))}
            </CardContent>
            <CardFooter className="p-3 border-t">
                <form 
                    className="flex w-full gap-2" 
                    onSubmit={(e) => { e.preventDefault(); handleSend(); }}
                >
                    <Input 
                        placeholder="Type a message..." 
                        value={input} 
                        onChange={(e) => setInput(e.target.value)}
                        className="flex-1"
                    />
                    <Button type="submit" size="icon" disabled={!input.trim()}>
                        <Send className="h-4 w-4" />
                    </Button>
                </form>
            </CardFooter>
        </Card>
      </div>

      {/* Floating Action Button */}
      <Button
        size="icon"
        className={cn(
            "h-14 w-14 rounded-full shadow-2xl transition-all duration-300 hover:scale-110 hover:shadow-primary/50",
            isOpen ? "bg-destructive text-destructive-foreground rotate-90" : "bg-primary text-primary-foreground"
        )}
        onClick={toggleChat}
      >
        {isOpen ? <X className="h-6 w-6" /> : <MessageCircle className="h-6 w-6" />}
        <span className="sr-only">Toggle Chat</span>
      </Button>
    </div>
  )
}
