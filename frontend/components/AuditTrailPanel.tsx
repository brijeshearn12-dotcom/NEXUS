"use client";

import React, { useEffect, useState, useCallback } from "react";
import { fetchCaseAudit, AuditLogItem } from "@/lib/api";

interface Props {
  caseId: string;
  refreshTrigger?: number;
}

export default function AuditTrailPanel({ caseId, refreshTrigger }: Props) {
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const loadAudit = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await fetchCaseAudit(caseId, 50);
    if (res.ok && res.data) {
      setItems(res.data.items || []);
    } else {
      setError(res.errorMessage || "Failed to load audit events");
    }
    setLoading(false);
  }, [caseId]);

  useEffect(() => {
    loadAudit();
  }, [loadAudit, refreshTrigger]);

  const formatTime = (isoString?: string) => {
    if (!isoString) return "--:--:--";
    try {
      const d = new Date(isoString);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return isoString;
    }
  };

  const getActionBadge = (action: string) => {
    const act = (action || "").toLowerCase();
    if (act.includes("confirm")) {
      return { bg: "bg-emerald-950 text-emerald-300 border-emerald-800", dot: "bg-emerald-400" };
    }
    if (act.includes("reject")) {
      return { bg: "bg-rose-950 text-rose-300 border-rose-800", dot: "bg-rose-400" };
    }
    if (act.includes("simulation")) {
      return { bg: "bg-indigo-950 text-indigo-300 border-indigo-800", dot: "bg-indigo-400" };
    }
    if (act.includes("analysis")) {
      return { bg: "bg-purple-950 text-purple-300 border-purple-800", dot: "bg-purple-400" };
    }
    if (act.includes("graph")) {
      return { bg: "bg-sky-950 text-sky-300 border-sky-800", dot: "bg-sky-400" };
    }
    if (act.includes("resolve") || act.includes("alias")) {
      return { bg: "bg-amber-950 text-amber-300 border-amber-800", dot: "bg-amber-400" };
    }
    if (act.includes("extract")) {
      return { bg: "bg-teal-950 text-teal-300 border-teal-800", dot: "bg-teal-400" };
    }
    return { bg: "bg-slate-800 text-slate-300 border-slate-700", dot: "bg-slate-400" };
  };

  return (
    <section className="flex flex-col rounded-lg border border-slate-700 bg-slate-900/95 p-3.5 text-xs text-slate-300 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm">📜</span>
          <h3 className="font-bold text-slate-100">Audit Trail (Read-Only)</h3>
          <span className="rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
            {items.length} events
          </span>
        </div>
        <button
          type="button"
          onClick={loadAudit}
          disabled={loading}
          className="text-[11px] text-blue-400 hover:text-blue-300 disabled:opacity-50"
          title="Refresh audit log"
        >
          {loading ? "Refreshing..." : "↻ Refresh"}
        </button>
      </div>

      {loading && items.length === 0 && (
        <div className="p-6 text-center text-slate-400">
          <div className="mx-auto h-5 w-5 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <p className="mt-2 text-xs">Loading audit trail…</p>
        </div>
      )}

      {error && items.length === 0 && (
        <div className="mt-3 rounded border border-rose-900/60 bg-rose-950/40 p-3 text-center text-rose-300">
          <p>{error}</p>
          <button
            onClick={loadAudit}
            className="mt-2 underline font-semibold text-white"
          >
            Retry
          </button>
        </div>
      )}

      {!loading && items.length === 0 && !error && (
        <div className="p-6 text-center text-slate-500 italic">
          No audit events recorded yet.
        </div>
      )}

      {/* Chronological Timeline */}
      <div className="mt-3 max-h-72 space-y-2 overflow-y-auto pr-1">
        {items.map((event, idx) => {
          const badge = getActionBadge(event.action);
          const isExpanded = expandedId === event.id;

          return (
            <div
              key={event.id || idx}
              onClick={() => setExpandedId(isExpanded ? null : event.id)}
              className="group cursor-pointer rounded border border-slate-800 bg-slate-950/70 p-2 transition hover:border-slate-700"
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 truncate">
                  <span className={`h-2 w-2 rounded-full shrink-0 ${badge.dot}`} />
                  <span className="font-mono text-[11px] text-slate-400 shrink-0">
                    {formatTime(event.timestamp)}
                  </span>
                  <span
                    className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold uppercase ${badge.bg}`}
                  >
                    {event.action.replace(/_/g, " ")}
                  </span>
                </div>
                <span className="text-[10px] text-slate-500 font-mono shrink-0">
                  {event.actor}
                </span>
              </div>

              {event.result_summary && (
                <p className="mt-1.5 text-[11px] text-slate-300 leading-snug line-clamp-2">
                  {event.result_summary}
                </p>
              )}

              {/* Expandable JSON details */}
              {isExpanded && (
                <div className="mt-2 border-t border-slate-800/80 pt-2 text-[10px] font-mono text-slate-400 space-y-1">
                  <div>
                    <span className="text-slate-500">Event ID:</span> {event.id}
                  </div>
                  <div>
                    <span className="text-slate-500">Case ID:</span> {event.case_id || "global"}
                  </div>
                  <div>
                    <span className="text-slate-500">ISO Timestamp:</span> {event.timestamp}
                  </div>
                  {event.entity_id && (
                    <div>
                      <span className="text-slate-500">Target Entity:</span> {event.entity_id}
                    </div>
                  )}
                  {event.input_summary && (
                    <div className="rounded bg-slate-900 p-1.5 border border-slate-800">
                      <span className="text-slate-500">Input Summary:</span>
                      <pre className="mt-0.5 overflow-x-auto text-[10px] text-slate-300">
                        {JSON.stringify(event.input_summary, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-2 border-t border-slate-800/80 pt-1.5 text-[10px] text-slate-500 italic">
        Read-only authoritative record stored in MongoDB `audit_log`. Tamper-evident and immutable.
      </div>
    </section>
  );
}
