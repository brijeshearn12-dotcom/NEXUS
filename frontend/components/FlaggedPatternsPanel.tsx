"use client";

import React, { useState } from "react";
import { PatternFlagItem, verifyFlag } from "@/lib/api";
import ConfirmRejectControl from "./ConfirmRejectControl";
import ReasoningTrailPanel from "./ReasoningTrailPanel";

interface Props {
  caseId?: string;
  flags?: PatternFlagItem[];
  onSelectEntityId?: (entityId: string) => void;
  onFlagStatusChange?: (flagId: string, status: "confirmed" | "rejected" | "unverified") => void;
}

export default function FlaggedPatternsPanel({
  caseId = "case_100478559",
  flags = [],
  onSelectEntityId,
  onFlagStatusChange,
}: Props) {
  const [expandedFlagId, setExpandedFlagId] = useState<string | null>(null);

  if (!flags || flags.length === 0) {
    return (
      <section className="rounded-lg border border-slate-700 bg-slate-800/90 p-3.5 text-xs text-slate-300">
        <p className="font-semibold text-slate-100">Automated Pattern Flags</p>
        <p className="mt-2 italic text-slate-500">
          No automated pattern flags detected for this case network.
        </p>
      </section>
    );
  }

  const handleVerify = async (
    flagId: string,
    status: "confirmed" | "rejected" | "unverified"
  ) => {
    const res = await verifyFlag(caseId, flagId, status);
    if (res.ok) {
      if (onFlagStatusChange) {
        onFlagStatusChange(flagId, status);
      }
    } else {
      alert(`Failed to verify flag: ${res.errorMessage}`);
    }
  };

  return (
    <section className="rounded-lg border border-slate-700 bg-slate-800/95 p-3.5 text-xs text-slate-300 shadow-md">
      <div className="flex items-center justify-between border-b border-slate-700/80 pb-2">
        <div className="flex items-center gap-2">
          <span className="text-base">🚩</span>
          <h3 className="font-bold text-slate-100">
            Detected Pattern Flags ({flags.length})
          </h3>
        </div>
        <span className="rounded bg-rose-500/20 px-1.5 py-0.5 text-[10px] font-semibold text-rose-300 border border-rose-800">
          High-Risk Topology
        </span>
      </div>

      <div className="mt-3 space-y-3">
        {flags.map((flag) => {
          const isExpanded = expandedFlagId === flag.flag_id;
          const severityBg =
            flag.severity === "high"
              ? "bg-rose-950 text-rose-300 border-rose-800"
              : flag.severity === "medium"
              ? "bg-amber-950 text-amber-300 border-amber-800"
              : "bg-blue-950 text-blue-300 border-blue-800";

          return (
            <div
              key={flag.flag_id}
              className="rounded-lg border border-slate-700/80 bg-slate-900/80 p-3 transition-all"
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span
                      className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase border ${severityBg}`}
                    >
                      {flag.severity}
                    </span>
                    <span className="font-mono text-[11px] font-semibold text-slate-200">
                      {flag.flag_type.replace(/_/g, " ").toUpperCase()}
                    </span>
                    {flag.canonical_name && (
                      <button
                        type="button"
                        onClick={() =>
                          flag.entity_id &&
                          onSelectEntityId &&
                          onSelectEntityId(flag.entity_id)
                        }
                        className="rounded bg-slate-800 px-1.5 py-0.5 text-[11px] font-medium text-blue-400 hover:text-blue-300 hover:underline"
                        title="Focus entity on graph"
                      >
                        Target: {flag.canonical_name} ↗
                      </button>
                    )}
                  </div>
                  <p className="mt-1.5 text-[11px] text-slate-300 leading-relaxed">
                    {flag.description}
                  </p>
                </div>
              </div>

              {/* Verification control */}
              <div className="mt-2.5 flex flex-wrap items-center justify-between border-t border-slate-800 pt-2 gap-2">
                <ConfirmRejectControl
                  currentStatus={flag.verification_status}
                  size="sm"
                  onConfirm={() => handleVerify(flag.flag_id, "confirmed")}
                  onReject={() => handleVerify(flag.flag_id, "rejected")}
                  onReset={() => handleVerify(flag.flag_id, "unverified")}
                />
                {flag.trail && (
                  <button
                    type="button"
                    onClick={() =>
                      setExpandedFlagId(isExpanded ? null : flag.flag_id)
                    }
                    className="text-[11px] font-medium text-slate-400 hover:text-slate-200 underline"
                  >
                    {isExpanded ? "Hide Trail ▲" : "Inspect Reasoning Trail ▼"}
                  </button>
                )}
              </div>

              {/* Reasoning Trail drawer */}
              {isExpanded && flag.trail && (
                <div className="mt-2.5 border-t border-slate-800 pt-2">
                  <ReasoningTrailPanel
                    trail={flag.trail}
                    title="Flag Reasoning Trail"
                    subtitle="Verification of topological pattern detection"
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
