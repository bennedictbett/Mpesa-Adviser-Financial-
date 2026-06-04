"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";

const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const CATEGORY_COLORS: Record<string, string> = {
  Food:      "#00C45A",
  Transport: "#3B82F6",
  Utilities: "#F59E0B",
  Airtime:   "#8B5CF6",
  Shopping:  "#EC4899",
  Banking:   "#06B6D4",
  Business:  "#F97316",
  Family:    "#14B8A6",
  Other:     "#6B7280",
};

type Summary = {
  total_transactions: number;
  total_spent: number;
  total_received: number;
  total_payments: number;
  total_withdrawals: number;
  largest_transaction: number;
  average_transaction: number;
  date_range: { from: string | null; to: string | null };
};

type Transaction = {
  recipient: string;
  amount: number;
  category: string;
  date: string | null;
  trans_type: string;
  confidence: number;
};

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary]         = useState<Summary | null>(null);
  const [categories, setCategories]   = useState<Record<string, number>>({});
  const [transactions, setTransactions] = useState<Transaction[]>([]);
  const [insight, setInsight]         = useState("");
  const [loadingInsight, setLoadingInsight] = useState(false);
  const [hasData, setHasData]         = useState(false);

  useEffect(() => {
    // Load statement data from localStorage (set by upload page)
    const raw = localStorage.getItem("statementData");
    if (raw) {
      try {
        const data = JSON.parse(raw);
        setSummary(data.summary || null);
        setCategories(data.categories || {});
        setTransactions(data.transactions || []);
        setHasData(true);
        // Auto-fetch an AI insight
        fetchInsight(data.transactions || []);
      } catch {
        setHasData(false);
      }
    }
  }, []);

  async function fetchInsight(txns: Transaction[]) {
    if (!txns.length) return;
    setLoadingInsight(true);
    try {
      const res = await fetch(`${API}/api/v1/analyse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          question: "Give me 3 short, specific insights about my spending and one actionable saving tip.",
          history: [],
        }),
      });
      if (res.ok) {
        const data = await res.json();
        setInsight(data.answer || "");
      }
    } catch {
      setInsight("");
    } finally {
      setLoadingInsight(false);
    }
  }

  const chartData = Object.entries(categories).map(([name, value]) => ({
    name,
    value: Math.round(value),
    color: CATEGORY_COLORS[name] || "#6B7280",
  }));

  const topCategory = chartData[0]?.name || "—";

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
      <nav className="relative z-10 flex items-center justify-between px-8 py-5 max-w-6xl mx-auto border-b border-white/8">
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
          <button
            onClick={() => router.push("/upload")}
            className="text-sm text-gray-400 hover:text-white transition-colors"
          >
            + New statement
          </button>
          <button
            onClick={() => router.push("/chat")}
            className="px-4 py-2 rounded-lg bg-[#00C45A] text-black text-sm font-bold hover:bg-[#00e066] transition-colors"
          >
            Ask AI advisor
          </button>
        </div>
      </nav>

      <div className="relative z-10 max-w-6xl mx-auto px-8 py-10">

        {/* No data state */}
        {!hasData && (
          <div className="flex flex-col items-center justify-center py-32 text-center">
            <div className="text-5xl mb-4">📊</div>
            <h2 className="text-2xl font-bold mb-2">No statement loaded</h2>
            <p className="text-gray-400 text-sm mb-6">
              Upload your M-Pesa statement to see your spending breakdown.
            </p>
            <button
              onClick={() => router.push("/upload")}
              className="px-6 py-3 rounded-xl bg-[#00C45A] text-black font-bold hover:bg-[#00e066] transition-colors"
            >
              Upload statement →
            </button>
          </div>
        )}

        {hasData && summary && (
          <>
            {/* Header */}
            <div className="mb-8">
              <p className="text-xs text-[#00C45A] font-mono mb-1">STEP 2 OF 3 — DASHBOARD</p>
              <h1 className="text-3xl font-black">Your spending breakdown</h1>
              {summary.date_range.from && (
                <p className="text-sm text-gray-500 mt-1">
                  {summary.date_range.from} → {summary.date_range.to}
                </p>
              )}
            </div>

            {/* Summary cards */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              {[
                {
                  label: "Total spent",
                  value: `KES ${summary.total_spent.toLocaleString()}`,
                  sub: `${summary.total_transactions} transactions`,
                  color: "text-white",
                },
                {
                  label: "Total received",
                  value: `KES ${summary.total_received.toLocaleString()}`,
                  sub: "income this period",
                  color: "text-[#00C45A]",
                },
                {
                  label: "Top category",
                  value: topCategory,
                  sub: categories[topCategory]
                    ? `KES ${Math.round(categories[topCategory]).toLocaleString()}`
                    : "—",
                  color: "text-white",
                },
                {
                  label: "Avg transaction",
                  value: `KES ${Math.round(summary.average_transaction).toLocaleString()}`,
                  sub: `largest: KES ${Math.round(summary.largest_transaction).toLocaleString()}`,
                  color: "text-white",
                },
              ].map((card) => (
                <div
                  key={card.label}
                  className="rounded-2xl border border-white/8 bg-white/3 p-5"
                >
                  <p className="text-xs text-gray-500 mb-2">{card.label}</p>
                  <p className={`text-xl font-black ${card.color} mb-1`}>
                    {card.value}
                  </p>
                  <p className="text-xs text-gray-600">{card.sub}</p>
                </div>
              ))}
            </div>

            {/* Chart + Transactions grid */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">

              {/* Spending by category chart */}
              <div className="rounded-2xl border border-white/8 bg-white/3 p-6">
                <h2 className="text-sm font-semibold text-white mb-6">
                  Spending by category
                </h2>
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={240}>
                    <BarChart data={chartData} layout="vertical">
                      <XAxis
                        type="number"
                        tick={{ fill: "#6B7280", fontSize: 10 }}
                        axisLine={false}
                        tickLine={false}
                        tickFormatter={(v) => `${(v/1000).toFixed(0)}k`}
                      />
                      <YAxis
                        type="category"
                        dataKey="name"
                        tick={{ fill: "#9CA3AF", fontSize: 11 }}
                        axisLine={false}
                        tickLine={false}
                        width={70}
                      />
                      <Tooltip
                        formatter={(value: number) => [`KES ${value.toLocaleString()}`, "Amount"]}
                        contentStyle={{
                          background: "#1a1a1a",
                          border: "1px solid rgba(255,255,255,0.1)",
                          borderRadius: "8px",
                          color: "#fff",
                          fontSize: "12px",
                        }}
                      />
                      <Bar dataKey="value" radius={[0, 4, 4, 0]}>
                        {chartData.map((entry, index) => (
                          <Cell key={index} fill={entry.color} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-gray-600 text-sm">No category data</p>
                )}
              </div>

              {/* Recent transactions */}
              <div className="rounded-2xl border border-white/8 bg-white/3 p-6">
                <h2 className="text-sm font-semibold text-white mb-4">
                  Recent transactions
                </h2>
                <div className="space-y-2 overflow-y-auto max-h-[240px]">
                  {transactions.slice(0, 10).map((t, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between py-2 border-b border-white/5 last:border-0"
                    >
                      <div className="flex items-center gap-3">
                        <div
                          className="w-2 h-2 rounded-full flex-shrink-0"
                          style={{
                            background: CATEGORY_COLORS[t.category] || "#6B7280",
                          }}
                        />
                        <div>
                          <p className="text-xs text-white font-medium truncate max-w-[140px]">
                            {t.recipient || "Unknown"}
                          </p>
                          <p className="text-xs text-gray-600">{t.category}</p>
                        </div>
                      </div>
                      <p className="text-xs font-mono text-white">
                        KES {t.amount.toLocaleString()}
                      </p>
                    </div>
                  ))}
                  {transactions.length === 0 && (
                    <p className="text-gray-600 text-sm">No transactions found</p>
                  )}
                </div>
              </div>
            </div>

            {/* AI Insights panel */}
            <div className="rounded-2xl border border-[#00C45A]/20 bg-[#00C45A]/5 p-6">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <span className="text-lg">🤖</span>
                  <h2 className="text-sm font-semibold text-white">
                    AI Advisor insights
                  </h2>
                </div>
                <button
                  onClick={() => router.push("/chat")}
                  className="text-xs text-[#00C45A] hover:underline"
                >
                  Ask more questions →
                </button>
              </div>

              {loadingInsight ? (
                <div className="flex items-center gap-3">
                  <div className="w-4 h-4 border-2 border-[#00C45A] border-t-transparent rounded-full animate-spin" />
                  <p className="text-sm text-gray-400">
                    Analysing your spending...
                  </p>
                </div>
              ) : insight ? (
                <p className="text-sm text-gray-300 leading-relaxed whitespace-pre-line">
                  {insight}
                </p>
              ) : (
                <div className="flex items-center gap-3">
                  <p className="text-sm text-gray-500">
                    Upload a statement to get personalised insights.
                  </p>
                  <button
                    onClick={() => router.push("/upload")}
                    className="text-xs text-[#00C45A] hover:underline whitespace-nowrap"
                  >
                    Upload now →
                  </button>
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </main>
  );
}