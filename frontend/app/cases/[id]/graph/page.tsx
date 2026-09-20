// cases/[id]/graph/page.tsx — Criminal network graph for a case
import GraphCanvas from "@/components/GraphCanvas";
import ProvenanceLegend from "@/components/ProvenanceLegend";

interface Props {
  params: { id: string };
}

export default function CaseGraphPage({ params }: Props) {
  return (
    <main className="flex h-screen flex-col p-4">
      <h1 className="mb-3 text-lg font-bold text-gray-100">Network Graph — Case {params.id}</h1>
      <div className="flex flex-1 gap-3 overflow-hidden">
        <div className="flex-1">
          <GraphCanvas />
        </div>
        <aside className="w-56 shrink-0 space-y-3">
          <ProvenanceLegend />
        </aside>
      </div>
    </main>
  );
}
