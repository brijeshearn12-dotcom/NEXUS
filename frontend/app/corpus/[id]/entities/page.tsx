// corpus/[id]/entities/page.tsx — Entity list for a specific corpus document
import EmptyState from "@/components/EmptyState";

interface Props {
  params: { id: string };
}

export default function CorpusEntitiesPage({ params }: Props) {
  return (
    <main className="p-6">
      <h1 className="mb-4 text-xl font-bold text-gray-100">Entities — Corpus {params.id}</h1>
      <EmptyState message="Entity extraction not yet run." />
    </main>
  );
}
