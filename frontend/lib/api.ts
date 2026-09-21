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
