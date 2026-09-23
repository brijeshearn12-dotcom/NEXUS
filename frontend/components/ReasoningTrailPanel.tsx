"use client";

import React from "react";
import { ReasoningTrailData } from "@/lib/api";

interface Props {
  trail?: ReasoningTrailData | null;
  title?: string;
  subtitle?: string;
}

export default function ReasoningTrailPanel({
  trail,
  title = "Evidence & Reasoning Trail",
  subtitle = "Deterministic 6-step verification chain (Task 5.1 & 6.1)",
}: Props) {
  if (!trail) {
    return (
      <section className="rounded-lg border border-slate-700 bg-slate-900/80 p-3.5 text-xs text-slate-400">
        <p className="font-semibold text-slate-200">{title}</p>
        <p className="mt-2 italic text-slate-500">
          No reasoning trail available. Select a node or pattern flag to inspect its verification chain.
        </p>
      </section>
    );
  }

  const confidencePct = Math.round((trail.confidence || 0) * 100);
  const confidenceColor =
    confidencePct >= 80
      ? "text-emerald-400 bg-emerald-950/60 border-emerald-800"
      : confidencePct >= 60
      ? "text-amber-400 bg-amber-950/60 border-amber-800"
      : "text-rose-400 bg-rose-950/60 border-rose-800";

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-900/90 p-3.5 text-xs shadow-md">
      <div className="flex items-center justify-between border-b border-slate-700/80 pb-2">
        <div>
          <h4 className="font-semibold text-slate-100">{title}</h4>
          {subtitle && <p className="text-[11px] text-slate-400">{subtitle}</p>}
        </div>
        <span
          className={`inline-flex items-center gap-1 rounded border px-2 py-0.5 text-[11px] font-semibold ${confidenceColor}`}
        >
          <span>Confidence:</span>
          <span>{confidencePct}%</span>
        </span>
      </div>

      <div className="mt-3 space-y-2.5">
        {/* Step 1: INPUT */}
        <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
          <div className="flex items-center gap-2">
            <span className="rounded bg-sky-950 px-1.5 py-0.5 font-mono text-[10px] font-bold text-sky-400 border border-sky-800">
              1. INPUT
            </span>
            <span className="text-[11px] font-medium text-slate-300">Entity & Relationship References</span>
          </div>
          <div className="mt-1.5 flex flex-wrap gap-1">
            {trail.input_refs && trail.input_refs.length > 0 ? (
              trail.input_refs.map((ref, idx) => (
                <span
                  key={idx}
                  className="rounded bg-slate-800/80 px-1.5 py-0.5 font-mono text-[10px] text-slate-300 border border-slate-700"
                >
                  {ref}
                </span>
              ))
            ) : (
              <span className="italic text-slate-500 text-[11px]">Primary case entity reference</span>
            )}
          </div>
        </div>

        {/* Step 2: EVIDENCE */}
        <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
          <div className="flex items-center gap-2">
            <span className="rounded bg-amber-950 px-1.5 py-0.5 font-mono text-[10px] font-bold text-amber-400 border border-amber-800">
              2. EVIDENCE
            </span>
            <span className="text-[11px] font-medium text-slate-300">Corroborated Document & Network Evidence</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-200 leading-relaxed font-mono bg-slate-900/60 p-1.5 rounded border border-slate-800/80">
            {trail.evidence || "Direct judicial record co-occurrence and network topological evidence"}
          </p>
        </div>

        {/* Step 3: REASONING */}
        <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
          <div className="flex items-center gap-2">
            <span className="rounded bg-indigo-950 px-1.5 py-0.5 font-mono text-[10px] font-bold text-indigo-400 border border-indigo-800">
              3. REASONING
            </span>
            <span className="text-[11px] font-medium text-slate-300">Algorithmic & Graph Derivation</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-300 leading-relaxed">
            {trail.reasoning || "Centrality scores, community clustering, and cross-case bridge analysis"}
          </p>
        </div>

        {/* Step 4: RESULT */}
        <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
          <div className="flex items-center gap-2">
            <span className="rounded bg-emerald-950 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-400 border border-emerald-800">
              4. RESULT
            </span>
            <span className="text-[11px] font-medium text-slate-300">Deduced Role & Significance</span>
          </div>
          <p className="mt-1 text-[11px] font-semibold text-emerald-300">
            {trail.result || "Analyzed network entity"}
          </p>
        </div>

        {/* Steps 5 & 6: CONFIDENCE & SOURCE */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
          <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-teal-950 px-1.5 py-0.5 font-mono text-[10px] font-bold text-teal-400 border border-teal-800">
                5. CONFIDENCE
              </span>
            </div>
            <p className="mt-1 text-[11px] text-teal-200">
              Score: <strong className="font-mono">{(trail.confidence || 0).toFixed(2)}</strong> ({confidencePct}%)
            </p>
          </div>

          <div className="rounded border border-slate-800 bg-slate-950/60 p-2">
            <div className="flex items-center gap-2">
              <span className="rounded bg-purple-950 px-1.5 py-0.5 font-mono text-[10px] font-bold text-purple-400 border border-purple-800">
                6. SOURCE
              </span>
            </div>
            <p className="mt-1 text-[11px] font-mono text-purple-200 truncate" title={trail.source}>
              {trail.source || "Official court record corpus"}
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
