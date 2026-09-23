// SyntheticBridgeControl.tsx — Synthetic CDR/Transaction bridge control panel with statutory disclosure
"use client";

import React, { useState, useEffect, useCallback } from "react";
import {
  fetchCaseSyntheticSummary,
  generateCaseSynthetic,
  clearCaseSynthetic,
  SyntheticSummaryResponse,
} from "@/lib/api";

interface Props {
  caseId: string;
  onUpdated?: () => void;
}

export default function SyntheticBridgeControl({ caseId, onUpdated }: Props) {
  const [summary, setSummary] = useState<SyntheticSummaryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [clearing, setClearing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const [cdrCount, setCdrCount] = useState<number>(5);
  const [txnCount, setTxnCount] = useState<number>(5);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  const loadSummary = useCallback(async () => {
    setLoading(true);
    setError(null);
    const res = await fetchCaseSyntheticSummary(caseId);
    if (res.ok && res.data) {
      setSummary(res.data);
    }
    setLoading(false);
  }, [caseId]);

  useEffect(() => {
    loadSummary();
  }, [loadSummary]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setSuccessMsg(null);
    const res = await generateCaseSynthetic(caseId, cdrCount, txnCount);
    setGenerating(false);

    if (res.ok && res.data) {
      setSuccessMsg(`Generated ${res.data.total_generated} synthetic demonstration relationships.`);
      loadSummary();
      if (onUpdated) onUpdated();
    } else {
      setError(res.errorMessage || "Failed to generate synthetic data.");
    }
  };

  const handleClear = async () => {
    setClearing(true);
    setError(null);
    setSuccessMsg(null);
    const res = await clearCaseSynthetic(caseId);
    setClearing(false);

    if (res.ok && res.data) {
      setSuccessMsg(`Removed ${res.data.deleted_count} synthetic relationships. Pure baseline restored.`);
      loadSummary();
      if (onUpdated) onUpdated();
    } else {
      setError(res.errorMessage || "Failed to clear synthetic data.");
    }
  };

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-800/95 p-3 text-xs shadow-md">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="flex h-2 w-2 rounded-full bg-cyan-400 animate-pulse" />
          <span className="font-semibold tracking-wide text-slate-200">
            SYNTHETIC CDR & TXN BRIDGE
          </span>
          {summary?.has_synthetic_data && (
            <span className="rounded bg-cyan-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-cyan-300">
              Active ({summary.synthetic_edges} Edges)
            </span>
          )}
        </div>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-[11px] font-medium text-slate-400 hover:text-slate-200 transition"
        >
          {isExpanded ? "Collapse ▲" : "Configure ▼"}
        </button>
      </div>

      {/* Mandatory Statutory Disclosure Banner */}
      <div className="mt-2.5 rounded border border-amber-500/40 bg-amber-500/10 p-2 text-[10px] text-amber-200 leading-relaxed">
        <p className="font-bold flex items-center gap-1 text-amber-300">
          <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
          </svg>
          MANDATORY PROVENANCE NOTICE
        </p>
        <p className="mt-0.5">
          Synthetic CDR and transaction relationships connect <b>strictly pre-existing real entities</b> using Faker.
          They are created for analytical demonstration and are <b>NOT real-world court evidence</b>.
        </p>
      </div>

      {/* Metrics Bar */}
      <div className="mt-2.5 grid grid-cols-3 gap-2 border-t border-slate-700/60 pt-2 text-center">
        <div className="rounded bg-slate-900/60 p-1.5">
          <div className="text-[10px] text-slate-400 uppercase">Primary Edges</div>
          <div className="text-xs font-bold text-slate-100">
            {loading ? "..." : summary ? summary.primary_edges : "-"}
          </div>
        </div>
        <div className="rounded bg-slate-900/60 p-1.5">
          <div className="text-[10px] text-cyan-400 uppercase">Synth CDR</div>
          <div className="text-xs font-bold text-cyan-200">
            {loading ? "..." : summary ? summary.synthetic_cdr_count : "-"}
          </div>
        </div>
        <div className="rounded bg-slate-900/60 p-1.5">
          <div className="text-[10px] text-emerald-400 uppercase">Synth Txn</div>
          <div className="text-xs font-bold text-emerald-200">
            {loading ? "..." : summary ? summary.synthetic_transaction_count : "-"}
          </div>
        </div>
      </div>

      {/* Expandable Configuration Controls */}
      {isExpanded && (
        <div className="mt-3 space-y-2.5 border-t border-slate-700/60 pt-2.5">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="block text-[10px] font-medium text-slate-400">
                CDR Count (1-20):
              </label>
              <input
                type="number"
                min="1"
                max="20"
                value={cdrCount}
                onChange={(e) => setCdrCount(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))}
                className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100"
              />
            </div>
            <div>
              <label className="block text-[10px] font-medium text-slate-400">
                Txn Count (1-20):
              </label>
              <input
                type="number"
                min="1"
                max="20"
                value={txnCount}
                onChange={(e) => setTxnCount(Math.max(1, Math.min(20, parseInt(e.target.value) || 1)))}
                className="mt-1 w-full rounded border border-slate-600 bg-slate-900 px-2 py-1 text-xs text-slate-100"
              />
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleGenerate}
              disabled={generating || clearing}
              className="flex-1 rounded bg-cyan-600 px-2.5 py-1.5 text-xs font-semibold text-white shadow-sm hover:bg-cyan-500 disabled:opacity-50 transition"
            >
              {generating ? "Generating..." : "Generate Bridge"}
            </button>
            {summary?.has_synthetic_data && (
              <button
                onClick={handleClear}
                disabled={generating || clearing}
                className="rounded border border-rose-500/40 bg-rose-500/20 px-2.5 py-1.5 text-xs font-medium text-rose-300 hover:bg-rose-500/30 disabled:opacity-50 transition"
              >
                {clearing ? "Clearing..." : "Clear Synth"}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Messages */}
      {successMsg && (
        <p className="mt-2 text-[10px] text-emerald-400 bg-emerald-500/10 p-1.5 rounded border border-emerald-500/30">
          {successMsg}
        </p>
      )}
      {error && (
        <p className="mt-2 text-[10px] text-rose-400 bg-rose-500/10 p-1.5 rounded border border-rose-500/30">
          {error}
        </p>
      )}
    </div>
  );
}
