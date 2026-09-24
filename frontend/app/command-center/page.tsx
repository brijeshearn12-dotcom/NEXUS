"use client";

import React, { useCallback, useEffect, useState, useMemo } from "react";
import Link from "next/link";
import {
  fetchCorpusStats,
  fetchCasePriorityQueue,
  CorpusStats,
  CasePriorityItem,
  CasePriorityStatus,
} from "@/lib/api";

const PRIORITY_BADGES: Record<
  CasePriorityStatus,
  { bg: string; text: string; border: string; dot: string; label: string }
> = {
  "Needs Verification": {
    bg: "bg-amber-950/60",
    text: "text-amber-300",
    border: "border-amber-700/60",
    dot: "bg-amber-400",
    label: "Needs Verification",
  },
  "Needs Analysis": {
    bg: "bg-blue-950/60",
    text: "text-blue-300",
    border: "border-blue-700/60",
    dot: "bg-blue-400",
    label: "Needs Analysis",
  },
  Ready: {
    bg: "bg-emerald-950/60",
    text: "text-emerald-300",
    border: "border-emerald-700/60",
    dot: "bg-emerald-400",
    label: "Ready",
  },
  "Insufficient Data": {
    bg: "bg-slate-800/80",
    text: "text-slate-400",
    border: "border-slate-700/60",
    dot: "bg-slate-500",
    label: "Insufficient Data",
  },
};

export default function CommandCenterPage() {
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [cases, setCases] = useState<CasePriorityItem[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Filters for priority queue
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [selectedPriority, setSelectedPriority] = useState<string>("ALL");

  const loadData = useCallback(async (isRefresh: boolean = false) => {
    if (isRefresh) {
      setRefreshing(true);
    } else {
      setLoading(true);
    }
    setErrorMessage(null);

    try {
      const [statsRes, queueRes] = await Promise.all([
        fetchCorpusStats(),
        fetchCasePriorityQueue(),
      ]);

      if (!statsRes.ok) {
        setErrorMessage(statsRes.errorMessage || "Unable to load corpus data.");
        setLoading(false);
        setRefreshing(false);
        return;
      }

      if (!queueRes.ok) {
        setErrorMessage(queueRes.errorMessage || "Unable to load corpus data.");
        setLoading(false);
        setRefreshing(false);
        return;
      }

      setStats(statsRes.data || null);
      setCases(queueRes.data?.items || []);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unable to load corpus data.";
      setErrorMessage(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadData(false);
  }, [loadData]);

  // Filtered case queue
  const filteredCases = useMemo(() => {
    return cases.filter((item) => {
      const matchesSearch =
        searchQuery.trim() === "" ||
        item.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
        item.case_id.toLowerCase().includes(searchQuery.toLowerCase());

      const matchesPriority =
        selectedPriority === "ALL" || item.priority === selectedPriority;

      return matchesSearch && matchesPriority;
    });
  }, [cases, searchQuery, selectedPriority]);

  const isEmpty =
    !loading &&
    !errorMessage &&
    (!stats || (stats.documents === 0 && stats.cases === 0 && cases.length === 0));

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col antialiased">
      {/* Top Navigation Bar */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40 px-4 sm:px-6 py-3.5">
        <div className="mx-auto flex max-w-7xl items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600/20 text-blue-400 font-bold border border-blue-500/40 text-xs shadow-sm">
              NX
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-base font-bold tracking-tight text-white">
                  NEXUS
                </span>
                <span className="rounded bg-blue-950 px-1.5 py-0.5 text-[10px] font-semibold text-blue-400 border border-blue-800">
                  Command Center
                </span>
              </div>
              <p className="text-[11px] text-slate-400 hidden sm:block">
                Corpus-wide intelligence &amp; multi-case operations
              </p>
            </div>
          </div>

          <nav className="flex items-center gap-2 sm:gap-4 text-xs sm:text-sm font-medium">
            <Link
              href="/command-center"
              className="text-blue-400 border-b-2 border-blue-500 pb-0.5 font-semibold"
            >
              Command Center
            </Link>
            <Link
              href="/corpus"
              className="text-slate-400 hover:text-slate-200 transition"
            >
              Corpus
            </Link>
            <Link
              href="/entities"
              className="text-slate-400 hover:text-slate-200 transition"
            >
              Entities
            </Link>
            <Link
              href="/dashboard"
              className="text-slate-400 hover:text-slate-200 transition"
            >
              Dashboard
            </Link>
          </nav>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="mx-auto max-w-7xl w-full p-4 sm:p-6 lg:p-8 space-y-6 flex-1">
        {/* Step 5 Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 pb-2 border-b border-slate-800/80">
          <div>
            <div className="flex items-center gap-2.5">
              <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-white">
                Command Center
              </h1>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-950/80 px-2.5 py-0.5 text-[11px] font-semibold text-emerald-300 border border-emerald-800/60">
                <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live Corpus
              </span>
            </div>
            <p className="mt-1 text-sm text-slate-400">
              Corpus-wide intelligence and case operations
            </p>
          </div>

          <div className="flex items-center gap-2.5">
            <button
              type="button"
              onClick={() => loadData(true)}
              disabled={refreshing || loading}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-800 hover:bg-slate-700 disabled:opacity-50 border border-slate-700 px-3.5 py-2 text-xs font-semibold text-slate-200 transition shadow-sm"
              title="Refresh statistics and case priority queue from database"
            >
              <span className={refreshing ? "animate-spin" : ""}>🔄</span>
              <span>{refreshing ? "Refreshing..." : "Refresh Data"}</span>
            </button>
            <Link
              href="/cases/case_100478559/graph"
              className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 px-3.5 py-2 text-xs font-bold text-white shadow transition"
            >
              <span>🕸️ Open Demo Case</span>
              <span>&rarr;</span>
            </Link>
          </div>
        </div>

        {/* Step 10 Error State */}
        {errorMessage && (
          <div className="rounded-xl border border-rose-900/60 bg-rose-950/40 p-5 text-sm text-rose-300 flex flex-col sm:flex-row sm:items-center justify-between gap-4 shadow-lg">
            <div className="flex items-center gap-3">
              <span className="text-2xl">⚠️</span>
              <div>
                <p className="font-semibold text-white">Unable to load corpus data.</p>
                <p className="text-xs text-rose-300/80 mt-0.5">{errorMessage}</p>
              </div>
            </div>
            <button
              type="button"
              onClick={() => loadData(false)}
              className="rounded-lg bg-rose-700 hover:bg-rose-600 px-4 py-2 text-xs font-bold text-white transition shadow self-start sm:self-auto"
            >
              Retry
            </button>
          </div>
        )}

        {/* Step 9 Loading State — Stat Cards Skeleton */}
        {loading && !stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
            {[...Array(6)].map((_, i) => (
              <div
                key={i}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-4 space-y-2 animate-pulse"
              >
                <div className="h-3 w-16 bg-slate-800 rounded" />
                <div className="h-7 w-20 bg-slate-800 rounded" />
                <div className="h-2.5 w-24 bg-slate-800/60 rounded" />
              </div>
            ))}
          </div>
        )}

        {/* Step 6 Stat Cards */}
        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 sm:gap-4">
            {/* Documents */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm hover:border-slate-700 transition">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Documents
              </span>
              <div className="mt-2 text-2xl sm:text-3xl font-extrabold text-white">
                {stats.documents.toLocaleString()}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Total in corpus</p>
            </div>

            {/* Cases */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm hover:border-slate-700 transition">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Cases
              </span>
              <div className="mt-2 text-2xl sm:text-3xl font-extrabold text-blue-400">
                {stats.cases.toLocaleString()}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Total cases</p>
            </div>

            {/* Entities */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm hover:border-slate-700 transition">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Entities
              </span>
              <div className="mt-2 text-2xl sm:text-3xl font-extrabold text-indigo-400">
                {stats.entities.toLocaleString()}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Extracted entities</p>
            </div>

            {/* Relationships */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm hover:border-slate-700 transition">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Relationships
              </span>
              <div className="mt-2 text-2xl sm:text-3xl font-extrabold text-cyan-400">
                {stats.edges.toLocaleString()}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Total graph edges</p>
            </div>

            {/* Flags */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm hover:border-slate-700 transition">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Flags
              </span>
              <div className="mt-2 text-2xl sm:text-3xl font-extrabold text-rose-400">
                {stats.flags.toLocaleString()}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Pattern flags</p>
            </div>

            {/* Validation */}
            <div className="rounded-xl border border-slate-800 bg-slate-900/70 p-4 shadow-sm hover:border-slate-700 transition">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                Validation
              </span>
              <div
                className={`mt-2 text-2xl sm:text-3xl font-extrabold ${
                  stats.validation_score ? "text-emerald-400" : "text-slate-400"
                }`}
              >
                {stats.validation_score
                  ? stats.validation_score.replace("/", " / ")
                  : "Not Run"}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">Task 5.2 result</p>
            </div>
          </div>
        )}

        {/* Step 11 Empty State */}
        {isEmpty && (
          <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/40 p-12 text-center space-y-3">
            <span className="text-4xl">📂</span>
            <h3 className="text-base font-bold text-slate-200">
              No corpus data available yet.
            </h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              The corpus is currently unpopulated. Ingest judgments or run extraction to populate cases, entities, and relationship graphs.
            </p>
            <div className="pt-2">
              <Link
                href="/corpus"
                className="inline-flex items-center gap-1.5 rounded-lg bg-blue-600 px-4 py-2 text-xs font-semibold text-white hover:bg-blue-500 transition"
              >
                Go to Corpus Ingestion &rarr;
              </Link>
            </div>
          </div>
        )}

        {/* Step 7 Case Priority Queue Section */}
        {!isEmpty && (
          <section className="space-y-4">
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 pt-2">
              <div>
                <div className="flex items-center gap-2">
                  <h2 className="text-xl font-bold text-white">
                    Case Priority Queue
                  </h2>
                  <span className="rounded-full bg-slate-800 px-2.5 py-0.5 text-xs font-semibold text-slate-300 border border-slate-700">
                    {loading ? "..." : cases.length} cases
                  </span>
                </div>
                <p className="text-xs text-slate-400 mt-0.5">
                  Triage queue prioritized by real extraction, network analysis, and human-in-the-loop verification status
                </p>
              </div>

              {/* Priority Filter and Search */}
              <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-2.5">
                {/* Search Box */}
                <div className="relative min-w-[220px]">
                  <input
                    type="text"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    placeholder="Search by case ID or title..."
                    className="w-full rounded-lg border border-slate-700 bg-slate-900/90 px-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:border-blue-500 focus:outline-none"
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      onClick={() => setSearchQuery("")}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-200 text-xs"
                    >
                      ✕
                    </button>
                  )}
                </div>

                {/* Priority Filter Tabs */}
                <div className="flex items-center rounded-lg bg-slate-900 border border-slate-800 p-0.5 text-xs">
                  {["ALL", "Needs Verification", "Needs Analysis", "Ready"].map(
                    (p) => (
                      <button
                        key={p}
                        type="button"
                        onClick={() => setSelectedPriority(p)}
                        className={`px-2.5 py-1 rounded-md text-[11px] font-semibold transition ${
                          selectedPriority === p
                            ? "bg-blue-600 text-white shadow-sm"
                            : "text-slate-400 hover:text-slate-200"
                        }`}
                      >
                        {p}
                      </button>
                    )
                  )}
                </div>
              </div>
            </div>

            {/* Step 9 Loading State — Table Skeleton */}
            {loading && !cases.length && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-6 space-y-4 animate-pulse">
                {[...Array(5)].map((_, i) => (
                  <div
                    key={i}
                    className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-slate-800/60 pb-3"
                  >
                    <div className="space-y-1.5 flex-1">
                      <div className="h-4 w-64 bg-slate-800 rounded" />
                      <div className="h-3 w-40 bg-slate-800/60 rounded" />
                    </div>
                    <div className="h-8 w-28 bg-slate-800 rounded" />
                  </div>
                ))}
              </div>
            )}

            {/* Case Cards / Table */}
            {!loading && filteredCases.length === 0 && (
              <div className="rounded-xl border border-slate-800 bg-slate-900/40 p-8 text-center text-xs text-slate-400">
                No cases match the selected filter.
              </div>
            )}

            {!loading && filteredCases.length > 0 && (
              <div className="space-y-3">
                {filteredCases.map((item) => {
                  const badge =
                    PRIORITY_BADGES[item.priority] ||
                    PRIORITY_BADGES["Needs Analysis"];

                  return (
                    <div
                      key={item.case_id}
                      className="rounded-xl border border-slate-800/80 bg-slate-900/80 p-4 sm:p-5 hover:border-slate-700/80 transition duration-150 shadow-sm flex flex-col md:flex-row md:items-center justify-between gap-4"
                    >
                      {/* Left: Case Info */}
                      <div className="space-y-2 flex-1 min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-bold text-blue-400 bg-blue-950/60 border border-blue-800 px-2 py-0.5 rounded">
                            {item.case_id}
                          </span>
                          <span
                            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-semibold border ${badge.bg} ${badge.text} ${badge.border}`}
                          >
                            <span
                              className={`h-1.5 w-1.5 rounded-full ${badge.dot}`}
                            />
                            {badge.label}
                          </span>
                        </div>

                        <h3
                          className="text-sm sm:text-base font-bold text-white truncate"
                          title={item.title}
                        >
                          {item.title}
                        </h3>

                        {/* Counts Breakdown Badges */}
                        <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs text-slate-300">
                          <span className="inline-flex items-center gap-1 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            <span>📄</span>
                            <span>{item.document_count} documents</span>
                          </span>
                          <span className="inline-flex items-center gap-1 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            <span>🏷️</span>
                            <span>{item.entity_count} entities</span>
                          </span>
                          <span className="inline-flex items-center gap-1 bg-slate-950 px-2 py-0.5 rounded border border-slate-800">
                            <span>🔗</span>
                            <span>{item.edge_count} relationships</span>
                          </span>
                          <span
                            className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border ${
                              item.flag_count > 0
                                ? "bg-rose-950/60 text-rose-300 border-rose-800/60 font-semibold"
                                : "bg-slate-950 text-slate-400 border-slate-800"
                            }`}
                          >
                            <span>🚩</span>
                            <span>{item.flag_count} flags</span>
                          </span>
                        </div>
                      </div>

                      {/* Right: Step 8 Open Case Button */}
                      <div className="shrink-0 flex items-center gap-2.5">
                        <Link
                          href={`/cases/${encodeURIComponent(item.case_id)}/graph`}
                          className="w-full sm:w-auto inline-flex items-center justify-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 px-4 py-2 text-xs font-bold text-white shadow transition"
                        >
                          <span>Open Case</span>
                          <span>&rarr;</span>
                        </Link>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
