"use client";

import React, { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  fetchCaseGraph,
  fetchCaseAnalysis,
  transformBackendGraph,
  BackendAnalysisResponse,
  EnrichedGraphNode,
  EnrichedGraphEdge,
} from "@/lib/api";
import GraphCanvas from "@/components/GraphCanvas";
import GraphSearch from "@/components/GraphSearch";
import EntityPanel from "@/components/EntityPanel";
import ProvenanceLegend from "@/components/ProvenanceLegend";
import FlaggedPatternsPanel from "@/components/FlaggedPatternsPanel";

interface Props {
  params: { id: string };
}

export default function CaseGraphPage({ params }: Props) {
  const caseId = params.id;

  const [nodes, setNodes] = useState<EnrichedGraphNode[]>([]);
  const [edges, setEdges] = useState<EnrichedGraphEdge[]>([]);
  const [analysis, setAnalysis] = useState<BackendAnalysisResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<EnrichedGraphNode | null>(null);
  const [activeTab, setActiveTab] = useState<"inspector" | "flags" | "legend">("inspector");

  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load graph and analysis data
  const loadData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setErrorMessage(null);

    try {
      const [graphRes, analysisRes] = await Promise.all([
        fetchCaseGraph(caseId),
        fetchCaseAnalysis(caseId),
      ]);

      if (!graphRes.ok || !graphRes.data) {
        setErrorMessage(
          graphRes.errorMessage || `Failed to fetch graph data for case ${caseId}`
        );
        return;
      }

      const analysisData = analysisRes.ok ? analysisRes.data : undefined;
      setAnalysis(analysisData || null);

      const transformed = transformBackendGraph(graphRes.data, analysisData);
      setNodes(transformed.nodes);
      setEdges(transformed.edges);

      // If a node was previously selected, keep it updated with fresh status
      setSelectedNode((prev) => {
        if (!prev) return null;
        return transformed.nodes.find((n) => n.id === prev.id) || prev;
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Unexpected error loading graph";
      setErrorMessage(msg);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [caseId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle entity verification status change in real time
  const handleEntityStatusChange = (
    entityId: string,
    newStatus: "confirmed" | "rejected" | "unverified"
  ) => {
    setNodes((prevNodes) =>
      prevNodes.map((n) =>
        n.id === entityId ? { ...n, verification_status: newStatus } : n
      )
    );

    if (selectedNode && selectedNode.id === entityId) {
      setSelectedNode((prev) => (prev ? { ...prev, verification_status: newStatus } : null));
    }
  };

  // Handle flag verification status change
  const handleFlagStatusChange = (
    flagId: string,
    newStatus: "confirmed" | "rejected" | "unverified"
  ) => {
    if (analysis && analysis.flags) {
      setAnalysis({
        ...analysis,
        flags: analysis.flags.map((f) =>
          f.flag_id === flagId ? { ...f, verification_status: newStatus } : f
        ),
      });
    }
  };

  // When a node is selected from graph or search
  const handleSelectNode = (node: EnrichedGraphNode | null) => {
    setSelectedNode(node);
    if (node) {
      setActiveTab("inspector");
    }
  };

  // When clicking an entity mentioned in flags
  const handleSelectEntityById = (entityId: string) => {
    const target = nodes.find((n) => n.id === entityId);
    if (target) {
      setSelectedNode(target);
      setActiveTab("inspector");
    }
  };

  const flagCount = analysis?.flags?.length || 0;

  return (
    <main className="flex h-screen flex-col bg-slate-950 text-slate-100 antialiased overflow-hidden">
      {/* Top Command Bar */}
      <header className="flex shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/90 px-4 py-2.5 shadow-sm">
        <div className="flex items-center gap-3">
          <Link
            href="/dashboard"
            className="rounded bg-slate-800 px-2 py-1 text-xs font-semibold text-slate-300 hover:bg-slate-700 hover:text-white"
          >
            ← Command Center
          </Link>
          <div className="h-4 w-px bg-slate-700" />
          <div className="flex items-center gap-2">
            <h1 className="text-sm font-bold tracking-tight text-white">
              Case Network Graph:
            </h1>
            <span className="font-mono text-xs text-blue-400 font-semibold bg-blue-950/60 px-2 py-0.5 rounded border border-blue-800">
              {caseId}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {/* Quick Demo Case Switcher */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-slate-400">
            <span>Demo:</span>
            <Link
              href="/cases/case_100478559/graph"
              className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                caseId === "case_100478559"
                  ? "bg-blue-600 text-white font-bold"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Curated Madras HC (100478559)
            </Link>
          </div>

          {/* Refresh / Persist Check button */}
          <button
            type="button"
            onClick={() => loadData(true)}
            disabled={refreshing || loading}
            className="flex items-center gap-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-200 transition-colors disabled:opacity-50"
            title="Reload from MongoDB to verify persistence"
          >
            <span className={refreshing ? "animate-spin" : ""}>🔄</span>
            <span>{refreshing ? "Reloading..." : "Reload from DB"}</span>
          </button>
        </div>
      </header>

      {/* Error Banner */}
      {errorMessage && (
        <div className="shrink-0 flex items-center justify-between bg-rose-950/90 border-b border-rose-800 px-4 py-2 text-xs text-rose-200">
          <span>⚠️ {errorMessage}</span>
          <button
            onClick={() => loadData()}
            className="underline hover:text-white font-semibold ml-2"
          >
            Retry
          </button>
        </div>
      )}

      {/* Main Workspace Layout */}
      <div className="flex flex-1 overflow-hidden p-3 gap-3">
        {/* Left / Center Area: Search + Graph Canvas */}
        <div className="flex flex-1 flex-col gap-2.5 min-w-0">
          <div className="shrink-0">
            <GraphSearch
              nodes={nodes}
              selectedNodeId={selectedNode?.id}
              onSelectNode={handleSelectNode}
              onClearSelection={() => setSelectedNode(null)}
            />
          </div>

          <div className="relative flex-1 min-h-0">
            <GraphCanvas
              nodes={nodes}
              edges={edges}
              selectedNodeId={selectedNode?.id}
              onSelectNode={handleSelectNode}
              isLoading={loading}
            />
          </div>
        </div>

        {/* Right Drawer / Tabbed Panel */}
        <aside className="flex w-96 shrink-0 flex-col overflow-hidden rounded-lg border border-slate-800 bg-slate-900/90 shadow-xl">
          {/* Panel Tab Navigation */}
          <div className="flex shrink-0 border-b border-slate-800 bg-slate-900 text-xs font-medium">
            <button
              type="button"
              onClick={() => setActiveTab("inspector")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "inspector"
                  ? "border-blue-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
            >
              Entity Inspector
              {selectedNode && (
                <span className="ml-1.5 inline-block h-2 w-2 rounded-full bg-blue-500" />
              )}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("flags")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "flags"
                  ? "border-rose-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
            >
              Flags ({flagCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("legend")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "legend"
                  ? "border-emerald-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
            >
              Visual Key
            </button>
          </div>

          {/* Tab Contents */}
          <div className="flex-1 overflow-y-auto p-3">
            {activeTab === "inspector" && (
              <EntityPanel
                entity={selectedNode}
                allEdges={edges}
                allNodes={nodes}
                onEntityStatusChange={handleEntityStatusChange}
                onSelectNeighbor={handleSelectNode}
                onClose={() => setSelectedNode(null)}
              />
            )}

            {activeTab === "flags" && (
              <FlaggedPatternsPanel
                caseId={caseId}
                flags={analysis?.flags || []}
                onSelectEntityId={handleSelectEntityById}
                onFlagStatusChange={handleFlagStatusChange}
              />
            )}

            {activeTab === "legend" && <ProvenanceLegend />}
          </div>

          {/* Quick status bar at bottom of panel */}
          <div className="shrink-0 border-t border-slate-800 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-400 flex items-center justify-between">
            <span>
              Status: <strong className="text-slate-300">{nodes.length}</strong> nodes,{" "}
              <strong className="text-slate-300">{edges.length}</strong> edges
            </span>
            <button
              type="button"
              onClick={() => setActiveTab(activeTab === "legend" ? "inspector" : "legend")}
              className="text-blue-400 hover:text-blue-300 font-medium"
            >
              {activeTab === "legend" ? "Show Inspector" : "Show Legend"}
            </button>
          </div>
        </aside>
      </div>
    </main>
  );
}
