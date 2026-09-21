"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  apiRequest,
  BatchExtractionResult,
  CorpusDocument,
  SingleExtractionResult,
} from "@/lib/api";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";

export default function CorpusPage() {
  const [documents, setDocuments] = useState<CorpusDocument[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Per-document extraction loading state: map of doc_id -> boolean
  const [extractingMap, setExtractingMap] = useState<Record<string, boolean>>({});

  // Batch extraction loading state
  const [batchExtracting, setBatchExtracting] = useState<boolean>(false);
  const [batchResult, setBatchResult] = useState<BatchExtractionResult | null>(null);

  // Status message (success or alert)
  const [alertMessage, setAlertMessage] = useState<{
    type: "success" | "error" | "info";
    text: string;
  } | null>(null);

  const fetchDocuments = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    const res = await apiRequest<{
      items: CorpusDocument[];
      total: number;
      page: number;
      limit: number;
    }>("/api/documents/?limit=100");

    if (res.ok && res.data) {
      setDocuments(res.data.items || []);
      setTotalCount(res.data.total || 0);
    } else {
      setErrorMessage(res.errorMessage || "Failed to load corpus documents from backend.");
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Extract single document
  const handleExtractSingle = async (docId: string) => {
    setExtractingMap((prev) => ({ ...prev, [docId]: true }));
    setAlertMessage(null);

    const res = await apiRequest<SingleExtractionResult>(
      `/api/documents/${encodeURIComponent(docId)}/extract`,
      { method: "POST" }
    );

    setExtractingMap((prev) => ({ ...prev, [docId]: false }));

    if (res.ok && res.data) {
      const extractedCount = res.data.entities_extracted;
      setAlertMessage({
        type: "success",
        text: `Successfully extracted ${extractedCount} entities from ${docId} (Gemini used: ${res.data.gemini_used ? "Yes" : "No"}).`,
      });
      // Refresh documents list to reflect updated counts
      fetchDocuments();
    } else {
      setAlertMessage({
        type: "error",
        text: `Extraction failed for ${docId}: ${res.errorMessage || "Unknown error"}`,
      });
    }
  };

  // Extract all corpus documents
  const handleExtractAll = async () => {
    if (batchExtracting) return;
    setBatchExtracting(true);
    setAlertMessage(null);
    setBatchResult(null);

    const res = await apiRequest<BatchExtractionResult>(
      "/api/corpus/extract-all",
      { method: "POST" },
      600000 // 10 minute timeout for full batch
    );

    setBatchExtracting(false);

    if (res.ok && res.data) {
      setBatchResult(res.data);
      setAlertMessage({
        type: "success",
        text: `Batch extraction completed in ${res.data.processing_duration_sec}s: ${res.data.successful_documents}/${res.data.total_documents} documents processed, ${res.data.total_entities_extracted} entities extracted.`,
      });
      fetchDocuments();
    } else {
      setAlertMessage({
        type: "error",
        text: `Batch extraction failed: ${res.errorMessage || "Unknown error"}`,
      });
    }
  };

  const extractedDocsCount = documents.filter((d) => d.extraction_status === "extracted").length;
  const pendingDocsCount = documents.filter((d) => d.extraction_status === "pending").length;
  const totalEntitiesInCorpus = documents.reduce((acc, d) => acc + (d.entities_count || 0), 0);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header Navigation */}
      <header className="border-b border-gray-800 bg-gray-900/60 backdrop-blur px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded bg-emerald-500/20 text-emerald-400 font-bold border border-emerald-500/30 text-sm">
              NX
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">NEXUS — Corpus Center</h1>
              <p className="text-xs text-gray-400">Curated Indian Kanoon Criminal Judgments & Extraction Pipeline</p>
            </div>
          </div>
          <nav className="flex items-center gap-4 text-sm font-medium">
            <Link href="/" className="text-gray-400 hover:text-gray-200 transition">
              Home
            </Link>
            <Link href="/corpus" className="text-emerald-400 border-b-2 border-emerald-500 pb-0.5">
              Corpus
            </Link>
            <Link href="/entities" className="text-gray-400 hover:text-gray-200 transition">
              Entities
            </Link>
            <Link href="/dashboard" className="text-gray-400 hover:text-gray-200 transition">
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-6 space-y-6">
        {/* Top Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Total Documents</span>
            <div className="mt-2 text-2xl font-bold text-white">{loading ? "..." : totalCount}</div>
            <p className="mt-1 text-xs text-gray-500">Curated Indian Kanoon cases</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-xs font-medium text-emerald-400 uppercase tracking-wider">Extracted Documents</span>
            <div className="mt-2 text-2xl font-bold text-emerald-400">{loading ? "..." : extractedDocsCount}</div>
            <p className="mt-1 text-xs text-gray-500">{loading ? "..." : `${pendingDocsCount} pending extraction`}</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4">
            <span className="text-xs font-medium text-indigo-400 uppercase tracking-wider">Entities In Database</span>
            <div className="mt-2 text-2xl font-bold text-indigo-400">{loading ? "..." : totalEntitiesInCorpus.toLocaleString()}</div>
            <p className="mt-1 text-xs text-gray-500">Accused, Locations, FIRs, Cases</p>
          </div>

          <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 flex flex-col justify-between">
            <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">Batch Operations</span>
            <button
              onClick={handleExtractAll}
              disabled={batchExtracting || loading || documents.length === 0}
              className="mt-2 w-full inline-flex items-center justify-center gap-2 rounded bg-emerald-600 hover:bg-emerald-500 disabled:bg-gray-800 disabled:text-gray-500 px-3 py-2 text-xs font-semibold text-white transition shadow"
            >
              {batchExtracting ? (
                <>
                  <svg className="h-4 w-4 animate-spin text-white" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                  </svg>
                  Processing Corpus...
                </>
              ) : (
                "Extract All Documents"
              )}
            </button>
          </div>
        </div>

        {/* Inline Alerts */}
        {alertMessage && (
          <div
            className={`rounded-lg border p-4 text-sm flex items-start justify-between gap-3 ${
              alertMessage.type === "success"
                ? "border-emerald-600/40 bg-emerald-950/40 text-emerald-300"
                : alertMessage.type === "error"
                  ? "border-red-600/40 bg-red-950/40 text-red-300"
                  : "border-blue-600/40 bg-blue-950/40 text-blue-300"
            }`}
          >
            <div>
              <span className="font-semibold">{alertMessage.type === "success" ? "✓ " : "⚠ "}</span>
              {alertMessage.text}
            </div>
            <button
              onClick={() => setAlertMessage(null)}
              className="text-gray-400 hover:text-gray-200 text-xs font-bold"
            >
              ✕
            </button>
          </div>
        )}

        {/* Batch Stats Panel if available */}
        {batchResult && (
          <div className="rounded-lg border border-gray-800 bg-gray-900/70 p-4 space-y-3">
            <div className="flex items-center justify-between border-b border-gray-800 pb-2">
              <h2 className="text-sm font-semibold text-white">Batch Extraction Metrics</h2>
              <span className="text-xs text-gray-400">Duration: {batchResult.processing_duration_sec}s</span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-2 text-xs">
              {Object.entries(batchResult.entity_counts_by_type || {}).map(([type, count]) => (
                <div key={type} className="rounded bg-gray-800/60 p-2 text-center border border-gray-700/50">
                  <div className="text-gray-400 text-[10px]">{type}</div>
                  <div className="text-base font-bold text-emerald-400">{count}</div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error State */}
        {errorMessage && <ErrorState message={errorMessage} />}

        {/* Document Table */}
        {!errorMessage && (
          <div className="rounded-lg border border-gray-800 bg-gray-900/40 overflow-hidden shadow">
            <div className="flex items-center justify-between border-b border-gray-800 px-6 py-3 bg-gray-900/70">
              <h2 className="text-sm font-semibold text-white">Judgment Documents</h2>
              <div className="flex items-center gap-3">
                <span className="text-xs text-gray-400">Showing {documents.length} of {totalCount} cases</span>
                <button
                  onClick={fetchDocuments}
                  disabled={loading}
                  className="rounded border border-gray-700 bg-gray-800 hover:bg-gray-700 px-2.5 py-1 text-xs text-gray-300 transition"
                >
                  {loading ? "Refreshing..." : "Refresh"}
                </button>
              </div>
            </div>

            {loading ? (
              <div className="flex h-64 items-center justify-center text-gray-400">
                <svg className="h-6 w-6 animate-spin text-emerald-500 mr-2" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Loading corpus documents...</span>
              </div>
            ) : documents.length === 0 ? (
              <EmptyState message="No corpus documents found in the database. Use POST /api/corpus/load to ingest." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-800 bg-gray-900/90 text-gray-400 uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="px-4 py-3">Document ID</th>
                      <th className="px-4 py-3">Title / Case</th>
                      <th className="px-4 py-3">Court & Date</th>
                      <th className="px-4 py-3">Length</th>
                      <th className="px-4 py-3">Status</th>
                      <th className="px-4 py-3">Entities</th>
                      <th className="px-4 py-3 text-right">Actions</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 font-normal text-gray-300">
                    {documents.map((doc) => {
                      const isExtracting = !!extractingMap[doc.id];
                      return (
                        <tr key={doc.id} className="hover:bg-gray-800/30 transition">
                          <td className="px-4 py-3 font-mono text-emerald-400 font-medium">
                            {doc.id}
                          </td>
                          <td className="px-4 py-3 max-w-md">
                            <div className="font-medium text-white truncate" title={doc.title}>
                              {doc.title}
                            </div>
                            {doc.case_id && (
                              <div className="text-[11px] font-mono text-gray-500 mt-0.5">
                                {doc.case_id}
                              </div>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            <div className="text-gray-300">{doc.court || "Unknown Court"}</div>
                            <div className="text-[11px] text-gray-500">{doc.date || "Unknown Date"}</div>
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap text-gray-400">
                            {doc.text_length ? `${(doc.text_length / 1000).toFixed(1)}k chars` : "—"}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {doc.extraction_status === "extracted" ? (
                              <span className="inline-flex items-center gap-1 rounded bg-emerald-950/80 px-2 py-0.5 text-[11px] font-medium text-emerald-400 border border-emerald-700/50">
                                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
                                Extracted
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 rounded bg-amber-950/60 px-2 py-0.5 text-[11px] font-medium text-amber-400 border border-amber-700/50">
                                <span className="h-1.5 w-1.5 rounded-full bg-amber-400" />
                                Pending
                              </span>
                            )}
                          </td>
                          <td className="px-4 py-3 whitespace-nowrap">
                            {doc.entities_count > 0 ? (
                              <Link
                                href={`/corpus/${doc.id}/entities`}
                                className="font-semibold text-indigo-400 hover:text-indigo-300 hover:underline"
                              >
                                {doc.entities_count} entities
                              </Link>
                            ) : (
                              <span className="text-gray-600">0</span>
                            )}
                          </td>
                          <td className="px-4 py-3 text-right whitespace-nowrap">
                            <div className="inline-flex items-center gap-2">
                              <button
                                onClick={() => handleExtractSingle(doc.id)}
                                disabled={isExtracting || batchExtracting}
                                className="rounded bg-gray-800 hover:bg-gray-700 disabled:bg-gray-900 disabled:text-gray-600 border border-gray-700 px-2.5 py-1 text-[11px] font-medium text-gray-200 transition"
                              >
                                {isExtracting ? (
                                  <span className="inline-flex items-center gap-1">
                                    <svg className="h-3 w-3 animate-spin text-emerald-400" viewBox="0 0 24 24" fill="none">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                                    </svg>
                                    Extracting...
                                  </span>
                                ) : doc.extraction_status === "extracted" ? (
                                  "Re-extract"
                                ) : (
                                  "Extract"
                                )}
                              </button>

                              <Link
                                href={`/corpus/${doc.id}/entities`}
                                className="rounded border border-indigo-700/50 bg-indigo-950/60 hover:bg-indigo-900/80 px-2.5 py-1 text-[11px] font-medium text-indigo-300 transition"
                              >
                                View Entities
                              </Link>
                            </div>
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
      </main>
    </div>
  );
}
