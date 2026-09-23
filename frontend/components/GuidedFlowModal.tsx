"use client";

import React, { useState } from "react";
import {
  extractCase,
  resolveCaseAliases,
  buildCaseGraph,
  fetchCaseAnalysis,
} from "@/lib/api";

interface Props {
  caseId: string;
  onFlowComplete: () => Promise<void> | void;
  isOpen: boolean;
  onClose: () => void;
}

type StepKey = "extract" | "resolve" | "graph" | "analysis";

interface StepState {
  key: StepKey;
  label: string;
  status: "idle" | "running" | "done" | "failed";
  details?: string;
}

export default function GuidedFlowModal({
  caseId,
  onFlowComplete,
  isOpen,
  onClose,
}: Props) {
  const [steps, setSteps] = useState<StepState[]>([
    { key: "extract", label: "Extract entities across case documents", status: "idle" },
    { key: "resolve", label: "Resolve entity aliases with conservative guardrails", status: "idle" },
    { key: "graph", label: "Build case relationship network graph", status: "idle" },
    { key: "analysis", label: "Run centrality, Louvain communities & pattern detection", status: "idle" },
  ]);

  const [isRunning, setIsRunning] = useState(false);
  const [pipelineError, setPipelineError] = useState<string | null>(null);
  const [isFinished, setIsFinished] = useState(false);

  if (!isOpen) return null;

  const updateStep = (key: StepKey, status: StepState["status"], details?: string) => {
    setSteps((prev) =>
      prev.map((s) => (s.key === key ? { ...s, status, details } : s))
    );
  };

  const runGuidedPipeline = async () => {
    setIsRunning(true);
    setPipelineError(null);
    setIsFinished(false);

    // Reset steps
    setSteps([
      { key: "extract", label: "Extract entities across case documents", status: "idle" },
      { key: "resolve", label: "Resolve entity aliases with conservative guardrails", status: "idle" },
      { key: "graph", label: "Build case relationship network graph", status: "idle" },
      { key: "analysis", label: "Run centrality, Louvain communities & pattern detection", status: "idle" },
    ]);

    // 1. EXTRACT
    updateStep("extract", "running");
    const extRes = await extractCase(caseId);
    if (!extRes.ok || !extRes.data) {
      const err = extRes.errorMessage || "Entity extraction failed";
      updateStep("extract", "failed", err);
      setPipelineError(`Step 1 Failed: ${err}`);
      setIsRunning(false);
      return;
    }
    updateStep(
      "extract",
      "done",
      extRes.data.message || `Extracted ${extRes.data.entities_extracted} entities`
    );

    // 2. RESOLVE
    updateStep("resolve", "running");
    const resRes = await resolveCaseAliases(caseId);
    if (!resRes.ok || !resRes.data) {
      const err = resRes.errorMessage || "Alias resolution failed";
      updateStep("resolve", "failed", err);
      setPipelineError(`Step 2 Failed: ${err}`);
      setIsRunning(false);
      return;
    }
    updateStep(
      "resolve",
      "done",
      `${resRes.data.merges_created} merges created across ${resRes.data.candidate_pairs} pairs`
    );

    // 3. BUILD GRAPH
    updateStep("graph", "running");
    const bgRes = await buildCaseGraph(caseId);
    if (!bgRes.ok || !bgRes.data) {
      const err = bgRes.errorMessage || "Graph construction failed";
      updateStep("graph", "failed", err);
      setPipelineError(`Step 3 Failed: ${err}`);
      setIsRunning(false);
      return;
    }
    updateStep(
      "graph",
      "done",
      `Graph constructed: ${bgRes.data.nodes} nodes, ${bgRes.data.edges_created} edges`
    );

    // 4. RUN ANALYSIS
    updateStep("analysis", "running");
    const anRes = await fetchCaseAnalysis(caseId);
    if (!anRes.ok || !anRes.data) {
      const err = anRes.errorMessage || "Network analysis failed";
      updateStep("analysis", "failed", err);
      setPipelineError(`Step 4 Failed: ${err}`);
      setIsRunning(false);
      return;
    }
    updateStep(
      "analysis",
      "done",
      `Analysis complete: ${anRes.data.ranked_individuals?.length || 0} key individuals, ${
        anRes.data.communities?.length || 0
      } communities`
    );

    // Succeeded!
    setIsRunning(false);
    setIsFinished(true);

    // Trigger parent refresh to load fresh graph, audit log, and analytics
    await onFlowComplete();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg rounded-2xl border border-slate-700 bg-slate-900 p-6 shadow-2xl text-slate-100">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-blue-600 text-white font-bold text-sm">
              ⚙️
            </span>
            <div>
              <h3 className="font-bold text-base text-white">Guided Analysis Flow</h3>
              <p className="text-xs text-slate-400">One-click end-to-end criminal network intelligence pipeline</p>
            </div>
          </div>
          {!isRunning && (
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 text-sm"
            >
              ✕
            </button>
          )}
        </div>

        {/* Case ID badge */}
        <div className="mt-4 flex items-center gap-2 text-xs">
          <span className="text-slate-400">Target Case:</span>
          <span className="font-mono font-semibold text-blue-400 bg-blue-950/60 px-2 py-0.5 rounded border border-blue-900">
            {caseId}
          </span>
        </div>

        {/* Steps List */}
        <div className="mt-4 space-y-3">
          {steps.map((step, idx) => {
            return (
              <div
                key={step.key}
                className={`rounded-lg border p-3 transition-colors ${
                  step.status === "running"
                    ? "border-blue-500 bg-blue-950/30"
                    : step.status === "done"
                    ? "border-emerald-800/80 bg-emerald-950/20"
                    : step.status === "failed"
                    ? "border-rose-800/80 bg-rose-950/30"
                    : "border-slate-800 bg-slate-950/50"
                }`}
              >
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-slate-500">{idx + 1}.</span>
                    <span className={`font-semibold ${
                      step.status === "done" ? "text-emerald-300" : "text-slate-200"
                    }`}>
                      {step.label}
                    </span>
                  </div>

                  {step.status === "idle" && (
                    <span className="text-slate-500 text-[11px]">○ Pending</span>
                  )}
                  {step.status === "running" && (
                    <span className="flex items-center gap-1 text-blue-400 text-[11px] font-medium">
                      <span className="h-3 w-3 animate-spin rounded-full border-2 border-blue-400 border-t-transparent" />
                      Running…
                    </span>
                  )}
                  {step.status === "done" && (
                    <span className="text-emerald-400 text-[11px] font-bold">✓ Complete</span>
                  )}
                  {step.status === "failed" && (
                    <span className="text-rose-400 text-[11px] font-bold">✕ Failed</span>
                  )}
                </div>

                {step.details && (
                  <p className="mt-1 text-[11px] font-mono text-slate-400 pl-4">
                    {step.details}
                  </p>
                )}
              </div>
            );
          })}
        </div>

        {/* Pipeline Error Announcement */}
        {pipelineError && (
          <div className="mt-4 rounded-lg border border-rose-800 bg-rose-950/50 p-3 text-xs text-rose-200">
            <p className="font-bold">Analysis stopped due to pipeline error:</p>
            <p className="mt-1">{pipelineError}</p>
          </div>
        )}

        {/* Footer Actions */}
        <div className="mt-6 flex items-center justify-between border-t border-slate-800 pt-3">
          <span className="text-[11px] text-slate-500 italic">
            Each step authoritatively appends to MongoDB `audit_log`.
          </span>

          <div className="flex items-center gap-2">
            {!isRunning && !isFinished && (
              <button
                type="button"
                onClick={runGuidedPipeline}
                className="rounded-lg bg-blue-600 hover:bg-blue-500 px-4 py-2 font-bold text-xs text-white shadow-lg transition"
              >
                {pipelineError ? "Retry Pipeline" : "Start Guided Flow"}
              </button>
            )}

            {isFinished && (
              <button
                type="button"
                onClick={onClose}
                className="rounded-lg bg-emerald-600 hover:bg-emerald-500 px-4 py-2 font-bold text-xs text-white shadow-lg transition"
              >
                View Complete Dashboard →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
