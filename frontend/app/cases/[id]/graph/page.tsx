"use client";

import React, { useEffect, useState, useCallback, useMemo } from "react";
import Link from "next/link";
import {
  fetchCaseGraph,
  fetchCaseAnalysis,
  transformBackendGraph,
  BackendAnalysisResponse,
  EnrichedGraphNode,
  EnrichedGraphEdge,
  SimulationResponse,
  RankedIndividual,
} from "@/lib/api";
import GraphCanvas from "@/components/GraphCanvas";
import GraphSearch from "@/components/GraphSearch";
import EntityPanel from "@/components/EntityPanel";
import ProvenanceLegend from "@/components/ProvenanceLegend";
import FlaggedPatternsPanel from "@/components/FlaggedPatternsPanel";
import KeyIndividualsPanel from "@/components/KeyIndividualsPanel";
import AuditTrailPanel from "@/components/AuditTrailPanel";
import ValidationBadge from "@/components/ValidationBadge";
import WhatIfControl from "@/components/WhatIfControl";
import GuidedFlowModal from "@/components/GuidedFlowModal";

interface Props {
  params: { id: string };
}

export default function CaseGraphPage({ params }: Props) {
  const caseId = params.id;

  // Real graph and analysis data
  const [nodes, setNodes] = useState<EnrichedGraphNode[]>([]);
  const [edges, setEdges] = useState<EnrichedGraphEdge[]>([]);
  const [analysis, setAnalysis] = useState<BackendAnalysisResponse | null>(null);
  const [selectedNode, setSelectedNode] = useState<EnrichedGraphNode | null>(null);

  // Active tab in sidebar
  const [activeTab, setActiveTab] = useState<
    "inspector" | "individuals" | "flags" | "audit" | "legend"
  >("inspector");

  // Loading & refresh states
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [auditTrigger, setAuditTrigger] = useState(0);

  // Guided Flow modal state
  const [showGuidedModal, setShowGuidedModal] = useState(false);

  // What-If Simulation state (in-memory temporary UI state)
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationResult, setSimulationResult] = useState<SimulationResponse | null>(null);
  const [simulatedExcludedName, setSimulatedExcludedName] = useState<string>("");

  // Load graph and analysis data from backend
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

      // Keep selected node updated
      setSelectedNode((prev) => {
        if (!prev) return null;
        return transformed.nodes.find((n) => n.id === prev.id) || prev;
      });

      // Increment audit refresh key
      setAuditTrigger((prev) => prev + 1);
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
    setAuditTrigger((prev) => prev + 1);
  };

  // Handle flag verification status change in real time
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
    setAuditTrigger((prev) => prev + 1);
  };

  // Select node from canvas, search, or key individuals
  const handleSelectNode = (node: EnrichedGraphNode | null) => {
    setSelectedNode(node);
    if (node) {
      setActiveTab("inspector");
    }
  };

  const handleSelectEntityById = (entityId: string) => {
    const target = nodes.find((n) => n.id === entityId);
    if (target) {
      setSelectedNode(target);
      setActiveTab("inspector");
    }
  };

  // What-If Simulation handlers
  const handleSimulationRun = (result: SimulationResponse, excludedNodeId: string) => {
    const excludedNode = nodes.find((n) => n.id === excludedNodeId);
    setSimulatedExcludedName(excludedNode ? excludedNode.name : excludedNodeId);
    setSimulationResult(result);
    setIsSimulating(true);
    setSelectedNode(null);
    setAuditTrigger((prev) => prev + 1);
  };

  const handleExitSimulation = () => {
    setIsSimulating(false);
    setSimulationResult(null);
    setSimulatedExcludedName("");
  };

  // Compute active nodes and edges (filters excluded node when simulation is active)
  const activeDisplayGraph = useMemo(() => {
    if (!isSimulating || !simulationResult) {
      return { nodes, edges };
    }

    const excludedIds = new Set(simulationResult.excluded_node_ids || []);
    const simTopMap = new Map<string, RankedIndividual>();
    for (const r of simulationResult.simulated_top_individuals || []) {
      simTopMap.set(r.entity_id, r);
    }

    const filteredNodes: EnrichedGraphNode[] = nodes
      .filter((n) => !excludedIds.has(n.id))
      .map((n) => {
        const simRank = simTopMap.get(n.id);
        if (simRank) {
          return {
            ...n,
            combined_score: simRank.combined_score,
            rank: simRank.rank,
            betweenness: simRank.betweenness,
            pagerank: simRank.pagerank,
            degree: simRank.degree,
            raw_degree: simRank.raw_degree,
          };
        }
        return n;
      });

    const filteredEdges: EnrichedGraphEdge[] = edges.filter(
      (e) => !excludedIds.has(e.source) && !excludedIds.has(e.target)
    );

    return { nodes: filteredNodes, edges: filteredEdges };
  }, [isSimulating, simulationResult, nodes, edges]);

  // Compute active ranked individuals (switches to simulated ranking during simulation)
  const activeRankedIndividuals = useMemo(() => {
    if (isSimulating && simulationResult) {
      return simulationResult.simulated_top_individuals || [];
    }
    return analysis?.ranked_individuals || [];
  }, [isSimulating, simulationResult, analysis]);

  // Compute active flags
  const activeFlags = useMemo(() => {
    if (isSimulating && simulationResult) {
      return simulationResult.flags || [];
    }
    return analysis?.flags || [];
  }, [isSimulating, simulationResult, analysis]);

  const flagCount = activeFlags.length;
  const individualCount = activeRankedIndividuals.length;

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
              Case Network Analysis:
            </h1>
            <span className="font-mono text-xs text-blue-400 font-semibold bg-blue-950/60 px-2 py-0.5 rounded border border-blue-800">
              {caseId}
            </span>
          </div>
        </div>

        {/* Center / Right controls */}
        <div className="flex items-center gap-3">
          {/* Real Task 5.2 Validation Badge */}
          <ValidationBadge />

          {/* Guided Flow Analyse Button */}
          <button
            type="button"
            onClick={() => setShowGuidedModal(true)}
            className="flex items-center gap-1.5 rounded-lg bg-blue-600 hover:bg-blue-500 px-3 py-1 text-xs font-bold text-white shadow transition-colors"
            title="Run complete 4-step guided pipeline: Extract → Resolve → Build Graph → Analysis"
          >
            <span>⚡ Analyse Case</span>
          </button>

          {/* Curated Case Switcher */}
          <div className="hidden lg:flex items-center gap-1.5 text-xs text-slate-400">
            <span>Demo:</span>
            <Link
              href="/cases/case_100478559/graph"
              className={`rounded px-2 py-0.5 text-[11px] font-medium transition-colors ${
                caseId === "case_100478559"
                  ? "bg-blue-600 text-white font-bold"
                  : "bg-slate-800 text-slate-300 hover:bg-slate-700"
              }`}
            >
              Madras HC (100478559)
            </Link>
          </div>

          {/* Refresh / Persistence verification button */}
          <button
            type="button"
            onClick={() => loadData(true)}
            disabled={refreshing || loading}
            className="flex items-center gap-1.5 rounded bg-slate-800 hover:bg-slate-700 border border-slate-700 px-2.5 py-1 text-xs font-medium text-slate-200 transition-colors disabled:opacity-50"
            title="Reload directly from MongoDB to verify persistence"
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
        {/* Left / Center Area: Search + What-If Banner + Graph Canvas */}
        <div className="flex flex-1 flex-col gap-2.5 min-w-0">
          {/* What-If Control Header */}
          <div className="shrink-0">
            <WhatIfControl
              caseId={caseId}
              selectedNode={selectedNode}
              onSimulationRun={handleSimulationRun}
              onExitSimulation={handleExitSimulation}
              isSimulating={isSimulating}
              activeSimulationResult={simulationResult}
              activeExcludedNodeName={simulatedExcludedName}
            />
          </div>

          {/* Search bar */}
          <div className="shrink-0">
            <GraphSearch
              nodes={activeDisplayGraph.nodes}
              selectedNodeId={selectedNode?.id}
              onSelectNode={handleSelectNode}
              onClearSelection={() => setSelectedNode(null)}
            />
          </div>

          {/* Cytoscape Canvas */}
          <div className="relative flex-1 min-h-0">
            <GraphCanvas
              nodes={activeDisplayGraph.nodes}
              edges={activeDisplayGraph.edges}
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
              title="Inspect selected node evidence and reasoning"
            >
              Inspector
              {selectedNode && (
                <span className="ml-1 inline-block h-1.5 w-1.5 rounded-full bg-blue-500" />
              )}
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("individuals")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "individuals"
                  ? "border-indigo-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
              title="Ranked key individuals by combined centrality"
            >
              Key ({individualCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("flags")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "flags"
                  ? "border-rose-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
              title="High-risk network pattern flags"
            >
              Flags ({flagCount})
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("audit")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "audit"
                  ? "border-amber-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
              title="Read-only chronological audit log"
            >
              Audit
            </button>

            <button
              type="button"
              onClick={() => setActiveTab("legend")}
              className={`flex-1 py-2 text-center transition-colors border-b-2 ${
                activeTab === "legend"
                  ? "border-emerald-500 font-bold text-white bg-slate-800/60"
                  : "border-transparent text-slate-400 hover:text-slate-200 hover:bg-slate-800/30"
              }`}
              title="Visual encoding and provenance key"
            >
              Key
            </button>
          </div>

          {/* Tab Contents */}
          <div className="flex-1 overflow-y-auto p-3">
            {activeTab === "inspector" && (
              <EntityPanel
                entity={selectedNode}
                allEdges={activeDisplayGraph.edges}
                allNodes={activeDisplayGraph.nodes}
                onEntityStatusChange={handleEntityStatusChange}
                onSelectNeighbor={handleSelectNode}
                onClose={() => setSelectedNode(null)}
              />
            )}

            {activeTab === "individuals" && (
              <KeyIndividualsPanel
                rankedIndividuals={activeRankedIndividuals}
                selectedEntityId={selectedNode?.id}
                onSelectIndividual={handleSelectEntityById}
                isLoading={loading}
              />
            )}

            {activeTab === "flags" && (
              <FlaggedPatternsPanel
                caseId={caseId}
                flags={activeFlags}
                onSelectEntityId={handleSelectEntityById}
                onFlagStatusChange={handleFlagStatusChange}
              />
            )}

            {activeTab === "audit" && (
              <AuditTrailPanel
                caseId={caseId}
                refreshTrigger={auditTrigger}
              />
            )}

            {activeTab === "legend" && <ProvenanceLegend />}
          </div>

          {/* Quick status bar at bottom of panel */}
          <div className="shrink-0 border-t border-slate-800 bg-slate-950/80 px-3 py-2 text-[11px] text-slate-400 flex items-center justify-between">
            <span>
              Graph: <strong className="text-slate-300">{activeDisplayGraph.nodes.length}</strong> nodes,{" "}
              <strong className="text-slate-300">{activeDisplayGraph.edges.length}</strong> edges
            </span>
            {isSimulating && (
              <span className="font-semibold text-amber-400">⚡ SIMULATION</span>
            )}
          </div>
        </aside>
      </div>

      {/* Guided Flow Pipeline Modal */}
      <GuidedFlowModal
        caseId={caseId}
        isOpen={showGuidedModal}
        onClose={() => setShowGuidedModal(false)}
        onFlowComplete={async () => {
          await loadData(true);
        }}
      />
    </main>
  );
}
