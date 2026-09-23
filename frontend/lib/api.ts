/**
 * Centralized API client and data types for NEXUS frontend.
 */

export interface ProvenanceData {
  tier: string;
  source_ref: string;
  method: string;
  confidence: number;
  extracted_at?: string;
  metadata?: Record<string, unknown>;
}

export interface EntityItem {
  id: string;
  case_id?: string;
  document_id?: string;
  name: string;
  entity_type: string;
  aliases?: string[];
  provenance: ProvenanceData;
  verification_status: "unverified" | "confirmed" | "rejected";
  evidence_snippet?: string;
  created_at: string;
  updated_at: string;
  metadata?: Record<string, unknown>;
}

export interface CorpusDocument {
  id: string;
  case_id?: string;
  title: string;
  court?: string;
  date?: string;
  source_ref?: string;
  source_url?: string;
  text_length?: number;
  entities_count: number;
  extraction_status: "extracted" | "pending";
  verification_status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface BatchExtractionResult {
  status: string;
  total_documents: number;
  successful_documents: number;
  failed_documents: number;
  total_entities_extracted: number;
  total_entities_created_or_updated?: number;
  entity_counts_by_type: Record<string, number>;
  entity_counts_by_method: Record<string, number>;
  processing_duration_sec: number;
  error_details: Array<{ document_id: string; error: string }>;
  results?: Array<{
    document_id: string;
    status: string;
    entities_extracted?: number;
    error?: string;
  }>;
}

export interface SingleExtractionResult {
  document_id: string;
  case_id?: string;
  status: string;
  entities_extracted: number;
  by_method: Record<string, number>;
  by_type?: Record<string, number>;
  gemini_used: boolean;
  gemini_reason?: string | null;
  filtered_legal_roles_count?: number;
  entities: EntityItem[];
}

export function getApiUrl(): string {
  const defaultUrl =
    process.env.NODE_ENV === "production"
      ? "https://nexus-backend-obb9.onrender.com"
      : "http://localhost:8000";

  const raw = process.env.NEXT_PUBLIC_API_URL || defaultUrl;
  return raw.trim().replace(/\/+$/, "").replace(/\/health\/?$/, "");
}

export interface FetchResult<T> {
  ok: boolean;
  data?: T;
  errorMessage?: string;
}

export async function apiRequest<T>(
  endpoint: string,
  options?: RequestInit,
  timeoutMs: number = 30000
): Promise<FetchResult<T>> {
  const baseUrl = getApiUrl();
  const url = endpoint.startsWith("http") ? endpoint : `${baseUrl}${endpoint.startsWith("/") ? "" : "/"}${endpoint}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      ...options,
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
        ...(options?.headers || {}),
      },
      signal: controller.signal,
    });
    clearTimeout(timeoutId);

    if (!res.ok) {
      let detail = "";
      try {
        const text = await res.text();
        try {
          const json = JSON.parse(text);
          detail = json.detail || json.message || json.error || "";
        } catch {
          if (text && text.length < 150) {
            detail = text.trim();
          }
        }
      } catch {
        // ignore
      }

      return {
        ok: false,
        errorMessage: detail ? `HTTP ${res.status}: ${detail}` : `HTTP Error ${res.status}: ${res.statusText}`,
      };
    }

    const data = (await res.json()) as T;
    return { ok: true, data };
  } catch (err: unknown) {
    clearTimeout(timeoutId);
    if (err instanceof Error && err.name === "AbortError") {
      return { ok: false, errorMessage: `Request timed out after ${timeoutMs / 1000}s` };
    }
    const message = err instanceof Error ? err.message : "Network request failed";
    return { ok: false, errorMessage: `Network/CORS error: ${message}` };
  }
}

// ==========================================
// Task 6.1 — Graph, Reasoning & Verification Types
// ==========================================

export interface BackendGraphNode {
  id: string;
  name: string;
  entity_type: string;
  aliases?: string[];
  case_id?: string;
  verification_status: "unverified" | "confirmed" | "rejected";
  provenance: ProvenanceData;
  evidence_snippet?: string;
}

export interface BackendGraphEdge {
  edge_id: string;
  source_entity_id: string;
  target_entity_id: string;
  edge_type: string;
  weight: number;
  case_ids?: string[];
  document_ids?: string[];
  evidence?: string;
  provenance: ProvenanceData;
  verification_status: "unverified" | "confirmed" | "rejected";
  created_at?: string;
}

export interface BackendGraphResponse {
  case_id: string;
  nodes: BackendGraphNode[];
  edges: BackendGraphEdge[];
  node_count: number;
  edge_count: number;
}

export interface ReasoningTrailData {
  input_refs: string[];
  evidence: string;
  reasoning: string;
  result: string;
  confidence: number;
  source: string;
}

export interface RankedIndividual {
  entity_id: string;
  canonical_name: string;
  degree: number;
  raw_degree: number;
  betweenness: number;
  pagerank: number;
  combined_score: number;
  rank: number;
  community_id: number;
  role_description?: string;
  trail: ReasoningTrailData;
}

export interface CommunityData {
  community_id: number;
  member_ids: string[];
  member_names: string[];
  size: number;
}

export interface PatternFlagItem {
  flag_id: string;
  flag_type: string;
  entity_id: string;
  canonical_name: string;
  case_id: string;
  severity: "high" | "medium" | "low";
  description: string;
  verification_status: "unverified" | "confirmed" | "rejected";
  trail: ReasoningTrailData;
}

export interface BackendAnalysisResponse {
  case_id: string;
  status: string;
  node_count: number;
  edge_count: number;
  communities_count: number;
  ranked_individuals: RankedIndividual[];
  communities: CommunityData[];
  flags: PatternFlagItem[];
  reasoning_trails?: Record<string, ReasoningTrailData>;
}

export interface EnrichedGraphNode extends BackendGraphNode {
  combined_score: number;
  rank?: number | null;
  community_id?: number | null;
  betweenness?: number;
  pagerank?: number;
  degree?: number;
  raw_degree?: number;
  role_description?: string;
  trail?: ReasoningTrailData;
}

export interface EnrichedGraphEdge extends BackendGraphEdge {
  id: string;
  source: string;
  target: string;
}

export const ENTITY_TYPE_COLORS: Record<string, string> = {
  ACCUSED: "#EF4444",
  PERSON: "#EF4444",
  ORGANIZATION: "#8B5CF6",
  LOCATION: "#06B6D4",
  VEHICLE: "#10B981",
  PHONE: "#14B8A6",
  LAWYER: "#F59E0B",
  JUDGE: "#6B7280",
  OTHER: "#3B82F6",
};

export function getEntityTypeColor(type: string): string {
  const normalized = (type || "").toUpperCase();
  return ENTITY_TYPE_COLORS[normalized] || ENTITY_TYPE_COLORS.OTHER;
}

export function getNodeSize(combinedScore: number): number {
  const clamped = Math.max(0, Math.min(1, combinedScore || 0));
  return Math.round(24 + clamped * 32);
}

export function transformBackendGraph(
  graphData: BackendGraphResponse,
  analysisData?: BackendAnalysisResponse
): { nodes: EnrichedGraphNode[]; edges: EnrichedGraphEdge[] } {
  const rankedMap = new Map<string, RankedIndividual>();
  if (analysisData?.ranked_individuals) {
    for (const r of analysisData.ranked_individuals) {
      if (r.entity_id) rankedMap.set(r.entity_id, r);
      if (r.canonical_name) rankedMap.set(r.canonical_name.toLowerCase(), r);
    }
  }

  const nodes: EnrichedGraphNode[] = graphData.nodes.map((node) => {
    const ranked =
      rankedMap.get(node.id) ||
      (node.name ? rankedMap.get(node.name.toLowerCase()) : undefined);

    const combined_score = ranked ? ranked.combined_score : 0.05;
    const trail = ranked?.trail || {
      input_refs: [node.id, ...(node.aliases || [])],
      evidence:
        node.evidence_snippet ||
        `Entity extracted from case documents with confidence ${(node.provenance?.confidence ?? 1.0).toFixed(2)}`,
      reasoning: `Extracted via ${node.provenance?.method || "automated pipeline"} (tier: ${
        node.provenance?.tier || "primary"
      }). Verification status: ${node.verification_status}.`,
      result: `${node.name} (${node.entity_type})`,
      confidence: node.provenance?.confidence ?? 0.8,
      source: node.provenance?.source_ref || node.case_id || "Case Record",
    };

    return {
      ...node,
      combined_score,
      rank: ranked?.rank ?? null,
      community_id: ranked?.community_id ?? null,
      betweenness: ranked?.betweenness,
      pagerank: ranked?.pagerank,
      degree: ranked?.degree,
      raw_degree: ranked?.raw_degree,
      role_description: ranked?.role_description,
      trail,
    };
  });

  const edges: EnrichedGraphEdge[] = graphData.edges.map((edge) => ({
    ...edge,
    id: edge.edge_id || `${edge.source_entity_id}-${edge.target_entity_id}`,
    source: edge.source_entity_id,
    target: edge.target_entity_id,
  }));

  return { nodes, edges };
}

export async function fetchCaseGraph(caseId: string): Promise<FetchResult<BackendGraphResponse>> {
  return apiRequest<BackendGraphResponse>(`/api/cases/${caseId}/graph`);
}

export async function fetchCaseAnalysis(caseId: string): Promise<FetchResult<BackendAnalysisResponse>> {
  return apiRequest<BackendAnalysisResponse>(`/api/cases/${caseId}/analysis`);
}

export async function verifyEntity(
  entityId: string,
  status: "confirmed" | "rejected" | "unverified",
  notes?: string
): Promise<FetchResult<{ status: string; entity_id: string; verification_status: string }>> {
  return apiRequest<{ status: string; entity_id: string; verification_status: string }>(
    `/api/entities/${entityId}/verify`,
    {
      method: "PATCH",
      body: JSON.stringify({
        verification_status: status,
        analyst_id: "analyst-1",
        notes: notes || `Analyst set verification status to ${status}`,
      }),
    }
  );
}

export async function verifyFlag(
  caseId: string,
  flagId: string,
  status: "confirmed" | "rejected" | "unverified",
  notes?: string
): Promise<FetchResult<{ status: string; flag_id: string; verification_status: string }>> {
  return apiRequest<{ status: string; flag_id: string; verification_status: string }>(
    `/api/cases/${caseId}/flags/${flagId}/verify`,
    {
      method: "PATCH",
      body: JSON.stringify({
        verification_status: status,
        analyst_id: "analyst-1",
        notes: notes || `Analyst verified flag as ${status}`,
      }),
    }
  );
}

// ==========================================
// Task 6.2 — Guided Flow, Audit Trail, Validation & What-If
// ==========================================

export interface AuditLogItem {
  id: string;
  case_id?: string;
  actor: string;
  action: string;
  timestamp: string;
  result_summary?: string;
  entity_type?: string;
  entity_id?: string;
  verification_status?: string;
  input_summary?: Record<string, unknown>;
}

export interface AuditTrailResponse {
  case_id: string;
  total: number;
  items: AuditLogItem[];
}

export interface ValidationDatasetInfo {
  name: string;
  network_type?: string;
  node_count?: number;
  edge_count?: number;
  relationship_categories?: string[];
}

export interface ValidationSourceReference {
  citation?: string;
  primary_source_document?: string;
  academic_reference?: string;
  doi?: string;
  source_repository?: string;
}

export interface ValidationResponse {
  status: string;
  dataset: ValidationDatasetInfo;
  source_reference: ValidationSourceReference;
  ground_truth_count: number;
  top_k: number;
  matches: number;
  score: string;
  validation_limitations: string[];
  legal_notice?: string;
}

export interface SimulationImpactSummary {
  requested_exclusions_count: number;
  removed_nodes_count: number;
  original_nodes?: number;
  simulated_nodes?: number;
  original_edges?: number;
  simulated_edges?: number;
  original_communities_count?: number;
  simulated_communities_count?: number;
  rankings_changed?: boolean;
  communities_changed?: boolean;
}

export interface SimulationResponse {
  status: string;
  case_id: string;
  reason?: string;
  excluded_node_ids: string[];
  actually_removed_node_ids?: string[];
  unknown_node_ids?: string[];
  original_top_individuals: RankedIndividual[];
  simulated_top_individuals: RankedIndividual[];
  communities: CommunityData[];
  flags: PatternFlagItem[];
  changed: boolean;
  impact_summary?: SimulationImpactSummary;
}

export interface CaseExtractResult {
  case_id: string;
  status: string;
  documents_count: number;
  entities_extracted: number;
  already_extracted: boolean;
  message: string;
}

export interface CaseResolveResult {
  case_id: string;
  entities_checked: number;
  candidate_pairs: number;
  merges_created: number;
  merges_skipped: number;
}

export interface CaseBuildGraphResult {
  case_id: string;
  nodes: number;
  edges_created: number;
  edges_updated: number;
}

export async function extractCase(
  caseId: string,
  enableGeminiFallback: boolean = true
): Promise<FetchResult<CaseExtractResult>> {
  return apiRequest<CaseExtractResult>(
    `/api/cases/${caseId}/extract?enable_gemini_fallback=${enableGeminiFallback}`,
    { method: "POST" },
    60000
  );
}

export async function resolveCaseAliases(
  caseId: string,
  threshold: number = 0.85
): Promise<FetchResult<CaseResolveResult>> {
  return apiRequest<CaseResolveResult>(
    `/api/cases/${caseId}/resolve?threshold=${threshold}`,
    { method: "POST" },
    45000
  );
}

export async function buildCaseGraph(caseId: string): Promise<FetchResult<CaseBuildGraphResult>> {
  return apiRequest<CaseBuildGraphResult>(
    `/api/cases/${caseId}/build-graph`,
    { method: "POST" },
    45000
  );
}

export async function fetchCaseAudit(
  caseId: string,
  limit: number = 100
): Promise<FetchResult<AuditTrailResponse>> {
  return apiRequest<AuditTrailResponse>(`/api/cases/${caseId}/audit?limit=${limit}`);
}

export async function fetchValidationResult(): Promise<FetchResult<ValidationResponse>> {
  return apiRequest<ValidationResponse>("/api/validate");
}

export async function simulateCase(
  caseId: string,
  excludeNodeIds: string[]
): Promise<FetchResult<SimulationResponse>> {
  return apiRequest<SimulationResponse>(`/api/cases/${caseId}/simulate`, {
    method: "POST",
    body: JSON.stringify({ exclude_node_ids: excludeNodeIds }),
  });
}
