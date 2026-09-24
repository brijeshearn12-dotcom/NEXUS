"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { apiRequest, EntityItem } from "@/lib/api";
import EmptyState from "@/components/EmptyState";
import ErrorState from "@/components/ErrorState";
import ConfidenceIndicator from "@/components/ConfidenceIndicator";

const ENTITY_TYPES = [
  "ALL",
  "ACCUSED",
  "PERSON",
  "ORGANIZATION",
  "LOCATION",
  "CASE_NUMBER",
  "FIR",
  "PHONE",
  "VEHICLE",
];

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

function EntitiesContent() {
  const searchParams = useSearchParams();
  const initialDocId = searchParams.get("document_id") || "";

  const [entities, setEntities] = useState<EntityItem[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [loading, setLoading] = useState<boolean>(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters
  const [selectedType, setSelectedType] = useState<string>("ALL");
  const [selectedStatus, setSelectedStatus] = useState<string>("ALL");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [filterDocId, setFilterDocId] = useState<string>(initialDocId);

  // Pagination
  const [page, setPage] = useState<number>(1);
  const pageSize = 50;

  // Selected snippet modal / details
  const [selectedEntity, setSelectedEntity] = useState<EntityItem | null>(null);

  const fetchEntities = useCallback(async () => {
    setLoading(true);
    setErrorMessage(null);

    const params = new URLSearchParams();
    params.set("limit", String(pageSize));
    params.set("skip", String((page - 1) * pageSize));

    if (selectedType !== "ALL") {
      params.set("entity_type", selectedType);
    }
    if (selectedStatus !== "ALL") {
      params.set("verification_status", selectedStatus.toLowerCase());
    }
    if (searchQuery.trim()) {
      params.set("q", searchQuery.trim());
    }
    if (filterDocId.trim()) {
      params.set("document_id", filterDocId.trim());
    }

    const res = await apiRequest<{
      total: number;
      limit: number;
      skip: number;
      items: EntityItem[];
    }>(`/api/entities/?${params.toString()}`);

    if (res.ok && res.data) {
      setEntities(res.data.items || []);
      setTotalCount(res.data.total || 0);
    } else {
      setErrorMessage(res.errorMessage || "Failed to load entities from database.");
    }
    setLoading(false);
  }, [selectedType, selectedStatus, searchQuery, filterDocId, page]);

  useEffect(() => {
    fetchEntities();
  }, [fetchEntities]);

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      {/* Header Navigation */}
      <header className="border-b border-gray-800 bg-gray-900/60 backdrop-blur px-6 py-4">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded bg-indigo-500/20 text-indigo-400 font-bold border border-indigo-500/30 text-sm">
              NX
            </span>
            <div>
              <h1 className="text-lg font-bold tracking-tight text-white">NEXUS — Entity Knowledge Repository</h1>
              <p className="text-xs text-gray-400">Extracted Entities with Provenance Tracking & Evidence Verification</p>
            </div>
          </div>
          <nav className="flex items-center gap-4 text-sm font-medium">
            <Link href="/command-center" className="text-gray-400 hover:text-gray-200 transition">
              Command Center
            </Link>
            <Link href="/corpus" className="text-gray-400 hover:text-gray-200 transition">
              Corpus
            </Link>
            <Link href="/entities" className="text-indigo-400 border-b-2 border-indigo-500 pb-0.5">
              Entities
            </Link>
            <Link href="/dashboard" className="text-gray-400 hover:text-gray-200 transition">
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl p-6 space-y-6">
        {/* Verification Status Banner */}
        <div className="rounded-lg border border-amber-900/50 bg-amber-950/20 p-3 text-xs text-amber-300 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="font-semibold text-amber-400">Notice on Verification Status:</span>
            <span>
              All automatically extracted entities are initially marked as{" "}
              <strong className="text-gray-200 uppercase font-mono">Unverified</strong> until reviewed by an intelligence analyst. Do not treat unverified extractions as proven criminal facts.
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1 rounded bg-gray-800 px-2 py-0.5 text-[10px] text-gray-300 border border-gray-700">
              Unverified
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-emerald-950 px-2 py-0.5 text-[10px] text-emerald-300 border border-emerald-700">
              Confirmed
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-red-950 px-2 py-0.5 text-[10px] text-red-300 border border-red-700">
              Rejected
            </span>
          </div>
        </div>

        {/* Filter Toolbar */}
        <div className="rounded-lg border border-gray-800 bg-gray-900/50 p-4 space-y-4">
          <div className="flex flex-col md:flex-row gap-3 items-stretch md:items-center justify-between">
            {/* Search Input */}
            <div className="relative flex-1 max-w-md">
              <input
                type="text"
                placeholder="Search entity name or alias..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setPage(1);
                }}
                className="w-full rounded border border-gray-700 bg-gray-900 px-3 py-1.5 text-xs text-gray-100 placeholder-gray-500 focus:border-indigo-500 focus:outline-none"
              />
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="absolute right-2.5 top-1.5 text-xs text-gray-400 hover:text-gray-200"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Document Filter */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap">Document ID:</label>
              <input
                type="text"
                placeholder="e.g. doc_100478559"
                value={filterDocId}
                onChange={(e) => {
                  setFilterDocId(e.target.value);
                  setPage(1);
                }}
                className="rounded border border-gray-700 bg-gray-900 px-2.5 py-1 text-xs text-gray-100 placeholder-gray-600 focus:border-indigo-500 focus:outline-none w-44 font-mono"
              />
              {filterDocId && (
                <button
                  onClick={() => setFilterDocId("")}
                  className="text-xs text-gray-400 hover:text-gray-200"
                  title="Clear document filter"
                >
                  ✕
                </button>
              )}
            </div>

            {/* Status Filter */}
            <div className="flex items-center gap-2">
              <label className="text-xs text-gray-400 whitespace-nowrap">Status:</label>
              <select
                value={selectedStatus}
                onChange={(e) => {
                  setSelectedStatus(e.target.value);
                  setPage(1);
                }}
                className="rounded border border-gray-700 bg-gray-900 px-2.5 py-1 text-xs text-gray-100 focus:border-indigo-500 focus:outline-none"
              >
                <option value="ALL">All Statuses</option>
                <option value="UNVERIFIED">Unverified (Extracted)</option>
                <option value="CONFIRMED">Confirmed</option>
                <option value="REJECTED">Rejected</option>
              </select>
            </div>
          </div>

          {/* Type Filter Pills */}
          <div className="flex flex-wrap gap-1.5 items-center pt-1 border-t border-gray-800/80">
            <span className="text-[11px] font-medium text-gray-400 mr-2">Taxonomy:</span>
            {ENTITY_TYPES.map((type) => {
              const active = selectedType === type;
              return (
                <button
                  key={type}
                  onClick={() => {
                    setSelectedType(type);
                    setPage(1);
                  }}
                  className={`rounded px-2.5 py-1 text-[11px] font-medium transition border ${
                    active
                      ? "bg-indigo-600 text-white border-indigo-500 shadow"
                      : "bg-gray-900 text-gray-400 border-gray-800 hover:bg-gray-800 hover:text-gray-200"
                  }`}
                >
                  {type}
                </button>
              );
            })}
          </div>
        </div>

        {/* Error State */}
        {errorMessage && <ErrorState message={errorMessage} />}

        {/* Entities Table */}
        {!errorMessage && (
          <div className="rounded-lg border border-gray-800 bg-gray-900/40 overflow-hidden shadow">
            <div className="flex items-center justify-between border-b border-gray-800 px-6 py-3 bg-gray-900/70">
              <div className="flex items-center gap-3">
                <h2 className="text-sm font-semibold text-white">Extracted Entities</h2>
                <span className="text-xs text-gray-400 font-mono">
                  {totalCount.toLocaleString()} total matches
                </span>
              </div>
              <div className="text-xs text-gray-400">
                Page {page} of {Math.max(1, Math.ceil(totalCount / pageSize))}
              </div>
            </div>

            {loading ? (
              <div className="flex h-64 items-center justify-center text-gray-400">
                <svg className="h-6 w-6 animate-spin text-indigo-500 mr-2" viewBox="0 0 24 24" fill="none">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                </svg>
                <span>Loading entities from database...</span>
              </div>
            ) : entities.length === 0 ? (
              <EmptyState message="No entities found matching the current search and filter criteria." />
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead className="border-b border-gray-800 bg-gray-900/90 text-gray-400 uppercase tracking-wider font-semibold">
                    <tr>
                      <th className="px-4 py-3">Entity Name</th>
                      <th className="px-4 py-3">Type</th>
                      <th className="px-4 py-3">Verification</th>
                      <th className="px-4 py-3">Extraction Method</th>
                      <th className="px-4 py-3">Confidence</th>
                      <th className="px-4 py-3">Related Document</th>
                      <th className="px-4 py-3">Evidence Snippet</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-800/60 text-gray-300">
                    {entities.map((entity) => {
                      const typeClass = TYPE_STYLES[entity.entity_type] || "bg-gray-800 text-gray-300 border-gray-700";
                      const vStatus = entity.verification_status || "unverified";
                      const statusClass =
                        vStatus === "confirmed"
                          ? "bg-emerald-950/80 text-emerald-400 border-emerald-700/60"
                          : vStatus === "rejected"
                            ? "bg-red-950/80 text-red-400 border-red-700/60"
                            : "bg-gray-800/80 text-gray-400 border-gray-700";

                      return (
                        <tr key={entity.id} className="hover:bg-gray-800/30 transition">
                          {/* Name & Aliases */}
                          <td className="px-4 py-3 max-w-xs">
                            <div className="font-semibold text-white truncate" title={entity.name}>
                              {entity.name}
                            </div>
                            {entity.aliases && entity.aliases.length > 0 && (
                              <div className="text-[10px] text-gray-500 truncate" title={entity.aliases.join(", ")}>
                                aka: {entity.aliases.join(", ")}
                              </div>
                            )}
                          </td>

                          {/* Entity Type Badge */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`inline-block rounded px-2 py-0.5 text-[10px] border ${typeClass}`}>
                              {entity.entity_type}
                            </span>
                          </td>

                          {/* Verification Status */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-medium border ${statusClass}`}>
                              {vStatus === "confirmed" && <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />}
                              {vStatus === "rejected" && <span className="h-1.5 w-1.5 rounded-full bg-red-400" />}
                              {vStatus === "unverified" && <span className="h-1.5 w-1.5 rounded-full bg-gray-400" />}
                              {vStatus.charAt(0).toUpperCase() + vStatus.slice(1)}
                            </span>
                          </td>

                          {/* Extraction Method */}
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-[11px] text-gray-400">
                            {entity.provenance?.method || "model_extraction"}
                          </td>

                          {/* Confidence */}
                          <td className="px-4 py-3 whitespace-nowrap">
                            {typeof entity.provenance?.confidence === "number" ? (
                              <ConfidenceIndicator score={entity.provenance.confidence} />
                            ) : (
                              <span className="text-gray-500">—</span>
                            )}
                          </td>

                          {/* Related Document */}
                          <td className="px-4 py-3 whitespace-nowrap font-mono text-[11px]">
                            {entity.document_id ? (
                              <button
                                onClick={() => {
                                  setFilterDocId(entity.document_id!);
                                  setPage(1);
                                }}
                                className="text-indigo-400 hover:text-indigo-300 hover:underline"
                                title="Filter by this document"
                              >
                                {entity.document_id}
                              </button>
                            ) : (
                              <span className="text-gray-500">—</span>
                            )}
                          </td>

                          {/* Evidence Snippet preview */}
                          <td className="px-4 py-3 max-w-sm">
                            {entity.evidence_snippet ? (
                              <div
                                onClick={() => setSelectedEntity(entity)}
                                className="cursor-pointer truncate text-[11px] text-gray-400 hover:text-gray-200 bg-gray-950/60 p-1 rounded border border-gray-800/80 font-mono"
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

            {/* Pagination footer */}
            {!loading && totalCount > pageSize && (
              <div className="flex items-center justify-between border-t border-gray-800 px-6 py-3 bg-gray-900/60 text-xs">
                <span className="text-gray-400">
                  Showing {(page - 1) * pageSize + 1} to {Math.min(page * pageSize, totalCount)} of {totalCount} entries
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                    disabled={page === 1}
                    className="rounded border border-gray-700 bg-gray-800 px-2.5 py-1 text-gray-300 hover:bg-gray-700 disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="text-gray-400 font-mono px-2">Page {page}</span>
                  <button
                    onClick={() => setPage((p) => (p * pageSize < totalCount ? p + 1 : p))}
                    disabled={page * pageSize >= totalCount}
                    className="rounded border border-gray-700 bg-gray-800 px-2.5 py-1 text-gray-300 hover:bg-gray-700 disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Evidence Snippet Modal */}
        {selectedEntity && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 p-4">
            <div className="w-full max-w-2xl rounded-lg border border-gray-800 bg-gray-900 p-6 shadow-2xl space-y-4">
              <div className="flex items-start justify-between border-b border-gray-800 pb-3">
                <div>
                  <div className="flex items-center gap-2">
                    <h3 className="text-base font-bold text-white">{selectedEntity.name}</h3>
                    <span className={`rounded px-2 py-0.5 text-[10px] border ${TYPE_STYLES[selectedEntity.entity_type] || ""}`}>
                      {selectedEntity.entity_type}
                    </span>
                  </div>
                  <p className="text-xs text-gray-400 font-mono mt-0.5">ID: {selectedEntity.id}</p>
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
                  <div className="rounded border border-gray-800 bg-gray-950 p-3 font-mono text-emerald-300/90 leading-relaxed whitespace-pre-wrap">
                    {selectedEntity.evidence_snippet || "No contextual evidence snippet recorded."}
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-3 pt-2">
                  <div className="rounded bg-gray-950/60 p-2 border border-gray-800">
                    <span className="text-gray-500 block text-[10px] uppercase">Provenance Method</span>
                    <span className="font-mono text-gray-200">{selectedEntity.provenance?.method || "—"}</span>
                  </div>
                  <div className="rounded bg-gray-950/60 p-2 border border-gray-800">
                    <span className="text-gray-500 block text-[10px] uppercase">Confidence</span>
                    <span className="font-mono text-gray-200">
                      {selectedEntity.provenance?.confidence ? `${Math.round(selectedEntity.provenance.confidence * 100)}%` : "—"}
                    </span>
                  </div>
                  <div className="rounded bg-gray-950/60 p-2 border border-gray-800">
                    <span className="text-gray-500 block text-[10px] uppercase">Document Reference</span>
                    <span className="font-mono text-indigo-400">{selectedEntity.document_id || "—"}</span>
                  </div>
                  <div className="rounded bg-gray-950/60 p-2 border border-gray-800">
                    <span className="text-gray-500 block text-[10px] uppercase">Verification Status</span>
                    <span className="font-semibold uppercase text-amber-400">{selectedEntity.verification_status}</span>
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

export default function EntitiesPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-gray-950 flex items-center justify-center text-gray-400 text-xs">
          Loading entities repository...
        </div>
      }
    >
      <EntitiesContent />
    </Suspense>
  );
}
