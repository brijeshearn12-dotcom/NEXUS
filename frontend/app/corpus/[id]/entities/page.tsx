"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { apiRequest, EntityItem, SingleExtractionResult } from "@/lib/api";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import ConfidenceIndicator from "@/components/ConfidenceIndicator";

const TYPE_STYLES: Record<string, string> = {
  ACCUSED: "bg-rose-950/80 text-rose-300 border-rose-700/60 font-semibold",
  PERSON: "bg-sky-950/80 text-sky-300 border-sky-700/60",
  ORGANIZATION: "bg-purple-950/80 text-purple-300 border-purple-700/60",
  LOCATION: "bg-amber-950/80 text-amber-300 border-amber-700/60",
  CASE_NUMBER: "bg-blue-950/80 text-blue-300 border-blue-700/60",
  FIR: "bg-orange-950/80 text-orange-300 border-orange-700/60",
  PHONE: "bg-teal-950/80 text-teal-300 border-teal-700/60",
  VEHICLE: "bg-emerald-950/80 text-emerald-300 border-emerald-700/60",
};

interface Props {
  params: { id: string };
}

export default function CorpusEntitiesPage({ params }: Props) {
  const docId = params.id;

  const [entities, setEntities] = useState<EntityItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [extracting, setExtracting] = useState<boolean>(false);
  const [statusNotice, setStatusNotice] = useState<string | null>(null);

  // Selected snippet modal
  const [selectedEntity, setSelectedEntity] = useState<EntityItem | null>(null);

  // Type filter
  const [selectedType, setSelectedType] = useState<string>("ALL");

  const fetchDocumentEntities = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    const typeParam = selectedType !== "ALL" ? `&entity_type=${encodeURIComponent(selectedType)}` : "";
    const res = await apiRequest<{
      total: number;
      items: EntityItem[];
    }>(`/api/entities/?document_id=${encodeURIComponent(docId)}&limit=500${typeParam}`);

    if (res.ok && res.data) {
      setEntities(res.data.items || []);
      setTotalCount(res.data.total || 0);
    } else {
      setErrorMessage(res.errorMessage || "Failed to load entities for this document.");
    }
    setLoading(false);
  }, [docId, selectedType]);

  useEffect(() => {
    fetchDocumentEntities();
  }, [fetchDocumentEntities]);

  const handleExtract = async () => {
    setExtracting(true);
    setStatusNotice(null);

    const res = await apiRequest<SingleExtractionResult>(
      `/api/documents/${encodeURIComponent(docId)}/extract`,
      { method: "POST" }
    );

    setExtracting(false);

    if (res.ok && res.data) {
      setStatusNotice(
        `Extraction complete: ${res.data.entities_extracted} entities extracted (Methods: ${Object.entries(res.data.by_method || {})
          .filter(([, v]) => v > 0)
          .map(([k, v]) => `${k}: ${v}`)
          .join(", ")}).`
      );
      fetchDocumentEntities();
    } else {
      setErrorMessage(res.errorMessage || "Extraction failed.");
    }
  };

  const typesPresent = Array.from(new Set(entities.map((e) => e.entity_type))).sort();

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/60 backdrop-blur px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/corpus"
              className="rounded bg-gray-800 hover:bg-gray-700 px-2 py-1 text-xs text-gray-300 transition"
            >
              ← Back to Corpus
            </Link>
            <div>
              <h1 className="text-base font-bold text-white flex items-center gap-2">
                Document Entities: <span className="font-mono text-indigo-400">{docId}</span>
              </h1>
              <p className="text-xs text-gray-400">{totalCount} total entities associated with this judgment</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <button
              onClick={handleExtract}
              disabled={extracting || loading}
              className="rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 disabled:text-gray-500 px-3 py-1.5 text-xs font-semibold text-white transition shadow flex items-center gap-2"
            >
              {extracting ? (
                <>
                  <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Extracting...
                </>
              ) : entities.length > 0 ? (
                "Re-run Extraction"
              ) : (
                "Run Extraction"
              )}
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-6 space-y-6">
        {/* Status Notice */}
        {statusNotice && (
          <div className="rounded-lg border border-emerald-600/40 bg-emerald-950/40 p-3 text-xs text-emerald-300">
            ✓ {statusNotice}
          </div>
        )}

        {/* Error State */}
        {errorMessage && <ErrorState message={errorMessage} />}

        {/* Filter Pills */}
        <div className="flex flex-wrap gap-2 items-center bg-gray-900/50 p-3 rounded-lg border border-gray-800">
          <span className="text-xs text-gray-400 font-medium mr-1">Filter by type:</span>
          <button
            onClick={() => setSelectedType("ALL")}
            className={`rounded px-2.5 py-1 text-xs font-medium transition border ${
              selectedType === "ALL"
                ? "bg-indigo-600 text-white border-indigo-500"
                : "bg-gray-900 text-gray-400 border-gray-800 hover:bg-gray-800"
            }`}
          >
            ALL ({totalCount})
          </button>
          {typesPresent.map((t) => (
            <button
              key={t}
              onClick={() => setSelectedType(t)}
              className={`rounded px-2.5 py-1 text-xs font-medium transition border ${
                selectedType === t
                  ? "bg-indigo-600 text-white border-indigo-500"
                  : "bg-gray-900 text-gray-400 border-gray-800 hover:bg-gray-800"
              }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Table */}
        {!errorMessage && (
          <div className="rounded-lg border border-gray-800 bg-gray-900/40 overflow-hidden shadow">
            {loading ? (
              <div className="flex h-64 items-center justify-center text-gray-400">
                <svg className="h-6 w-6 animate-spin text-indigo-500 mr-2" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Loading entities...</span>
              </div>
            ) : entities.length === 0 ? (
              <div className="p-8 text-center space-y-3">
                <EmptyState message="No entities extracted for this document yet." />
                <button
                  onClick={handleExtract}
                  className="rounded bg-emerald-600 hover:bg-emerald-500 px-4 py-2 text-xs font-semibold text-white transition"
                >
                  Run Extraction Now
                </button>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-800 bg-gray-900/90 text-gray-400 uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="px-4 py-3">Entity Name</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Method</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Verbatim Evidence Snippet</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 text-gray-300">
                    {entities.map((entity) => {
                      const typeClass = TYPE_STYLES[entity.entity_type] || "bg-gray-800 text-gray-300 border-gray-700";
                      const vStatus = entity.verification_status || "unverified";
                      return (
                        <tr key={entity.id} className="hover:bg-gray-800/30 transition">
                          <td className="px-4 py-3 max-w-xs">
                            <div className="font-semibold text-white truncate" title={entity.name}>
                              {entity.name}
                            </div>
                            {entity.aliases && entity.aliases.length > 0 && (
                              <div className="text-[10px] text-gray-500 truncate">
                                aliases: {entity.aliases.join(", ")}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`inline-block rounded px-2 py-0.5 text-[10px] border ${typeClass}`}>
                              {entity.entity_type}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className="inline-flex items-center gap-1 rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-400 border border-gray-700 capitalize">
                              <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />
                              {vStatus}
                            </span>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-[11px] text-gray-400">
                            {entity.provenance?.method || "—"}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {typeof entity.provenance?.confidence === "number" ? (
                              <ConfidenceIndicator score={entity.provenance.confidence} />
                            ) : (
                              <span className="text-gray-500">—</span>
                            )}
                          </td>
                          <td className="px-4 py-3 max-w-md">
                            {entity.evidence_snippet ? (
                              <div
                                onClick={() => setSelectedEntity(entity)}
                                className="cursor-pointer truncate text-[11px] text-gray-400 hover:text-gray-200 bg-gray-950/60 p-1 rounded border border-gray-800 font-mono"
                                title="Click to view full evidence context"
                              >
                                {entity.evidence_snippet}
                              </div>
                            ) : (
                              <span className="text-gray-600 text-[11px]">No snippet captured</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* Modal */}
        {selectedEntity && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
            <div className="w-full max-w-2xl rounded-lg border border-gray-800 bg-gray-900 p-6 shadow-2xl space-y-4">
              <div className="flex items-start justify-between border-b border-gray-800 pb-3">
                <div className="flex items-center gap-2">
                  <h3 className="text-base font-bold text-white">{selectedEntity.name}</h3>
                  <span className={`rounded px-2 py-0.5 text-[10px] border ${TYPE_STYLES[selectedEntity.entity_type] || ""}`}>
                    {selectedEntity.entity_type}
                  </span>
                </div>
                <button
                  onClick={() => setSelectedEntity(null)}
                  className="rounded p-1 text-gray-400 hover:bg-gray-800 hover:text-white"
                >
                  ✕
                </button>
              </div>

              <div className="space-y-3 text-xs">
                <div>
                  <span className="font-semibold text-gray-400 block mb-1">Verbatim Source Evidence Snippet:</span>
                  <div className="rounded border border-gray-800 bg-gray-950 p-3 font-mono text-emerald-300 leading-relaxed whitespace-pre-wrap">
                    {selectedEntity.evidence_snippet || "No snippet available."}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="rounded bg-gray-950/60 p-2 border border-gray-800">
                    <span className="text-gray-500 block text-[10px] uppercase">Extraction Method</span>
                    <span className="font-mono text-gray-200">{selectedEntity.provenance?.method || "—"}</span>
                  </div>
                  <div className="rounded bg-gray-950/60 p-2 border border-gray-800">
                    <span className="text-gray-500 block text-[10px] uppercase">Confidence</span>
                    <span className="font-mono text-gray-200">
                      {selectedEntity.provenance?.confidence ? `${Math.round(selectedEntity.provenance.confidence * 100)}%` : "—"}
                    </span>
                  </div>
                </div>
              </div>

              <div className="flex justify-end pt-3 border-t border-gray-800">
                <button
                  onClick={() => setSelectedEntity(null)}
                  className="rounded bg-gray-800 hover:bg-gray-700 px-4 py-1.5 text-xs font-medium text-gray-200"
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
