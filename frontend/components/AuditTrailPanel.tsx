// AuditTrailPanel.tsx — Shows immutable audit log entries
"use client";

export default function AuditTrailPanel() {
  return (
    <section className="rounded border border-gray-700 bg-gray-800 p-3 text-sm text-gray-300">
      <p className="font-semibold text-gray-100">Audit Trail</p>
      <p className="mt-2 italic text-gray-500">No audit entries yet.</p>
    </section>
  );
}
