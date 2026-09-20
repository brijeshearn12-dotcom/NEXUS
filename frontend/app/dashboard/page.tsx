// dashboard/page.tsx — Command Center: overview of the whole system
import KeyIndividualsPanel from "@/components/KeyIndividualsPanel";
import FlaggedPatternsPanel from "@/components/FlaggedPatternsPanel";

export default function DashboardPage() {
  return (
    <main className="p-6">
      <h1 className="mb-6 text-2xl font-bold text-gray-100">
        NEXUS Command Center
      </h1>
      <p className="mb-6 text-sm text-gray-400">
        AI-Powered Criminal Network Analysis — SIH26189GREEN
      </p>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <KeyIndividualsPanel />
        <FlaggedPatternsPanel />
      </div>
    </main>
  );
}
