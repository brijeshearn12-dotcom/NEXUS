// EntityPanel.tsx — Side-panel showing entity details
"use client";

export default function EntityPanel() {
  return (
    <section className="rounded border border-gray-700 bg-gray-800 p-3 text-sm text-gray-300">
      <p className="font-semibold text-gray-100">Entity Details</p>
      <p className="mt-2 italic text-gray-500">Select a node to inspect.</p>
    </section>
  );
}
