"use client";

import React from "react";
import {
  EnrichedGraphNode,
  EnrichedGraphEdge,
  getEntityTypeColor,
  verifyEntity,
} from "@/lib/api";
import ConfirmRejectControl from "./ConfirmRejectControl";
import ReasoningTrailPanel from "./ReasoningTrailPanel";

interface Props {
  entity: EnrichedGraphNode | null;
  allEdges: EnrichedGraphEdge[];
  allNodes: EnrichedGraphNode[];
  onEntityStatusChange: (entityId: string, newStatus: "confirmed" | "rejected" | "unverified") => void;
  onSelectNeighbor?: (node: EnrichedGraphNode) => void;
  onClose?: () => void;
}

export default function EntityPanel({
  entity,
  allEdges,
  allNodes,
  onEntityStatusChange,
  onSelectNeighbor,
  onClose,
}: Props) {
  if (!entity) {
    return (
      <section className="flex h-full flex-col justify-center rounded-lg border border-slate-700 bg-slate-800/90 p-6 text-center text-slate-400">
        <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-slate-700/60 text-2xl text-slate-300">
          🔍
        </div>
        <h3 className="text-base font-semibold text-slate-200">Entity Inspector</h3>
        <p className="mt-1 text-xs text-slate-400">
          Click any node on the graph or search by name to view evidence, centrality, provenance, and reasoning trail.
        </p>
      </section>
    );
  }

  // Find connected edges and neighbors
  const connectedEdges = allEdges.filter(
    (e) => e.source === entity.id || e.target === entity.id
  );

  const neighbors = connectedEdges.map((e) => {
    const isSource = e.source === entity.id;
    const neighborId = isSource ? e.target : e.source;
    const neighborNode = allNodes.find((n) => n.id === neighborId);
    return {
      edge: e,
      neighborId,
      neighborName: neighborNode ? neighborNode.name : neighborId,
      neighborType: neighborNode ? neighborNode.entity_type : "UNKNOWN",
      neighborNode,
      relationship: e.edge_type || "co_occurrence",
    };
  });

  const typeColor = getEntityTypeColor(entity.entity_type);

  const handleConfirm = async () => {
    const res = await verifyEntity(entity.id, "confirmed");
    if (res.ok) {
      onEntityStatusChange(entity.id, "confirmed");
    } else {
      alert(`Failed to confirm entity: ${res.errorMessage}`);
    }
  };

  const handleReject = async () => {
    const res = await verifyEntity(entity.id, "rejected");
    if (res.ok) {
      onEntityStatusChange(entity.id, "rejected");
    } else {
      alert(`Failed to reject entity: ${res.errorMessage}`);
    }
  };

  const handleReset = async () => {
    const res = await verifyEntity(entity.id, "unverified");
    if (res.ok) {
      onEntityStatusChange(entity.id, "unverified");
    } else {
      alert(`Failed to reset entity: ${res.errorMessage}`);
    }
  };

  return (
    <section className="flex h-full flex-col overflow-y-auto rounded-lg border border-slate-700 bg-slate-800/95 p-4 text-xs text-slate-300 shadow-xl backdrop-blur-sm">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-slate-700 pb-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: typeColor }}
            />
            <h3 className="text-base font-bold text-slate-100">{entity.name}</h3>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded bg-slate-700/80 px-2 py-0.5 text-[10px] font-semibold uppercase text-slate-300">
              {entity.entity_type}
            </span>
            {entity.rank && (
              <span className="rounded bg-blue-900/60 px-2 py-0.5 text-[10px] font-bold text-blue-300 border border-blue-700">
                Centrality Rank #{entity.rank}
              </span>
            )}
            {entity.community_id !== undefined && entity.community_id !== null && (
              <span className="rounded bg-purple-900/60 px-2 py-0.5 text-[10px] text-purple-300 border border-purple-700">
                Community #{entity.community_id}
              </span>
            )}
          </div>
        </div>

        {onClose && (
          <button
            onClick={onClose}
            className="rounded p-1 text-slate-400 hover:bg-slate-700 hover:text-slate-100"
            title="Close inspector"
          >
            ✕
          </button>
        )}
      </div>

      {/* Verification controls */}
      <div className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/80 p-3">
        <div className="flex items-center justify-between">
          <span className="text-[11px] font-semibold text-slate-300 uppercase tracking-wider">
            Analyst Verification (HITL)
          </span>
        </div>
        <p className="mt-1 text-[11px] text-slate-400">
          Confirm or reject this extracted entity. Status is recorded in MongoDB audit log and persists across page reloads.
        </p>
        <div className="mt-2.5">
          <ConfirmRejectControl
            currentStatus={entity.verification_status}
            onConfirm={handleConfirm}
            onReject={handleReject}
            onReset={handleReset}
          />
        </div>
      </div>

      {/* Centrality Metrics */}
      <div className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/50 p-3">
        <span className="font-semibold text-slate-200 uppercase text-[10px] tracking-wider">
          Centrality & Network Metrics
        </span>
        <div className="mt-2 grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded bg-slate-800/80 p-2">
            <span className="text-slate-400">Combined Centrality:</span>
            <p className="font-mono font-bold text-blue-400">
              {(entity.combined_score || 0).toFixed(4)}
            </p>
          </div>
          <div className="rounded bg-slate-800/80 p-2">
            <span className="text-slate-400">PageRank:</span>
            <p className="font-mono font-bold text-indigo-400">
              {(entity.pagerank || 0).toFixed(4)}
            </p>
          </div>
          <div className="rounded bg-slate-800/80 p-2">
            <span className="text-slate-400">Betweenness:</span>
            <p className="font-mono font-bold text-teal-400">
              {(entity.betweenness || 0).toFixed(4)}
            </p>
          </div>
          <div className="rounded bg-slate-800/80 p-2">
            <span className="text-slate-400">Degree Connections:</span>
            <p className="font-mono font-bold text-emerald-400">
              {entity.raw_degree ?? connectedEdges.length}
            </p>
          </div>
        </div>
      </div>

      {/* Provenance Metadata */}
      <div className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/50 p-3 space-y-1.5">
        <span className="font-semibold text-slate-200 uppercase text-[10px] tracking-wider">
          Source & Provenance
        </span>
        <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
          <div>
            <span className="text-slate-400">Provenance Tier:</span>
            <p className="font-medium text-slate-200 uppercase">
              {entity.provenance?.tier || "primary"}
            </p>
          </div>
          <div>
            <span className="text-slate-400">Extraction Method:</span>
            <p className="font-medium text-slate-200">
              {entity.provenance?.method || "automated"}
            </p>
          </div>
          <div className="col-span-2">
            <span className="text-slate-400">Source Document / Case:</span>
            <p className="font-mono text-slate-200 truncate" title={entity.provenance?.source_ref || entity.case_id}>
              {entity.provenance?.source_ref || entity.case_id || "Corpus Record"}
            </p>
          </div>
          {entity.evidence_snippet && (
            <div className="col-span-2">
              <span className="text-slate-400">Direct Case Evidence Snippet:</span>
              <p className="mt-1 rounded bg-slate-950 p-2 font-mono text-[11px] text-slate-300 border border-slate-800">
                &ldquo;{entity.evidence_snippet}&rdquo;
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Deterministic Reasoning Trail */}
      <div className="mt-3">
        <ReasoningTrailPanel trail={entity.trail} />
      </div>

      {/* Connected Neighbors */}
      <div className="mt-3 rounded-lg border border-slate-700/80 bg-slate-900/50 p-3">
        <div className="flex items-center justify-between">
          <span className="font-semibold text-slate-200 uppercase text-[10px] tracking-wider">
            Connected Relationships ({neighbors.length})
          </span>
        </div>
        {neighbors.length === 0 ? (
          <p className="mt-2 italic text-slate-500 text-[11px]">No direct network edges found.</p>
        ) : (
          <ul className="mt-2 max-h-48 space-y-1.5 overflow-y-auto pr-1">
            {neighbors.map((n, idx) => (
              <li
                key={idx}
                onClick={() => n.neighborNode && onSelectNeighbor && onSelectNeighbor(n.neighborNode)}
                className={`flex items-center justify-between rounded bg-slate-800/80 p-1.5 text-[11px] transition-colors ${
                  onSelectNeighbor && n.neighborNode
                    ? "cursor-pointer hover:bg-slate-700/80 hover:text-white"
                    : ""
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <span
                    className="h-2 w-2 rounded-full shrink-0"
                    style={{ backgroundColor: getEntityTypeColor(n.neighborType) }}
                  />
                  <span className="truncate font-medium text-slate-200">{n.neighborName}</span>
                </div>
                <div className="flex items-center gap-1.5 shrink-0 text-[10px] text-slate-400">
                  <span className="rounded bg-slate-900 px-1 text-slate-300">
                    {n.relationship}
                  </span>
                  <span>wt: {n.edge.weight || 1}</span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
