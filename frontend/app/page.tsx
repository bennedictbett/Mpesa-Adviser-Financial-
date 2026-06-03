"use client";

import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

export default function LandingPage() {
  const router = useRouter();
  const [visible, setVisible] = useState(false);
  const [apiOk, setApiOk] = useState<boolean | null>(null);

  useEffect(() => {
    setVisible(true);
    // Check if backend is alive
    fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/health`)
      .then((r) => r.json())
      .then(() => setApiOk(true))
      .catch(() => setApiOk(false));
  }, []);

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white overflow-hidden">
      {/* ── Grid background ── */}
      <div
        className="fixed inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      {/* ── Green accent blob ── */}
      <div
        className="fixed top-[-200px] right-[-100px] w-[600px] h-[600px] rounded-full pointer-events-none"
        style={{
          background:
            "radial-gradient(circle, rgba(0,196,90,0.12) 0%, transparent 70%)",
        }}
      />

      {/* ── Nav ── */}
      <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-6xl mx-auto">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[#00C45A] flex items-center justify-center">
            <span className="text-black font-black text-sm">M</span>
          </div>
          <span className="font-semibold text-white tracking-tight">
            M-Pesa Advisor
          </span>
        </div>
        <div className="flex items-center gap-3">
          {apiOk === true && (
            <span className="flex items-center gap-1.5 text-xs text-[#00C45A]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#00C45A] animate-pulse" />
              API live
            </span>
          )}
          {apiOk === false && (
            <span className="flex items-center gap-1.5 text-xs text-red-400">
              <span className="w-1.5 h-1.5 rounded-full bg-red-400" />
              API offline
            </span>
          )}
          <button
            onClick={() => router.push("/upload")}
            className="px-4 py-2 rounded-lg bg-white text-black text-sm font-medium hover:bg-gray-100 transition-colors"
          >
            Get started
          </button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="relative z-10 max-w-6xl mx-auto px-8 pt-24 pb-32">
        <div
          className="transition-all duration-700"
          style={{
            opacity: visible ? 1 : 0,
            transform: visible ? "translateY(0)" : "translateY(24px)",
          }}
        >
          {/* Tag */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border border-white/10 bg-white/5 text-xs text-gray-400 mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-[#00C45A]" />
            Powered by RAG · Groq · LangChain
          </div>

          {/* Headline */}
          <h1 className="text-6xl md:text-7xl font-black leading-[1.05] tracking-tight mb-6 max-w-3xl">
            Your M-Pesa
            <br />
            <span className="text-[#00C45A]">knows more</span>
            <br />
            than you think.
          </h1>

          {/* Subhead */}
          <p className="text-lg text-gray-400 max-w-xl mb-10 leading-relaxed">
            Upload your M-Pesa statement or paste it directly. Get an instant
            breakdown of where your money goes — and an AI advisor that tells
            you exactly how to spend better.
          </p>

          {/* CTAs */}
          <div className="flex items-center gap-4 flex-wrap">
            <button
              onClick={() => router.push("/upload")}
              className="px-6 py-3.5 rounded-xl bg-[#00C45A] text-black font-bold text-sm hover:bg-[#00e066] transition-colors"
            >
              Analyse my statement →
            </button>
            <button
              onClick={() => router.push("/chat")}
              className="px-6 py-3.5 rounded-xl border border-white/10 text-white text-sm font-medium hover:bg-white/5 transition-colors"
            >
              Ask the advisor
            </button>
          </div>
        </div>

        {/* ── Feature cards ── */}
        <div
          className="grid grid-cols-1 md:grid-cols-3 gap-4 mt-24 transition-all duration-700 delay-200"
          style={{
            opacity: visible ? 1 : 0,
            transform: visible ? "translateY(0)" : "translateY(24px)",
          }}
        >
          {[
            {
              icon: "📊",
              title: "Spending breakdown",
              desc: "Every transaction categorised — Food, Transport, Utilities, Family, and more.",
            },
            {
              icon: "🤖",
              title: "AI financial advice",
              desc: "Ask anything about your finances. Get cited, grounded answers from your actual data.",
            },
            {
              icon: "🔒",
              title: "Private by design",
              desc: "Your statement is processed locally. Nothing is stored beyond your session.",
            },
          ].map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-white/8 bg-white/3 p-6 hover:border-white/15 hover:bg-white/5 transition-all"
            >
              <div className="text-2xl mb-3">{f.icon}</div>
              <div className="font-semibold text-white mb-1.5">{f.title}</div>
              <div className="text-sm text-gray-500 leading-relaxed">
                {f.desc}
              </div>
            </div>
          ))}
        </div>

        {/* ── How it works ── */}
        <div
          className="mt-24 transition-all duration-700 delay-300"
          style={{
            opacity: visible ? 1 : 0,
            transform: visible ? "translateY(0)" : "translateY(24px)",
          }}
        >
          <h2 className="text-2xl font-bold mb-10 text-white">How it works</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {[
              { step: "01", title: "Upload", desc: "PDF or paste your M-Pesa statement text" },
              { step: "02", title: "Parse",  desc: "Every transaction extracted and categorised automatically" },
              { step: "03", title: "Analyse", desc: "Dashboard shows your spending breakdown in seconds" },
              { step: "04", title: "Advise", desc: "Ask the AI advisor anything about your finances" },
            ].map((s, i) => (
              <div key={s.step} className="relative">
                {i < 3 && (
                  <div className="hidden md:block absolute top-4 left-full w-full h-px bg-white/8 z-0" />
                )}
                <div className="relative z-10">
                  <div className="text-xs font-mono text-[#00C45A] mb-2">{s.step}</div>
                  <div className="font-semibold text-white mb-1">{s.title}</div>
                  <div className="text-sm text-gray-500 leading-relaxed">{s.desc}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* ── Bottom CTA ── */}
        <div
          className="mt-24 rounded-2xl border border-[#00C45A]/20 bg-[#00C45A]/5 p-10 text-center transition-all duration-700 delay-400"
          style={{
            opacity: visible ? 1 : 0,
            transform: visible ? "translateY(0)" : "translateY(24px)",
          }}
        >
          <h2 className="text-3xl font-black mb-3">
            Ready to understand your money?
          </h2>
          <p className="text-gray-400 mb-6 text-sm">
            No account needed. Upload your statement and get insights in under
            30 seconds.
          </p>
          <button
            onClick={() => router.push("/upload")}
            className="px-8 py-4 rounded-xl bg-[#00C45A] text-black font-bold hover:bg-[#00e066] transition-colors"
          >
            Get started for free →
          </button>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="relative z-10 border-t border-white/8 px-8 py-6 max-w-6xl mx-auto flex items-center justify-between text-xs text-gray-600">
        <span>M-Pesa Financial Advisor · Built by Benedict Bett</span>
        <span>RAG · LangChain · ChromaDB · Groq</span>
      </footer>
    </main>
  );
}