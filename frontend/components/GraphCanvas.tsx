"use client";

import React, { useEffect, useRef, useState, useCallback } from "react";
import cytoscape, { Core, EventObject } from "cytoscape";
import {
  EnrichedGraphNode,
  EnrichedGraphEdge,
  getEntityTypeColor,
  getNodeSize,
} from "@/lib/api";

interface Props {
  nodes: EnrichedGraphNode[];
  edges: EnrichedGraphEdge[];
  selectedNodeId?: string | null;
  onSelectNode: (node: EnrichedGraphNode | null) => void;
  isLoading?: boolean;
}

export default function GraphCanvas({
  nodes,
  edges,
  selectedNodeId,
  onSelectNode,
  isLoading = false,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const [currentLayout, setCurrentLayout] = useState<string>("cose");

  // Re-run layout on demand
  const runLayout = useCallback((layoutName: string) => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    let layoutConfig: cytoscape.LayoutOptions;
    if (layoutName === "cose") {
      layoutConfig = {
        name: "cose",
        animate: true,
        animationDuration: 600,
        randomize: false,
        componentSpacing: 100,
        nodeRepulsion: () => 8000,
        nodeOverlap: 20,
        idealEdgeLength: () => 60,
        edgeElasticity: () => 100,
        gravity: 80,
        numIter: 500,
        padding: 40,
      } as cytoscape.LayoutOptions;
    } else if (layoutName === "concentric") {
      layoutConfig = {
        name: "concentric",
        animate: true,
        animationDuration: 500,
        concentric: (ele: cytoscape.NodeSingular) => {
          return (ele.data("combined_score") || 0) * 10;
        },
        levelWidth: () => 2,
        padding: 40,
      } as cytoscape.LayoutOptions;
    } else if (layoutName === "circle") {
      layoutConfig = {
        name: "circle",
        animate: true,
        animationDuration: 500,
        padding: 40,
      } as cytoscape.LayoutOptions;
    } else {
      layoutConfig = {
        name: "breadthfirst",
        directed: false,
        animate: true,
        animationDuration: 500,
        padding: 40,
      } as cytoscape.LayoutOptions;
    }

    const layout = cy.layout(layoutConfig);
    layout.run();
  }, []);

  // Initialize and update Cytoscape instance
  useEffect(() => {
    if (!containerRef.current) return;

    // Build elements
    const elements: cytoscape.ElementDefinition[] = [];

    for (const node of nodes) {
      const color = getEntityTypeColor(node.entity_type);
      const size = getNodeSize(node.combined_score);
      elements.push({
        group: "nodes",
        data: {
          id: node.id,
          label: node.name,
          entity_type: node.entity_type,
          verification_status: node.verification_status,
          combined_score: node.combined_score,
          color,
          size,
          raw_node: node,
        },
      });
    }

    for (const edge of edges) {
      const isSynthetic =
        edge.provenance?.tier === "synthetic" ||
        edge.provenance?.tier === "tier_3" ||
        edge.edge_type === "inferred";
      const width = Math.min(6, Math.max(1.5, (edge.weight || 1) * 1.5));

      elements.push({
        group: "edges",
        data: {
          id: edge.id,
          source: edge.source,
          target: edge.target,
          edge_type: edge.edge_type,
          weight: edge.weight,
          width,
          is_synthetic: isSynthetic ? "true" : "false",
          raw_edge: edge,
        },
      });
    }

    if (cyRef.current) {
      cyRef.current.destroy();
    }

    const cy = cytoscape({
      container: containerRef.current,
      elements,
      style: [
        {
          selector: "node",
          style: {
            "background-color": "data(color)",
            width: "data(size)",
            height: "data(size)",
            label: "data(label)",
            color: "#F1F5F9",
            "font-size": 11,
            "font-weight": "bold",
            "text-valign": "bottom",
            "text-margin-y": 5,
            "text-background-color": "#0F172A",
            "text-background-opacity": 0.85,
            "text-background-padding": "3px",
            "text-background-shape": "roundrectangle",
            "border-width": 2,
            "border-color": "#64748B",
            "transition-property": "border-width, border-color, opacity, width, height",
            "transition-duration": 250,
          },
        },
        {
          selector: 'node[verification_status = "confirmed"]',
          style: {
            "border-width": 3.5,
            "border-color": "#22C55E",
            "border-style": "solid",
          },
        },
        {
          selector: 'node[verification_status = "unverified"]',
          style: {
            "border-width": 2.5,
            "border-color": "#F59E0B",
            "border-style": "solid",
          },
        },
        {
          selector: 'node[verification_status = "rejected"]',
          style: {
            "border-width": 2,
            "border-color": "#64748B",
            "border-style": "dashed",
            opacity: 0.45,
          },
        },
        {
          selector: "node:selected",
          style: {
            "border-width": 4.5,
            "border-color": "#3B82F6",
            "border-style": "solid",
            "text-background-color": "#1E3A8A",
            "text-background-opacity": 1.0,
          },
        },
        {
          selector: "edge",
          style: {
            width: "data(width)",
            "line-color": "#64748B",
            "target-arrow-color": "#64748B",
            "curve-style": "bezier",
            opacity: 0.7,
            "transition-property": "line-color, width, opacity",
            "transition-duration": 200,
          },
        },
        {
          selector: 'edge[is_synthetic = "true"]',
          style: {
            "line-style": "dashed",
            "line-dash-pattern": [6, 4],
            "line-color": "#94A3B8",
            opacity: 0.55,
          },
        },
        {
          selector: 'edge[edge_type = "co_accused"]',
          style: {
            "line-color": "#EF4444",
          },
        },
        {
          selector: 'edge[edge_type = "represented_by"]',
          style: {
            "line-color": "#F59E0B",
          },
        },
        {
          selector: 'edge[edge_type = "testified_against"]',
          style: {
            "line-color": "#3B82F6",
          },
        },
        {
          selector: "edge:selected",
          style: {
            "line-color": "#60A5FA",
            width: 4,
            opacity: 1.0,
          },
        },
      ],
      layout: {
        name: currentLayout,
        animate: false,
        padding: 40,
      } as cytoscape.LayoutOptions,
      wheelSensitivity: 0.25,
      minZoom: 0.15,
      maxZoom: 3.5,
    });

    // Node selection events
    cy.on("tap", "node", (evt: EventObject) => {
      const nodeData = evt.target.data("raw_node") as EnrichedGraphNode;
      onSelectNode(nodeData);
    });

    cy.on("tap", (evt: EventObject) => {
      if (evt.target === cy) {
        onSelectNode(null);
      }
    });

    cyRef.current = cy;
    runLayout(currentLayout);

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [nodes, edges, onSelectNode, currentLayout, runLayout]);

  // Center/focus on selected node when selectedNodeId changes externally
  useEffect(() => {
    if (!cyRef.current) return;
    const cy = cyRef.current;

    cy.nodes().unselect();
    if (selectedNodeId) {
      const target = cy.getElementById(selectedNodeId);
      if (target && target.length > 0) {
        target.select();
        cy.animate(
          {
            center: { eles: target },
            zoom: Math.max(cy.zoom(), 1.2),
          },
          { duration: 400 }
        );
      }
    }
  }, [selectedNodeId]);

  // Control handlers
  const handleZoomIn = () => {
    if (cyRef.current) {
      cyRef.current.animate({
        zoom: cyRef.current.zoom() * 1.3,
      }, { duration: 200 });
    }
  };

  const handleZoomOut = () => {
    if (cyRef.current) {
      cyRef.current.animate({
        zoom: cyRef.current.zoom() / 1.3,
      }, { duration: 200 });
    }
  };

  const handleFit = () => {
    if (cyRef.current) {
      cyRef.current.animate({
        fit: { eles: cyRef.current.elements(), padding: 40 },
      }, { duration: 300 });
    }
  };

  return (
    <div className="relative h-full w-full overflow-hidden rounded-lg border border-slate-700 bg-slate-950 shadow-inner">
      {/* Cytoscape container */}
      <div ref={containerRef} className="h-full w-full" />

      {/* Floating Canvas Controls */}
      <div className="absolute top-3 left-3 z-10 flex flex-wrap items-center gap-1.5 rounded-lg border border-slate-700/80 bg-slate-900/90 p-1.5 shadow-lg backdrop-blur-sm">
        <button
          type="button"
          onClick={handleZoomIn}
          className="rounded px-2.5 py-1 text-xs font-bold text-slate-200 hover:bg-slate-800 hover:text-white"
          title="Zoom In"
        >
          +
        </button>
        <button
          type="button"
          onClick={handleZoomOut}
          className="rounded px-2.5 py-1 text-xs font-bold text-slate-200 hover:bg-slate-800 hover:text-white"
          title="Zoom Out"
        >
          −
        </button>
        <button
          type="button"
          onClick={handleFit}
          className="rounded px-2 py-1 text-xs font-medium text-slate-300 hover:bg-slate-800 hover:text-white"
          title="Fit view to graph"
        >
          Fit
        </button>
        <div className="h-4 w-px bg-slate-700 mx-1" />
        <span className="text-[10px] text-slate-400 uppercase font-medium">Layout:</span>
        <button
          type="button"
          onClick={() => {
            setCurrentLayout("cose");
            runLayout("cose");
          }}
          className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
            currentLayout === "cose"
              ? "bg-blue-600 text-white"
              : "text-slate-300 hover:bg-slate-800"
          }`}
          title="Force-directed spring embedder layout"
        >
          Force
        </button>
        <button
          type="button"
          onClick={() => {
            setCurrentLayout("concentric");
            runLayout("concentric");
          }}
          className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
            currentLayout === "concentric"
              ? "bg-blue-600 text-white"
              : "text-slate-300 hover:bg-slate-800"
          }`}
          title="Centrality concentric rings"
        >
          Centrality
        </button>
        <button
          type="button"
          onClick={() => {
            setCurrentLayout("circle");
            runLayout("circle");
          }}
          className={`rounded px-2 py-1 text-xs font-medium transition-colors ${
            currentLayout === "circle"
              ? "bg-blue-600 text-white"
              : "text-slate-300 hover:bg-slate-800"
          }`}
          title="Circular layout"
        >
          Circle
        </button>
      </div>

      {/* Network Stats Overlay */}
      <div className="absolute bottom-3 left-3 z-10 flex items-center gap-2 rounded-lg border border-slate-700/80 bg-slate-900/80 px-2.5 py-1 text-[11px] text-slate-400 backdrop-blur-sm">
        <span>Nodes: <strong className="text-slate-200">{nodes.length}</strong></span>
        <span>•</span>
        <span>Edges: <strong className="text-slate-200">{edges.length}</strong></span>
      </div>

      {/* Loading overlay */}
      {isLoading && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-slate-950/70 backdrop-blur-xs">
          <div className="h-8 w-8 animate-spin rounded-full border-2 border-blue-500 border-t-transparent" />
          <p className="mt-2 text-xs font-medium text-slate-300">Rendering relationship graph...</p>
        </div>
      )}
    </div>
  );
}
