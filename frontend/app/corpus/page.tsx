// corpus/page.tsx — Lists all loaded corpora
import EmptyState from "@/components/EmptyState";

export default function CorpusPage() {
  return (
    <main className="p-6">
      <h1 className="mb-4 text-xl font-bold text-gray-100">Corpus</h1>
      <EmptyState message="No corpora loaded yet. Use the fetch script to populate." />
    </main>
  );
}
