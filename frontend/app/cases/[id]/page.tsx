// cases/[id]/page.tsx — Case detail view
import EmptyState from "@/components/EmptyState";

interface Props {
  params: { id: string };
}

export default function CaseDetailPage({ params }: Props) {
  return (
    <main className="p-6">
      <h1 className="mb-4 text-xl font-bold text-gray-100">Case {params.id}</h1>
      <EmptyState message="Case detail view — coming on Day 2." />
    </main>
  );
}
