// dashboard/page.tsx — Command Center: overview of the whole system
import Link from "next/link";
import KeyIndividualsPanel from "@/components/KeyIndividualsPanel";
import FlaggedPatternsPanel from "@/components/FlaggedPatternsPanel";

export default function DashboardPage() {
  return (
    <main className="p-6 max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-slate-800 pb-4 mb-6 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-100">
            NEXUS Command Center
          </h1>
          <p className="text-sm text-gray-400">
            AI-Powered Criminal Network Analysis — SIH26189GREEN
          </p>
        </div>

        <Link
          href="/cases/case_100478559/graph"
          className="inline-flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-500 transition-colors"
        >
          <span>🕸️ Launch Interactive Graph (Demo)</span>
          <span>→</span>
        </Link>
      </div>

      {/* Task 6.1 Interactive Graph Showcase Callout */}
      <div className="mb-6 rounded-xl border border-blue-900/60 bg-gradient-to-r from-blue-950/40 via-slate-900 to-indigo-950/40 p-5 shadow-lg">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <span className="rounded bg-blue-500/20 px-2 py-0.5 text-xs font-bold text-blue-400 border border-blue-800">
                TASK 6.1 READY
              </span>
              <h2 className="text-base font-bold text-white">
                Interactive Relationship Graph, Reasoning Trail & HITL Verification
              </h2>
            </div>
            <p className="mt-1 text-xs text-slate-300 max-w-2xl leading-relaxed">
              Explore the 225-node Madras High Court criminal conspiracy network (Case <code>case_100478559</code>). Inspect centrality-driven node sizing, entity-type color mapping, dashed synthetic edges, 6-step deterministic reasoning trails, and verify/reject entities with persistent MongoDB audit logging.
            </p>
          </div>
          <div className="shrink-0 flex items-center gap-2">
            <Link
              href="/cases/case_100478559/graph"
              className="rounded-lg bg-emerald-600 px-4 py-2 text-xs font-bold text-white hover:bg-emerald-500 shadow transition-colors"
            >
              Open Madras HC Graph (100478559) &rarr;
            </Link>
          </div>
        </div>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <KeyIndividualsPanel />
        <FlaggedPatternsPanel />
      </div>
    </main>
  );
}
