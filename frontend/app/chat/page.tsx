"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
};

const SUGGESTED_QUESTIONS = [
  "How much did I spend last month?",
  "What do I spend most of my money on?",
  "How can I save KES 5,000 this month?",
  "Am I over budget on any category?",
  "How much did I spend on Transport this month?",
];

export default function ChatPage() {
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);

  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);

  useEffect(() => {
    const id = localStorage.getItem("sessionId");
    if (!id) {
      // backend/ has no general, statement-less chat mode — send them
      // to upload a statement first rather than degrade to a different kind of chatbot.
      router.push("/upload");
      return;
    }
    setSessionId(id);
    setMessages([
      {
        role: "assistant",
        content: "I've loaded your M-Pesa statement. Ask me anything about your spending, savings, or budget.",
      },
    ]);
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(question: string) {
    if (!question.trim() || loading || !sessionId) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setLoading(true);

    try {
      const res = await fetch(`${API}/api/v1/${sessionId}/ask`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });

      if (!res.ok) throw new Error("Request failed");

      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.answer }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Sorry, I couldn't reach the API. Make sure the backend is running." },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  if (!sessionId) return null; // redirecting to /upload

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-white/8 flex-shrink-0">
        <button onClick={() => router.push("/")} className="flex items-center gap-2 hover:opacity-70 transition-opacity">
          <div className="w-8 h-8 rounded-lg bg-[#00C45A] flex items-center justify-center">
            <span className="text-black font-black text-sm">M</span>
          </div>
          <span className="font-semibold tracking-tight">M-Pesa Advisor</span>
        </button>
        <button onClick={() => router.push("/dashboard")} className="text-sm text-gray-400 hover:text-white transition-colors">
          ← Dashboard
        </button>
      </nav>

      <div className="relative z-10 flex-1 overflow-y-auto px-8 py-6 max-w-3xl mx-auto w-full">
        {messages.map((m, i) => (
          <div key={i} className={`mb-4 flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
            <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm ${
              m.role === "user" ? "bg-[#00C45A] text-black" : "bg-white/5 text-gray-200"
            }`}>
              {m.content}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start mb-4">
            <div className="bg-white/5 rounded-2xl px-4 py-3">
              <div className="w-4 h-4 border-2 border-[#00C45A] border-t-transparent rounded-full animate-spin" />
            </div>
          </div>
        )}
        {messages.length === 1 && (
          <div className="flex flex-wrap gap-2 mt-6">
            {SUGGESTED_QUESTIONS.map((q) => (
              <button
                key={q}
                onClick={() => sendMessage(q)}
                className="text-xs px-3 py-2 rounded-lg border border-white/10 text-gray-400 hover:text-white hover:border-white/20 transition-colors"
              >
                {q}
              </button>
            ))}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="relative z-10 border-t border-white/8 px-8 py-4">
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            placeholder="Ask about your spending..."
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-[#00C45A]/50"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={loading || !input.trim()}
            className="px-5 py-3 rounded-xl bg-[#00C45A] text-black font-bold text-sm disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </main>
  );
}