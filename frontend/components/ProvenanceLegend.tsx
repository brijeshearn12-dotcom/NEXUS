// ProvenanceLegend.tsx — Shows colour/icon coding for provenance sources
"use client";

export default function ProvenanceLegend() {
  return (
    <aside className="rounded border border-gray-700 bg-gray-800 p-3 text-xs text-gray-300">
      <p className="font-semibold text-gray-100">Provenance Legend</p>
      <ul className="mt-2 space-y-1">
        <li>🟢 Regex</li>
        <li>🔵 spaCy NER</li>
        <li>🟡 LLM Fallback</li>
        <li>⚪ Manual</li>
      </ul>
    </aside>
  );
}
