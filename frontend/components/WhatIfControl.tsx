"use client";

import React, { useState } from "react";
import {
  EnrichedGraphNode,
  simulateCase,
  SimulationResponse,
} from "@/lib/api";

interface Props {
  caseId: string;
  selectedNode: EnrichedGraphNode | null;
  onSimulationRun: (result: SimulationResponse, excludedNodeId: string) => void;
  onExitSimulation: () => void;
  isSimulating: boolean;
  activeSimulationResult: SimulationResponse | null;
  activeExcludedNodeName?: string;
}

export default function WhatIfControl({
  caseId,
  selectedNode,
  onSimulationRun,
  onExitSimulation,
  isSimulating,
  activeSimulationResult,
  activeExcludedNodeName,
}: Props) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunSimulation = async () => {
    if (!selectedNode) return;
    setLoading(true);
    setError(null);

    try {
      const res = await simulateCase(caseId, [selectedNode.id]);
      if (res.ok && res.data) {
        onSimulationRun(res.data, selectedNode.id);
      } else {
        setError(res.errorMessage || "Simulation failed to execute");
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Error executing simulation";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  // If simulation is active, show the simulation banner & before/after comparison
  if (isSimulating && activeSimulationResult) {
    const impact = activeSimulationResult.impact_summary;
    const origTop = activeSimulationResult.original_top_individuals || [];
    const simTop = activeSimulationResult.simulated_top_individuals || [];

    return (
      <section className="rounded-xl border border-amber-500/80 bg-gradient-to-r from-amber-950/60 via-slate-900 to-amber-950/40 p-4 text-xs shadow-xl">
        {/* Banner */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-amber-800/60 pb-3 gap-2">
          <div className="flex items-center gap-2">
            <span className="flex h-6 w-6 items-center justify-center rounded-full bg-amber-500 text-slate-950 font-bold text-xs">
              ⚡
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-bold text-amber-300 uppercase tracking-wider text-xs">
                  What-If Simulation Active
                </span>
                <span className="rounded bg-amber-950 px-2 py-0.5 text-[10px] font-semibold text-amber-200 border border-amber-700">
                  Hypothetical Subgraph
                </span>
              </div>
              <p className="text-[11px] text-slate-300 mt-0.5">
                Simulated removal of: <strong className="text-white">{activeExcludedNodeName || "Selected Entity"}</strong>
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onExitSimulation}
            className="rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-600 px-3 py-1.5 font-bold text-slate-200 hover:text-white transition shadow-sm"
          >
            ← Exit Simulation (Restore Graph)
          </button>
        </div>

        {/* Impact metrics row */}
        {impact && (
          <div className="mt-3 grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-[11px]">
            <div className="rounded bg-slate-900/80 p-2 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Remaining Nodes</span>
              <span className="font-mono font-bold text-white">
                {impact.simulated_nodes} / {impact.original_nodes}
              </span>
            </div>
            <div className="rounded bg-slate-900/80 p-2 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Remaining Edges</span>
              <span className="font-mono font-bold text-white">
                {impact.simulated_edges} / {impact.original_edges}
              </span>
            </div>
            <div className="rounded bg-slate-900/80 p-2 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Rankings Changed?</span>
              <span className={`font-mono font-bold ${impact.rankings_changed ? "text-amber-400" : "text-slate-400"}`}>
                {impact.rankings_changed ? "YES (Impactful)" : "No change"}
              </span>
            </div>
            <div className="rounded bg-slate-900/80 p-2 border border-slate-800">
              <span className="text-slate-400 block text-[10px]">Communities</span>
              <span className="font-mono font-bold text-purple-400">
                {impact.simulated_communities_count}
              </span>
            </div>
          </div>
        )}

        {/* Before / After Comparison Table */}
        <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-3">
          {/* Baseline */}
          <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-2.5">
            <h4 className="font-bold text-slate-300 text-[11px] mb-2 uppercase tracking-wide">
              Original Top Individuals
            </h4>
            <div className="space-y-1">
              {origTop.slice(0, 5).map((ind, idx) => (
                <div key={idx} className="flex items-center justify-between text-[11px] py-1 border-b border-slate-900 last:border-0">
                  <div className="flex items-center gap-1.5 truncate">
                    <span className="font-mono text-slate-500 w-4">#{ind.rank || idx + 1}</span>
                    <span className="text-slate-200 truncate">{ind.canonical_name}</span>
                  </div>
                  <span className="font-mono text-slate-400">{(ind.combined_score || 0).toFixed(4)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Simulated */}
          <div className="rounded-lg border border-amber-900/50 bg-slate-950/80 p-2.5">
            <h4 className="font-bold text-amber-300 text-[11px] mb-2 uppercase tracking-wide">
              Simulated Top Individuals
            </h4>
            <div className="space-y-1">
              {simTop.slice(0, 5).map((ind, idx) => {
                const origMatch = origTop.find((o) => o.entity_id === ind.entity_id);
                const scoreDiff = origMatch ? ind.combined_score - origMatch.combined_score : 0;
                return (
                  <div key={idx} className="flex items-center justify-between text-[11px] py-1 border-b border-slate-900 last:border-0">
                    <div className="flex items-center gap-1.5 truncate">
                      <span className="font-mono text-amber-400 w-4">#{ind.rank || idx + 1}</span>
                      <span className="text-slate-200 truncate">{ind.canonical_name}</span>
                    </div>
                    <div className="flex items-center gap-1.5 font-mono">
                      <span className="text-slate-300">{(ind.combined_score || 0).toFixed(4)}</span>
                      {scoreDiff !== 0 && (
                        <span className={`text-[10px] ${scoreDiff > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                          {scoreDiff > 0 ? `+${scoreDiff.toFixed(3)}` : scoreDiff.toFixed(3)}
                        </span>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>

        <p className="mt-2.5 text-[10px] italic text-slate-400 text-center">
          In-memory simulation. Underlying database remains intact. Exit or refresh at any time to restore baseline.
        </p>
      </section>
    );
  }

  // Normal dormant control
  return (
    <div className="rounded-lg border border-slate-800 bg-slate-900/80 p-3 text-xs text-slate-300">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-1.5">
          <span className="text-sm">⚡</span>
          <span className="font-bold text-slate-200">What-If Scenario Simulation</span>
        </div>
        {selectedNode && (
          <button
            type="button"
            onClick={handleRunSimulation}
            disabled={loading}
            className="rounded bg-amber-600 hover:bg-amber-500 px-3 py-1 font-semibold text-slate-950 transition shadow disabled:opacity-50"
            title="Simulate network without this entity"
          >
            {loading ? "Running Simulation…" : `Simulate Removal of "${selectedNode.name}"`}
          </button>
        )}
      </div>

      {!selectedNode && (
        <p className="mt-1 text-[11px] text-slate-500 italic">
          Select any central node on the graph or from Key Individuals to run a what-if disruption simulation.
        </p>
      )}

      {error && (
        <p className="mt-2 text-rose-400 text-[11px]">
          ⚠️ {error}
        </p>
      )}
    </div>
  );
}
