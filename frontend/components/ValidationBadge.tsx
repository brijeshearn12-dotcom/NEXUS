"use client";

import React, { useEffect, useState } from "react";
import { fetchValidationResult, ValidationResponse } from "@/lib/api";

export default function ValidationBadge() {
  const [data, setData] = useState<ValidationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    let mounted = true;
    async function loadValidation() {
      setLoading(true);
      setError(null);
      const res = await fetchValidationResult();
      if (!mounted) return;
      if (res.ok && res.data) {
        setData(res.data);
      } else {
        setError(res.errorMessage || "Validation service unreachable");
      }
      setLoading(false);
    }
    loadValidation();
    return () => {
      mounted = false;
    };
  }, []);

  if (loading) {
    return (
      <div className="inline-flex items-center gap-1.5 rounded-full border border-slate-700 bg-slate-800/80 px-2.5 py-1 text-xs text-slate-400">
        <span className="inline-block h-2 w-2 animate-pulse rounded-full bg-slate-400" />
        <span>Checking validation…</span>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div
        className="inline-flex items-center gap-1.5 rounded-full border border-rose-900/60 bg-rose-950/40 px-2.5 py-1 text-xs text-rose-300"
        title={error || "Validation data unavailable"}
      >
        <span className="h-2 w-2 rounded-full bg-rose-500" />
        <span>Validation unavailable ({error || "No data"})</span>
      </div>
    );
  }

  return (
    <div className="relative inline-block">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="inline-flex items-center gap-1.5 rounded-full border border-emerald-700/60 bg-emerald-950/60 px-3 py-1 text-xs font-medium text-emerald-300 shadow-sm transition hover:bg-emerald-900/80 hover:text-white"
        title="Click to view academic validation benchmark against Noordin Top dataset"
      >
        <span className="h-2 w-2 rounded-full bg-emerald-400 animate-ping" />
        <span>Validation: {data.score}</span>
        <span className="text-[10px] text-emerald-400">ℹ️</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 z-50 mt-2 w-96 rounded-xl border border-slate-700 bg-slate-900 p-4 text-xs text-slate-300 shadow-2xl backdrop-blur-md">
          <div className="flex items-center justify-between border-b border-slate-800 pb-2">
            <div className="flex items-center gap-1.5">
              <span className="font-bold text-slate-100">Algorithmic Benchmark Validation</span>
              <span className="rounded bg-emerald-950 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-400 border border-emerald-800">
                Task 5.2 Verified
              </span>
            </div>
            <button
              onClick={() => setIsOpen(false)}
              className="text-slate-400 hover:text-slate-200"
            >
              ✕
            </button>
          </div>

          <div className="mt-3 space-y-2.5">
            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Benchmark Metric & Score
              </span>
              <p className="mt-0.5 text-sm font-semibold text-emerald-300">
                {data.score} ({data.matches}/{data.top_k} Top-k Matches)
              </p>
            </div>

            <div className="rounded bg-slate-950 p-2.5 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Documented Ground Truth Dataset
              </span>
              <p className="font-medium text-slate-200">{data.dataset.name}</p>
              <p className="text-[11px] text-slate-400">
                Network: {data.dataset.node_count} nodes, {data.dataset.edge_count} edges (
                {data.dataset.relationship_categories?.join(", ")})
              </p>
            </div>

            <div className="rounded bg-slate-950 p-2.5 border border-slate-800 space-y-1">
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Literature & Source Reference
              </span>
              <p className="text-[11px] text-slate-300 leading-snug">
                {data.source_reference.citation}
              </p>
              {data.source_reference.primary_source_document && (
                <p className="text-[10px] text-slate-400">
                  Primary Source: {data.source_reference.primary_source_document}
                </p>
              )}
            </div>

            <div>
              <span className="text-[10px] uppercase font-bold text-slate-400 tracking-wider">
                Documented Limitations
              </span>
              <ul className="mt-1 list-disc pl-4 space-y-0.5 text-[11px] text-slate-400">
                {data.validation_limitations?.map((lim, idx) => (
                  <li key={idx}>{lim}</li>
                ))}
              </ul>
            </div>

            {data.legal_notice && (
              <p className="border-t border-slate-800 pt-2 text-[10px] italic text-slate-500 leading-relaxed">
                {data.legal_notice}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
