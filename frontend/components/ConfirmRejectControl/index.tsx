"use client";

import React, { useState } from "react";

interface Props {
  currentStatus?: "unverified" | "confirmed" | "rejected";
  onConfirm: () => Promise<void> | void;
  onReject: () => Promise<void> | void;
  onReset?: () => Promise<void> | void;
  disabled?: boolean;
  size?: "sm" | "md";
}

export default function ConfirmRejectControl({
  currentStatus = "unverified",
  onConfirm,
  onReject,
  onReset,
  disabled = false,
  size = "md",
}: Props) {
  const [loadingAction, setLoadingAction] = useState<"confirm" | "reject" | "reset" | null>(null);

  const handleAction = async (action: "confirm" | "reject" | "reset", fn: () => Promise<void> | void) => {
    try {
      setLoadingAction(action);
      await fn();
    } finally {
      setLoadingAction(null);
    }
  };

  const btnPad = size === "sm" ? "px-2 py-1 text-xs" : "px-3 py-1.5 text-xs font-semibold";

  return (
    <div className="flex flex-wrap items-center gap-2">
      {/* Current status pill */}
      <span
        className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider ${
          currentStatus === "confirmed"
            ? "bg-emerald-950 text-emerald-400 border border-emerald-700/50"
            : currentStatus === "rejected"
            ? "bg-slate-800 text-slate-400 border border-slate-600/50"
            : "bg-amber-950 text-amber-400 border border-amber-700/50"
        }`}
      >
        {currentStatus === "confirmed" && "✓ Confirmed"}
        {currentStatus === "rejected" && "✗ Rejected"}
        {currentStatus === "unverified" && "⏳ Unverified"}
      </span>

      {/* Action buttons */}
      <div className="flex items-center gap-1.5">
        <button
          type="button"
          onClick={() => handleAction("confirm", onConfirm)}
          disabled={disabled || loadingAction !== null || currentStatus === "confirmed"}
          className={`inline-flex items-center gap-1 rounded transition-colors ${btnPad} ${
            currentStatus === "confirmed"
              ? "bg-emerald-900/40 text-emerald-500/60 cursor-not-allowed border border-emerald-900/50"
              : "bg-emerald-600 text-white hover:bg-emerald-500 shadow-sm border border-emerald-500 disabled:opacity-40"
          }`}
          title="Mark entity or flag as verified and accurate"
        >
          {loadingAction === "confirm" ? (
            <span className="inline-block animate-spin">⏳</span>
          ) : (
            <span>✓</span>
          )}
          <span>Confirm</span>
        </button>

        <button
          type="button"
          onClick={() => handleAction("reject", onReject)}
          disabled={disabled || loadingAction !== null || currentStatus === "rejected"}
          className={`inline-flex items-center gap-1 rounded transition-colors ${btnPad} ${
            currentStatus === "rejected"
              ? "bg-rose-950/40 text-rose-500/50 cursor-not-allowed border border-rose-950/50"
              : "bg-rose-700 text-white hover:bg-rose-600 shadow-sm border border-rose-600 disabled:opacity-40"
          }`}
          title="Flag as false positive or inaccurate (preserves record as rejected)"
        >
          {loadingAction === "reject" ? (
            <span className="inline-block animate-spin">⏳</span>
          ) : (
            <span>✗</span>
          )}
          <span>Reject</span>
        </button>

        {onReset && currentStatus !== "unverified" && (
          <button
            type="button"
            onClick={() => handleAction("reset", onReset)}
            disabled={disabled || loadingAction !== null}
            className={`inline-flex items-center gap-1 rounded bg-slate-800 text-slate-300 hover:bg-slate-700 hover:text-white border border-slate-600 disabled:opacity-40 ${btnPad}`}
            title="Reset verification status to unverified"
          >
            {loadingAction === "reset" ? "..." : "Reset"}
          </button>
        )}
      </div>
    </div>
  );
}
