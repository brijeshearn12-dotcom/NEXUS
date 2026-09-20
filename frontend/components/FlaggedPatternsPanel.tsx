// FlaggedPatternsPanel.tsx — Displays automated pattern flags
"use client";

export default function FlaggedPatternsPanel() {
  return (
    <section className="rounded border border-gray-700 bg-gray-800 p-3 text-sm text-gray-300">
      <p className="font-semibold text-gray-100">Flagged Patterns</p>
      <p className="mt-2 italic text-gray-500">No flags detected yet.</p>
    </section>
  );
}
