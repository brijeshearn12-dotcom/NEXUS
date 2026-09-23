// dashboard/page.tsx — Command Center: overview of the whole system
import Link from "next/link";
import KeyIndividualsPanel from "@/components/KeyIndividualsPanel";
import FlaggedPatternsPanel from "@/components/FlaggedPatternsPanel";
import ValidationBadge from "@/components/ValidationBadge";

export default function DashboardPage() {
  return (
    <main className="p-6 max-w-6xl mx-auto text-slate-100">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4 mb-6 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold text-white">
              NEXUS Command Center
            </h1>
            <ValidationBadge />
          </div>
          <p className="text-sm text-slate-400 mt-1">
            AI-Powered Criminal Network Analysis & Intelligence Platform — SIH26189GREEN
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/cases/case_100478559/graph"
            className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-xs font-bold text-white shadow hover:bg-blue-500 transition-colors"
          >
            <span>🕸️ Open Curated Demo Graph</span>
            <span>→</span>
          </Link>
        </div>
      </div>

      {/* Task 6.2 Showcase Callout */}
      <div className="mb-6 rounded-xl border border-blue-900/60 bg-gradient-to-r from-blue-950/40 via-slate-900 to-indigo-950/40 p-5 shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-400 border border-blue-800">
                TASK 6.2 READY
              </span>
              <h2 className="text-base font-bold text-white">
                One-Click Guided Analysis, What-If Simulation & Read-Only Audit Trail
              </h2>
            </div>
            <p className="mt-1 text-xs text-slate-300 max-w-2xl leading-relaxed">
              Launch the complete 4-step orchestration pipeline (<code>extract → resolve → build-graph → analysis</code>) with live step progress, examine real centrality-ranked Key Individuals, test disruptive removal simulations with before/after ranking diffs, and inspect the immutable audit log.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2">
            <Link
              href="/cases/case_100478559/graph"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 shadow transition-colors"
            >
              Launch Case Analysis &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <KeyIndividualsPanel rankedIndividuals={[]} />
        <FlaggedPatternsPanel />
      </div>
    </main>
  );
}
