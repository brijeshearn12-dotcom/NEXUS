"use client";

import React, { useState, useMemo } from "react";
import { EnrichedGraphNode, getEntityTypeColor } from "@/lib/api";

interface Props {
  nodes: EnrichedGraphNode[];
  selectedNodeId?: string | null;
  onSelectNode: (node: EnrichedGraphNode) => void;
  onClearSelection?: () => void;
}

export default function GraphSearch({
  nodes,
  selectedNodeId,
  onSelectNode,
  onClearSelection,
}: Props) {
  const [query, setQuery] = useState("");
  const [isOpen, setIsOpen] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return [];
    return nodes
      .filter((n) => {
        const matchName = n.name.toLowerCase().includes(q);
        const matchType = n.entity_type.toLowerCase().includes(q);
        const matchAlias = n.aliases?.some((a) => a.toLowerCase().includes(q));
        return matchName || matchType || matchAlias;
      })
      .slice(0, 10);
  }, [nodes, query]);

  const handleSelect = (node: EnrichedGraphNode) => {
    onSelectNode(node);
    setQuery(node.name);
    setIsOpen(false);
  };

  const handleClear = () => {
    setQuery("");
    setIsOpen(false);
    if (onClearSelection) {
      onClearSelection();
    }
  };

  return (
    <div className="relative w-full">
      <div className="relative flex items-center">
        <span className="absolute left-3 text-slate-400 text-sm">🔍</span>
        <input
          type="search"
          placeholder="Search entities, accused, organizations by name or type..."
          value={query}
          onChange={(e) => {
            setQuery(e.target.value);
            setIsOpen(true);
          }}
          onFocus={() => {
            if (query.trim()) setIsOpen(true);
          }}
          className="w-full rounded-lg border border-slate-700 bg-slate-900/90 pl-9 pr-9 py-2 text-sm text-slate-100 placeholder-slate-500 shadow-inner focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
        />
        {query && (
          <button
            type="button"
            onClick={handleClear}
            className="absolute right-2.5 text-xs text-slate-400 hover:text-slate-200"
            title="Clear search"
          >
            ✕
          </button>
        )}
      </div>

      {isOpen && filtered.length > 0 && (
        <ul className="absolute z-50 mt-1 max-h-64 w-full overflow-y-auto rounded-lg border border-slate-700 bg-slate-900 shadow-xl backdrop-blur-md">
          {filtered.map((node) => {
            const isSelected = node.id === selectedNodeId;
            const color = getEntityTypeColor(node.entity_type);
            return (
              <li
                key={node.id}
                onClick={() => handleSelect(node)}
                className={`flex cursor-pointer items-center justify-between px-3 py-2 text-xs transition-colors hover:bg-slate-800 ${
                  isSelected ? "bg-slate-800/80 font-medium" : ""
                }`}
              >
                <div className="flex items-center gap-2 truncate">
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: color }}
                  />
                  <span className="truncate text-slate-200">{node.name}</span>
                  <span className="rounded bg-slate-800 px-1.5 py-0.2 text-[10px] text-slate-400 uppercase">
                    {node.entity_type}
                  </span>
                </div>
                <div className="flex items-center gap-2 shrink-0 text-[11px] text-slate-400">
                  {node.rank && (
                    <span className="rounded bg-blue-950 px-1 text-[10px] text-blue-300 border border-blue-900">
                      Rank #{node.rank}
                    </span>
                  )}
                  <span
                    className={`rounded px-1.5 py-0.5 text-[10px] uppercase ${
                      node.verification_status === "confirmed"
                        ? "text-emerald-400"
                        : node.verification_status === "rejected"
                        ? "text-slate-500 line-through"
                        : "text-amber-400"
                    }`}
                  >
                    {node.verification_status}
                  </span>
                </div>
              </li>
            );
          })}
        </ul>
      )}

      {isOpen && query.trim() && filtered.length === 0 && (
        <div className="absolute z-50 mt-1 w-full rounded-lg border border-slate-700 bg-slate-900 p-3 text-center text-xs text-slate-400 shadow-xl">
          No matching entities found for &quot;{query}&quot;
        </div>
      )}
    </div>
  );
}
