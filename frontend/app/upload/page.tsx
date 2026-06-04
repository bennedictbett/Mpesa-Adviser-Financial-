"use client";

import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

type UploadState = "idle" | "uploading" | "parsing" | "success" | "error";

export default function UploadPage() {
  const router = useRouter();
  const fileRef = useRef<HTMLInputElement>(null);
  const [tab, setTab] = useState<"pdf" | "paste">("pdf");
  const [state, setState] = useState<UploadState>("idle");
  const [pastedText, setPastedText] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [error, setError] = useState("");

  const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

  async function handlePdfUpload(file: File) {
    if (!file.name.endsWith(".pdf")) {
      setError("Only PDF files are supported.");
      setState("error");
      return;
    }
    setState("uploading");
    setError("");
    const formData = new FormData();
    formData.append("file", file);
    try {
      const res = await fetch(`${API}/api/v1/upload`, {
        method: "POST",
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Upload failed");
      }
      const data = await res.json();
      setState("success");
      localStorage.setItem("uploadResult", JSON.stringify(data));
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (e: any) {
      setError(e.message || "Upload failed. Please try again.");
      setState("error");
    }
  }

  async function handlePasteSubmit() {
    if (pastedText.trim().length < 10) {
      setError("Please paste your M-Pesa statement text.");
      setState("error");
      return;
    }
    setState("parsing");
    setError("");
    try {
      const res = await fetch(`${API}/api/v1/parse-text`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: pastedText }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Parse failed");
      }
      const data = await res.json();
      setState("success");
      localStorage.setItem("statementData", JSON.stringify(data));
      setTimeout(() => router.push("/dashboard"), 1500);
    } catch (e: any) {
      setError(e.message || "Could not parse statement. Please try again.");
      setState("error");
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files[0];
    if (file) handlePdfUpload(file);
  }

  const isLoading = state === "uploading" || state === "parsing";

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-white">
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
      <nav className="relative z-10 flex items-center justify-between px-8 py-6 max-w-4xl mx-auto">
        <button
          onClick={() => router.push("/")}
          className="flex items-center gap-2 hover:opacity-70 transition-opacity"
        >
          <div className="w-8 h-8 rounded-lg bg-[#00C45A] flex items-center justify-center">
            <span className="text-black font-black text-sm">M</span>
          </div>
          <span className="font-semibold text-white tracking-tight">
            M-Pesa Advisor
          </span>
        </button>
        <button
          onClick={() => router.push("/chat")}
          className="text-sm text-gray-400 hover:text-white transition-colors"
        >
          Skip → Ask advisor
        </button>
      </nav>

      {/* Main content */}
      <section className="relative z-10 max-w-2xl mx-auto px-8 pt-16 pb-24">
        <div className="mb-10">
          <p className="text-xs text-[#00C45A] font-mono mb-3">STEP 1 OF 3</p>
          <h1 className="text-4xl font-black mb-3">
            Add your M-Pesa statement
          </h1>
          <p className="text-gray-400 text-sm leading-relaxed">
            Upload your statement PDF or paste the text directly from
            MySafaricom app. Your data stays private — nothing is stored
            permanently.
          </p>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-1 p-1 bg-white/5 rounded-xl mb-8 w-fit">
          {(["pdf", "paste"] as const).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setState("idle"); setError(""); }}
              className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
                tab === t
                  ? "bg-white text-black"
                  : "text-gray-400 hover:text-white"
              }`}
            >
              {t === "pdf" ? "📄 Upload PDF" : "📋 Paste text"}
            </button>
          ))}
        </div>

        {/* PDF Upload tab */}
        {tab === "pdf" && (
          <div
            onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => !isLoading && fileRef.current?.click()}
            className={`relative rounded-2xl border-2 border-dashed p-16 text-center cursor-pointer transition-all ${
              dragOver
                ? "border-[#00C45A] bg-[#00C45A]/10"
                : state === "success"
                ? "border-[#00C45A] bg-[#00C45A]/5"
                : state === "error"
                ? "border-red-500/50 bg-red-500/5"
                : "border-white/10 bg-white/3 hover:border-white/20 hover:bg-white/5"
            }`}
          >
            <input
              ref={fileRef}
              type="file"
              accept=".pdf"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) handlePdfUpload(file);
              }}
            />
            {state === "uploading" ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-10 h-10 border-2 border-[#00C45A] border-t-transparent rounded-full animate-spin" />
                <p className="text-sm text-gray-400">Uploading and processing...</p>
              </div>
            ) : state === "success" ? (
              <div className="flex flex-col items-center gap-3">
                <div className="w-12 h-12 rounded-full bg-[#00C45A]/20 flex items-center justify-center">
                  <span className="text-2xl">✓</span>
                </div>
                <p className="text-sm text-[#00C45A] font-medium">
                  Upload successful — redirecting to dashboard...
                </p>
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3">
                <div className="w-14 h-14 rounded-2xl border border-white/10 bg-white/5 flex items-center justify-center text-2xl mb-2">
                  📄
                </div>
                <p className="text-white font-medium">
                  Drop your PDF here or click to browse
                </p>
                <p className="text-xs text-gray-500">
                  M-Pesa statement PDF · Max 10MB
                </p>
              </div>
            )}
          </div>
        )}

        {/* Paste text tab */}
        {tab === "paste" && (
          <div className="space-y-4">
            <div className="rounded-2xl border border-white/10 bg-white/3 overflow-hidden">
              <div className="px-4 py-3 border-b border-white/8 flex items-center justify-between">
                <span className="text-xs text-gray-500 font-mono">
                  M-Pesa statement text
                </span>
                {pastedText && (
                  <button
                    onClick={() => setPastedText("")}
                    className="text-xs text-gray-600 hover:text-gray-400"
                  >
                    Clear
                  </button>
                )}
              </div>
              <textarea
                value={pastedText}
                onChange={(e) => {
                  setPastedText(e.target.value);
                  setState("idle");
                  setError("");
                }}
                placeholder={`Paste your M-Pesa statement here...\n\nExample:\nRJK81ABCDE  01/05/2026  Customer Transfer to JOHN KAMAU  -850.00  12,450.00`}
                className="w-full h-56 bg-transparent px-4 py-4 text-sm text-gray-300 placeholder:text-gray-700 resize-none focus:outline-none font-mono leading-relaxed"
              />
            </div>

            {state === "success" ? (
              <div className="rounded-xl bg-[#00C45A]/10 border border-[#00C45A]/20 px-4 py-3 flex items-center gap-3">
                <span className="text-[#00C45A]">✓</span>
                <p className="text-sm text-[#00C45A]">
                  Parsed successfully — redirecting to dashboard...
                </p>
              </div>
            ) : (
              <button
                onClick={handlePasteSubmit}
                disabled={isLoading || pastedText.trim().length < 10}
                className="w-full py-3.5 rounded-xl bg-[#00C45A] text-black font-bold text-sm hover:bg-[#00e066] transition-colors disabled:opacity-40 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {state === "parsing" ? (
                  <>
                    <div className="w-4 h-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                    Parsing statement...
                  </>
                ) : (
                  "Analyse my statement →"
                )}
              </button>
            )}
          </div>
        )}

        {/* Error message */}
        {state === "error" && error && (
          <div className="mt-4 rounded-xl bg-red-500/10 border border-red-500/20 px-4 py-3">
            <p className="text-sm text-red-400">{error}</p>
          </div>
        )}

        {/* Tips */}
        <div className="mt-10 rounded-2xl border border-white/8 bg-white/2 p-6">
          <p className="text-xs font-medium text-gray-500 mb-4 uppercase tracking-wider">
            Where to find your statement
          </p>
          <div className="space-y-3">
            {[
              {
                icon: "📱",
                title: "MySafaricom App",
                desc: "M-Pesa → Statement → Download or copy text",
              },
              {
                icon: "💬",
                title: "SMS/USSD",
                desc: "Dial *334# → My Account → Mini Statement → copy and paste",
              },
              {
                icon: "📧",
                title: "Email statement",
                desc: "Request via M-Pesa → Statement → Email → download the PDF",
              },
            ].map((tip) => (
              <div key={tip.title} className="flex gap-3">
                <span className="text-lg">{tip.icon}</span>
                <div>
                  <p className="text-sm text-white font-medium">{tip.title}</p>
                  <p className="text-xs text-gray-500">{tip.desc}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}