// ReportDownloadButton.tsx — Triggers PDF investigation report download
"use client";

import React, { useState } from "react";

interface Props {
  caseId: string;
  className?: string;
}

export default function ReportDownloadButton({ caseId, className }: Props) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleDownload = async () => {
    setDownloading(true);
    setError(null);

    const defaultApiUrl =
      process.env.NODE_ENV === "production"
        ? "https://nexus-backend-obb9.onrender.com"
        : "http://localhost:8000";
    const apiBase = (
      process.env.NEXT_PUBLIC_API_URL ||
      process.env.NEXT_PUBLIC_API_BASE_URL ||
      defaultApiUrl
    )
      .trim()
      .replace(/\/+$/, "")
      .replace(/\/health\/?$/, "");

    try {
      const url = `${apiBase}/api/cases/${caseId}/report`;
      const res = await fetch(url);
      if (!res.ok) {
        throw new Error(`Report generation failed (${res.status})`);
      }
      const blob = await res.blob();
      const downloadUrl = window.URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = downloadUrl;
      a.download = `NEXUS_Investigation_Dossier_${caseId}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(downloadUrl);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Download failed";
      setError(msg);
      // Fallback: direct window.open
      window.open(`${apiBase}/report/${caseId}`, "_blank");
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="inline-flex flex-col items-start">
      <button
        onClick={handleDownload}
        disabled={downloading}
        className={
          className ||
          "inline-flex items-center gap-1.5 rounded bg-blue-700 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-blue-600 disabled:opacity-60"
        }
        title="Download official PDF investigation dossier with complete provenance appendix"
      >
        {downloading ? (
          <>
            <svg className="h-3.5 w-3.5 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            <span>Generating Dossier...</span>
          </>
        ) : (
          <>
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M12 10v6m0 0l-3-3m3 3l3-3m2 8H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>Export Dossier (PDF)</span>
          </>
        )}
      </button>
      {error && <span className="mt-1 text-[10px] text-rose-400">{error}</span>}
    </div>
  );
}
