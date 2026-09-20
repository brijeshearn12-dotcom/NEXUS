// ReasoningTrailPanel.tsx — Displays the reasoning trail for an extraction
"use client";

export default function ReasoningTrailPanel() {
  return (
    <section className="rounded border border-gray-700 bg-gray-800 p-3 text-xs text-gray-300">
      <p className="font-semibold text-gray-100">Reasoning Trail</p>
      <p className="mt-2 italic text-gray-500">No entity selected.</p>
    </section>
  );
}
