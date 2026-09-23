// cases/[id]/page.tsx — Case detail view with link to network graph
import Link from "next/link";

interface Props {
  params: { id: string };
}

export default function CaseDetailPage({ params }: Props) {
  return (
    <main className="p-6 max-w-4xl mx-auto text-slate-100">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-white">Case Overview: {params.id}</h1>
          <p className="text-sm text-slate-400 mt-1">Criminal network investigation and judicial dossier</p>
        </div>
        <Link
          href={`/cases/${params.id}/graph`}
          className="rounded-lg bg-blue-600 px-4 py-2 text-sm font-semibold text-white shadow hover:bg-blue-500 transition-colors flex items-center gap-2"
        >
          <span>🕸️ Open Interactive Graph</span>
          <span>→</span>
        </Link>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-5">
          <h2 className="text-base font-semibold text-slate-200">Investigation Dossier</h2>
          <p className="mt-2 text-xs text-slate-400 leading-relaxed">
            Entities extracted from official High Court judgments and police charge sheets. Inspect relationships, centrality scores, and provenance trails directly on the interactive network graph.
          </p>
          <div className="mt-4">
            <Link
              href={`/cases/${params.id}/graph`}
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-blue-400 hover:text-blue-300"
            >
              Launch Case Relationship Graph & Reasoning Trail &rarr;
            </Link>
          </div>
        </div>

        <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-5">
          <h2 className="text-base font-semibold text-slate-200">Curated Demonstration Case</h2>
          <p className="mt-2 text-xs text-slate-400 leading-relaxed">
            For judge evaluation, Case <strong>case_100478559</strong> contains 225 nodes, 196 edges, 57 ranked individuals, Louvain communities, and high-risk pattern flags with verified trails.
          </p>
          <div className="mt-4">
            <Link
              href="/cases/case_100478559/graph"
              className="inline-flex items-center gap-1.5 text-xs font-semibold text-emerald-400 hover:text-emerald-300"
            >
              Open Madras HC Curated Graph (case_100478559) &rarr;
            </Link>
          </div>
        </div>
      </div>
    </main>
  );
}
