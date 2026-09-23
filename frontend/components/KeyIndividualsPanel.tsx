"use client";

import React, { useState } from "react";
import { RankedIndividual, getEntityTypeColor } from "@/lib/api";
import ReasoningTrailPanel from "./ReasoningTrailPanel";

interface Props {
  rankedIndividuals: RankedIndividual[];
  selectedEntityId?: string | null;
  onSelectIndividual?: (entityId: string) => void;
  isLoading?: boolean;
}

export default function KeyIndividualsPanel({
  rankedIndividuals = [],
  selectedEntityId,
  onSelectIndividual,
  isLoading = false,
}: Props) {
  const [expandedEntityId, setExpandedEntityId] = useState<string | null>(null);

  if (isLoading) {
    return (
      <section className="flex flex-col rounded-lg border border-slate-700 bg-slate-900/90 p-5 text-center text-xs text-slate-400">
        <div className="mx-auto h-6 w-6 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
        <p className="mt-2 font-medium text-slate-300">Loading key individuals…</p>
      </section>
    );
  }

  if (!rankedIndividuals || rankedIndividuals.length === 0) {
    return (
      <section className="rounded-lg border border-slate-700 bg-slate-900/80 p-5 text-center text-xs text-slate-400">
        <p className="font-semibold text-slate-200">Key Individuals</p>
        <p className="mt-2 italic text-slate-500">
          No ranked individuals available. Run network analysis or verify case data.
        </p>
      </section>
    );
  }

  return (
    <section className="flex flex-col rounded-lg border border-slate-700 bg-slate-900/95 p-3.5 text-xs text-slate-300 shadow-lg">
      <div className="flex items-center justify-between border-b border-slate-800 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-sm">👥</span>
          <h3 className="font-bold text-slate-100">
            Key Individuals by Centrality ({rankedIndividuals.length})
          </h3>
        </div>
        <span className="rounded bg-blue-950/80 px-2 py-0.5 font-mono text-[10px] font-semibold text-blue-300 border border-blue-800">
          Task 5.1 Analytics
        </span>
      </div>

      <p className="mt-1.5 text-[11px] text-slate-400 italic">
        Neutral structural metric ranking based on combined degree, betweenness, and PageRank. Does not establish legal guilt.
      </p>

      {/* Ranked individuals list */}
      <div className="mt-3 max-h-96 space-y-2.5 overflow-y-auto pr-1">
        {rankedIndividuals.map((ind) => {
          const isSelected = selectedEntityId === ind.entity_id;
          const isExpanded = expandedEntityId === ind.entity_id;
          const confidencePct = ind.trail?.confidence ? Math.round(ind.trail.confidence * 100) : 85;

          return (
            <div
              key={ind.entity_id || ind.rank}
              className={`rounded-lg border p-2.5 transition-all ${
                isSelected
                  ? "border-blue-500 bg-blue-950/30 ring-1 ring-blue-500"
                  : "border-slate-800 bg-slate-950/70 hover:border-slate-700"
              }`}
            >
              {/* Header row */}
              <div className="flex items-center justify-between gap-2">
                <div
                  onClick={() => onSelectIndividual && onSelectIndividual(ind.entity_id)}
                  className="flex cursor-pointer items-center gap-2 truncate"
                  title="Click to focus on graph"
                >
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-800 font-mono text-[10px] font-bold text-slate-200 border border-slate-700">
                    #{ind.rank}
                  </span>
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: getEntityTypeColor("PERSON") }}
                  />
                  <span className="truncate font-semibold text-slate-100 hover:text-blue-300">
                    {ind.canonical_name}
                  </span>
                </div>

                <div className="flex items-center gap-1.5 shrink-0">
                  <span className="font-mono text-[11px] font-bold text-blue-400" title="Combined Centrality Score">
                    {(ind.combined_score || 0).toFixed(4)}
                  </span>
                  {ind.community_id !== undefined && (
                    <span className="rounded bg-purple-950 px-1.5 py-0.5 text-[10px] text-purple-300 border border-purple-800">
                      C#{ind.community_id}
                    </span>
                  )}
                </div>
              </div>

              {/* Centrality metrics grid */}
              <div className="mt-2 grid grid-cols-4 gap-1 rounded bg-slate-900/60 p-1.5 font-mono text-[10px] text-slate-400 text-center">
                <div>
                  <span className="text-slate-500 block">Degree</span>
                  <span className="text-slate-200 font-bold">{ind.raw_degree ?? (ind.degree ? ind.degree.toFixed(3) : 0)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Betweenness</span>
                  <span className="text-slate-200 font-bold">{(ind.betweenness || 0).toFixed(3)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">PageRank</span>
                  <span className="text-slate-200 font-bold">{(ind.pagerank || 0).toFixed(3)}</span>
                </div>
                <div>
                  <span className="text-slate-500 block">Confidence</span>
                  <span className="text-emerald-400 font-bold">{confidencePct}%</span>
                </div>
              </div>

              {/* Actions */}
              <div className="mt-2 flex items-center justify-between border-t border-slate-800/80 pt-1.5">
                <button
                  type="button"
                  onClick={() => onSelectIndividual && onSelectIndividual(ind.entity_id)}
                  className="text-[11px] font-medium text-blue-400 hover:text-blue-300"
                >
                  Locate on graph ↗
                </button>
                <button
                  type="button"
                  onClick={() => setExpandedEntityId(isExpanded ? null : ind.entity_id)}
                  className="text-[11px] font-medium text-slate-400 hover:text-slate-200 underline"
                >
                  {isExpanded ? "Hide Reasoning ▲" : "View Reasoning Trail ▼"}
                </button>
              </div>

              {/* Expandable Reasoning Trail */}
              {isExpanded && ind.trail && (
                <div className="mt-2.5 border-t border-slate-800 pt-2">
                  <ReasoningTrailPanel
                    trail={ind.trail}
                    title={`Reasoning Trail: ${ind.canonical_name}`}
                    subtitle="Deterministic graph derivation chain"
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
