"use client";

import React from "react";
import { ENTITY_TYPE_COLORS } from "@/lib/api";

export default function ProvenanceLegend() {
  return (
    <aside className="rounded-lg border border-slate-700 bg-slate-800/95 p-3 text-xs text-slate-300 shadow-lg backdrop-blur-sm">
      <div className="flex items-center justify-between border-b border-slate-700 pb-2">
        <span className="font-semibold tracking-wide text-slate-100">
          PROVENANCE & VISUAL KEY
        </span>
        <span className="rounded bg-blue-500/20 px-1.5 py-0.5 text-[10px] font-medium text-blue-400">
          Task 6.1
        </span>
      </div>

      {/* Entity Types */}
      <div className="mt-3">
        <p className="font-medium text-slate-400 uppercase text-[10px] tracking-wider">
          Node Color — Entity Type
        </p>
        <div className="mt-1.5 grid grid-cols-2 gap-1.5">
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.PERSON }}
            />
            <span className="truncate">Person / Accused</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.ORGANIZATION }}
            />
            <span className="truncate">Organization</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.LOCATION }}
            />
            <span className="truncate">Location</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.VEHICLE }}
            />
            <span className="truncate">Vehicle</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.PHONE }}
            />
            <span className="truncate">Phone</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.LAWYER }}
            />
            <span className="truncate">Legal / Lawyer</span>
          </div>
          <div className="flex items-center gap-2">
            <span
              className="h-3 w-3 rounded-full shrink-0 shadow-sm"
              style={{ backgroundColor: ENTITY_TYPE_COLORS.OTHER }}
            />
            <span className="truncate">Other</span>
          </div>
        </div>
      </div>

      {/* Node Size: Centrality */}
      <div className="mt-3 border-t border-slate-700/60 pt-2">
        <p className="font-medium text-slate-400 uppercase text-[10px] tracking-wider">
          Node Size — Centrality
        </p>
        <div className="mt-2 flex items-center justify-between text-slate-300">
          <div className="flex items-center gap-1.5">
            <div className="h-3 w-3 rounded-full bg-slate-500" />
            <span className="text-[11px]">Low centrality</span>
          </div>
          <span className="text-slate-500">→</span>
          <div className="flex items-center gap-1.5">
            <div className="h-5 w-5 rounded-full bg-slate-300 ring-2 ring-blue-500" />
            <span className="text-[11px] font-medium text-slate-200">High Centrality</span>
          </div>
        </div>
        <p className="mt-1 text-[10px] text-slate-400 italic">
          Proportional to Task 5.1 combined PageRank + betweenness score
        </p>
      </div>

      {/* Verification Status */}
      <div className="mt-3 border-t border-slate-700/60 pt-2">
        <p className="font-medium text-slate-400 uppercase text-[10px] tracking-wider">
          Node Border — Verification Status
        </p>
        <div className="mt-1.5 space-y-1">
          <div className="flex items-center gap-2">
            <span className="h-3.5 w-3.5 rounded-full border-2 border-emerald-500 bg-slate-700" />
            <span>Confirmed (Validated by analyst)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3.5 w-3.5 rounded-full border-2 border-amber-500 bg-slate-700" />
            <span>Unverified (Pending review)</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="h-3.5 w-3.5 rounded-full border-2 border-dashed border-slate-500 bg-slate-700 opacity-50" />
            <span className="text-slate-400">Rejected (Muted, preserved in graph)</span>
          </div>
        </div>
      </div>

      {/* Edge Styling: Provenance */}
      <div className="mt-3 border-t border-slate-700/60 pt-2">
        <p className="font-medium text-slate-400 uppercase text-[10px] tracking-wider">
          Edge Style — Provenance Tier
        </p>
        <div className="mt-1.5 space-y-1.5">
          <div className="flex items-center gap-2">
            <div className="h-0.5 w-6 bg-slate-300" />
            <span>Primary Evidence (Direct co-occurrence)</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-0.5 w-6 border-b border-dashed border-slate-400" />
            <span>Synthetic / Inferred relationship</span>
          </div>
        </div>
        <p className="mt-1 text-[10px] text-slate-400 italic">
          Line thickness scales with relationship weight / co-occurrence count
        </p>
      </div>
    </aside>
  );
}
