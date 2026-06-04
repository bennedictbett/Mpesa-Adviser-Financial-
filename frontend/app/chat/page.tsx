"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

type Message = {
  role: "user" | "assistant";
  content: string;
  sources?: string[];
  has_context?: boolean;
};

const SUGGESTED_QUESTIONS = [
  "How much did I spend last month?",
  "What do I spend most of my money on?",
  "How can I save KES 5,000 this month?",
  "What were my top 3 expenses?",
  "Am I spending more than I earn?",
  "How much did I send to family?",
];

export default function ChatPage() {
  const router = useRouter();
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef  = useRef<HTMLInputElement>(null);

  const [messages, setMessages]   = useState<Message[]>([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [hasStatement, setHasStatement] = useState(false);

  useEffect(() => {
    // Check if statement data exists in localStorage
    const raw = localStorage.getItem("statementData");
    setHasStatement(!!raw);

    // Welcome message
    setMessages([
      {
        role: "assistant",
        content: raw
          ? "I've loaded your M-Pesa statement. Ask me anything about your spending, savings, or finances."
          : "Hello! I'm your M-Pesa Financial Advisor. You can ask me general questions about M-Pesa fees and CBK regulations, or upload your statement for personalised advice.",
        sources: [],
      },
    ]);
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  async function sendMessage(question: string) {
    if (!question.trim() || loading) return;

    const userMessage: Message = { role: "user", content: question };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const history = messages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      // Use /analyse if statement is loaded, /chat for general questions
      const endpoint = hasStatement ? "/api/v1/analyse" : "/api/v1/chat";

      const res = await fetch(`${API}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, history }),
      });

      if (!res.ok) throw new Error("Request failed");

      const data = await res.json();

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.answer,
          sources: data.sources || [],
          has_context: data.has_context,
        },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Sorry, I couldn't reach the API. Make sure the backend is running.",
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white flex flex-col">
      {/* Grid background */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* Nav */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 border-b border-white/8 flex-shrink-0">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-2 hover:opacity-70 transition-opacity"
        >
          <div className="w-8 h-8 rounded-lg bg-[#00C45A] flex items-center justify-center">
            <span className="text-black font-black text-sm">M</span>
          </div>
          <span className="font-semibold tracking-tight">M-Pesa Advisor</span>
        </button>
        <div className="flex items-center gap-3">
          {hasStatement && (
            <button
              onClick={() => router.push("/dashboard")}
              className="text-sm text-gray-400 hover:text-white transition-colors"
            >
              ← Dashboard
            </button>
          )}
          <button
            onClick={() => router.push("/upload")}
            className="px-4 py-2 rounded-lg border border-white/10 text-white text-sm hover:bg-white/5 transition-colors"
          >
            {hasStatement ? "New statement" : "Upload statement"}
          </button>
        </div>
      </nav>

      {/* Chat area */}
      <div className="relative z-10 flex-1 overflow-y-auto px-4 py-6 max-w-3xl mx-auto w-full">

        {/* Step indicator */}
        <div className="text-center mb-8">
          <p className="text-xs text-[#00C45A] font-mono mb-1">STEP 3 OF 3 — AI ADVISOR</p>
          <p className="text-xs text-gray-600">
            {hasStatement
              ? "Asking about your uploaded statement"
              : "General M-Pesa and CBK questions"}
          </p>
        </div>

        {/* Messages */}
        <div className="space-y-4 mb-6">
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
            >
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-3 ${
                  msg.role === "user"
                    ? "bg-[#00C45A] text-black"
                    : "bg-white/5 border border-white/8 text-gray-200"
                }`}
              >
                <p className="text-sm leading-relaxed whitespace-pre-line">
                  {msg.content}
                </p>
                {msg.sources && msg.sources.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-white/10">
                    <p className="text-xs text-gray-500">
                      Sources: {msg.sources.join(", ")}
                    </p>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <div className="flex justify-start">
              <div className="bg-white/5 border border-white/8 rounded-2xl px-4 py-3">
                <div className="flex items-center gap-2">
                  <div className="w-1.5 h-1.5 rounded-full bg-[#00C45A] animate-bounce" style={{ animationDelay: "0ms" }} />
                  <div className="w-1.5 h-1.5 rounded-full bg-[#00C45A] animate-bounce" style={{ animationDelay: "150ms" }} />
                  <div className="w-1.5 h-1.5 rounded-full bg-[#00C45A] animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Suggested questions — show only at start */}
        {messages.length <= 1 && !loading && (
          <div className="mb-6">
            <p className="text-xs text-gray-600 mb-3">Suggested questions</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTED_QUESTIONS.map((q) => (
                <button
                  key={q}
                  onClick={() => sendMessage(q)}
                  className="px-3 py-1.5 rounded-lg border border-white/10 text-xs text-gray-400 hover:border-white/20 hover:text-white transition-all"
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Input bar */}
      <div className="relative z-10 border-t border-white/8 px-4 py-4 flex-shrink-0">
        <div className="max-w-3xl mx-auto flex gap-3">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && sendMessage(input)}
            placeholder={
              hasStatement
                ? "Ask about your spending, savings, or finances..."
                : "Ask about M-Pesa fees, limits, regulations..."
            }
            className="flex-1 bg-white/5 border border-white/10 rounded-xl px-4 py-3 text-sm text-white placeholder:text-gray-600 focus:outline-none focus:border-white/20 transition-colors"
          />
          <button
            onClick={() => sendMessage(input)}
            disabled={!input.trim() || loading}
            className="px-5 py-3 rounded-xl bg-[#00C45A] text-black font-bold text-sm hover:bg-[#00e066] transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Send
          </button>
        </div>
        <p className="text-center text-xs text-gray-700 mt-2">
          Answers grounded in official documents · Sources cited
        </p>
      </div>
    </main>
  );
}