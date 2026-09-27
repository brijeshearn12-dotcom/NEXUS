"use client";

import React, { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  CrossCaseCorroboration,
  CrossCaseLink,
  CrossCaseSide,
  CrossCaseStatus,
  fetchCaseCrossCaseLinks,
  runCrossCaseMatching,
  verifyCrossCaseLink,
} from "@/lib/api";
import ConfirmRejectControl from "./ConfirmRejectControl";

interface Props {
  caseId: string;
  /** Called after a matching run or an analyst decision (e.g. to refresh the audit trail). */
  onDecision?: () => void;
}

const KIND_LABEL: Record<string, string> = {
  fir_police_station: "Same FIR + police station",
  vehicle: "Same vehicle",
  phone: "Same phone number",
  shared_participant: "Shared participant",
};

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/** Render a verbatim passage with the matched name highlighted. */
function Highlighted({ passage, term }: { passage: string; term: string }) {
  if (!term.trim()) return <>{passage}</>;
  const parts = passage.split(new RegExp(`(${escapeRegExp(term)})`, "ig"));
  return (
    <>
      {parts.map((part, idx) =>
        part.toLowerCase() === term.toLowerCase() ? (
          <mark key={idx} className="rounded bg-amber-500/25 px-0.5 font-semibold text-amber-100">
            {part}
          </mark>
        ) : (
          <React.Fragment key={idx}>{part}</React.Fragment>
        )
      )}
    </>
  );
}

function SideSummary({ label, side, linkToGraph }: { label: string; side: CrossCaseSide; linkToGraph: boolean }) {
  return (
    <div className="min-w-0 rounded border border-slate-800 bg-slate-900/70 p-2">
      <p className="text-[10px] font-bold uppercase tracking-wider text-slate-500">{label}</p>
      <p className="mt-0.5 truncate text-sm font-bold text-slate-100" title={side.matched_name_form}>
        {side.matched_name_form}
      </p>
      {side.entity_name !== side.matched_name_form && (
        <p className="truncate text-[10px] text-slate-500" title={side.entity_name}>
          per-case entity: {side.entity_name}
        </p>
      )}
      {side.is_accused_in_case && <p className="text-[10px] font-medium text-rose-300">marked accused in this case</p>}
      <p className="mt-0.5 truncate text-[10px] text-slate-400" title={side.document_title || side.case_id}>
        {side.document_title || side.case_id}
      </p>
      {linkToGraph && (
        <Link
          href={`/cases/${encodeURIComponent(side.case_id)}/graph`}
          className="text-[10px] font-semibold text-blue-400 hover:text-blue-300"
        >
          Open {side.case_id} &rarr;
        </Link>
      )}
    </div>
  );
}

function EvidenceBlock({ label, side }: { label: string; side: CrossCaseSide }) {
  return (
    <div className="mt-2">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">{label}</p>
        {side.source_url && (
          <a
            href={side.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="shrink-0 text-[10px] font-semibold text-blue-400 hover:text-blue-300"
          >
            Source judgment &#8599;
          </a>
        )}
      </div>
      <blockquote className="mt-1 border-l-2 border-slate-600 pl-2 text-[11px] leading-relaxed text-slate-300">
        &ldquo;
        <Highlighted passage={side.evidence_passage} term={side.matched_name_form} />
        &rdquo;
      </blockquote>
    </div>
  );
}

export default function CrossCaseMatchesPanel({ caseId, onDecision }: Props) {
  const [links, setLinks] = useState<CrossCaseLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [runNote, setRunNote] = useState<string | null>(null);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [openDetails, setOpenDetails] = useState<Record<string, boolean>>({});

  const load = useCallback(async () => {
    setLoading(true);
    const res = await fetchCaseCrossCaseLinks(caseId);
    if (res.ok && res.data) {
      setLinks(res.data.items);
      setError(null);
    } else {
      setError(res.errorMessage || "Could not load cross-case matches.");
    }
    setLoading(false);
  }, [caseId]);

  useEffect(() => {
    load();
  }, [load]);

  const handleRun = async () => {
    setRunning(true);
    setRunNote(null);
    const res = await runCrossCaseMatching();
    if (res.ok && res.data) {
      setRunNote(
        `${res.data.proposals_found} candidate match(es) across ${res.data.distinct_judgments} distinct ` +
          `judgments (${res.data.documents_considered} documents; duplicate copies ignored).`
      );
      await load();
      onDecision?.();
    } else {
      setError(res.errorMessage || "Cross-case matching failed.");
    }
    setRunning(false);
  };

  const decide = async (link: CrossCaseLink, status: CrossCaseStatus) => {
    const res = await verifyCrossCaseLink(link.link_id, status, notes[link.link_id]);
    if (res.ok && res.data) {
      const updated = res.data;
      setLinks((prev) => prev.map((l) => (l.link_id === updated.link_id ? updated : l)));
      setError(null);
      onDecision?.();
    } else {
      setError(res.errorMessage || "Could not record the decision.");
    }
  };

  return (
    <section className="flex flex-col gap-3 rounded-lg border border-slate-700 bg-slate-900/95 p-3.5 text-xs text-slate-300 shadow-lg">
      <div className="border-b border-slate-800 pb-2">
        <div className="flex items-center justify-between gap-2">
          <h3 className="font-bold text-slate-100">Cross-Case Matches</h3>
          <button
            type="button"
            onClick={handleRun}
            disabled={running}
            className="rounded border border-cyan-700 bg-cyan-900/40 px-2 py-1 text-[11px] font-semibold text-cyan-200 hover:bg-cyan-800/50 disabled:opacity-50"
            title="Scan all judgments for candidate matches (never merges identities)"
          >
            {running ? "Matching…" : "Find candidates"}
          </button>
        </div>
        <p className="mt-1 text-[11px] leading-relaxed text-slate-400">
          NEXUS proposes. The investigator verifies. A candidate match does not establish identity or guilt.
        </p>
        {runNote && <p className="mt-1 text-[11px] text-cyan-300">{runNote}</p>}
      </div>

      {error && <div className="rounded border border-rose-800 bg-rose-950/60 p-2 text-rose-300">{error}</div>}

      {loading ? (
        <p className="text-slate-500">Loading candidate matches…</p>
      ) : links.length === 0 ? (
        <p className="text-slate-500">
          No candidate matches involve this case. Use &ldquo;Find candidates&rdquo; to scan the corpus.
        </p>
      ) : (
        links.map((link) => {
          const thisIsA = link.side_a.case_id === caseId;
          const here = thisIsA ? link.side_a : link.side_b;
          const there = thisIsA ? link.side_b : link.side_a;
          const evidenceFor = (c: CrossCaseCorroboration): [string, string] => {
            const a = c.evidence_a || "";
            const b = c.evidence_b || "";
            return thisIsA ? [a, b] : [b, a];
          };
          const detailsOpen = Boolean(openDetails[link.link_id]);
          return (
            <article key={link.link_id} className="rounded-md border border-slate-700 bg-slate-950/60 p-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-bold uppercase tracking-wider text-cyan-300">Candidate match</span>
                <span
                  className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                    link.match_strength === "strong"
                      ? "bg-cyan-950 text-cyan-300 border border-cyan-800"
                      : "bg-slate-800 text-slate-300 border border-slate-700"
                  }`}
                  title={link.score_note}
                >
                  {link.match_strength} · {link.match_score} pts
                </span>
              </div>

              <div className="mt-2 grid grid-cols-2 gap-2">
                <SideSummary label="Entity A · this case" side={here} linkToGraph={false} />
                <SideSummary label="Entity B · other case" side={there} linkToGraph />
              </div>

              <EvidenceBlock label="Evidence A" side={here} />
              <EvidenceBlock label="Evidence B" side={there} />

              <div className="mt-2">
                <p className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Why linked</p>
                <ul className="mt-1 space-y-1">
                  <li className="text-[11px] text-slate-300">
                    • Name match ({link.name_match_basis.replace(/_/g, " ")}): &ldquo;{here.matched_name_form}&rdquo; /
                    &ldquo;{there.matched_name_form}&rdquo;
                  </li>
                  {link.corroboration.map((c) => (
                    <li key={`${c.kind}:${c.value}`} className="text-[11px] text-slate-300">
                      • <span className="font-semibold text-slate-100">{KIND_LABEL[c.kind] || c.kind}</span>: {c.description}
                    </li>
                  ))}
                </ul>
                <button
                  type="button"
                  onClick={() => setOpenDetails((prev) => ({ ...prev, [link.link_id]: !detailsOpen }))}
                  className="mt-1 text-[10px] font-semibold text-blue-400 hover:text-blue-300"
                >
                  {detailsOpen ? "Hide corroborating passages" : "Show corroborating passages"}
                </button>
                {detailsOpen && (
                  <div className="mt-1 space-y-2">
                    {link.corroboration.map((c) => {
                      const [evHere, evThere] = evidenceFor(c);
                      return (
                        <div key={`ev:${c.kind}:${c.value}`} className="rounded border border-slate-800 p-1.5">
                          <p className="text-[10px] font-semibold text-slate-400">{KIND_LABEL[c.kind] || c.kind}</p>
                          <p className="mt-0.5 text-[10px] text-slate-400">A: &ldquo;{evHere}&rdquo;</p>
                          <p className="mt-0.5 text-[10px] text-slate-400">B: &ldquo;{evThere}&rdquo;</p>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              <textarea
                value={notes[link.link_id] ?? link.analyst_notes ?? ""}
                onChange={(e) => setNotes((prev) => ({ ...prev, [link.link_id]: e.target.value }))}
                placeholder="Analyst notes (optional)"
                rows={2}
                className="mt-2 w-full rounded border border-slate-700 bg-slate-900 p-1.5 text-[11px] text-slate-200 placeholder:text-slate-600"
              />

              <div className="mt-2">
                <ConfirmRejectControl
                  currentStatus={link.status === "proposed" ? "unverified" : link.status}
                  pendingLabel="Proposed"
                  size="sm"
                  onConfirm={() => decide(link, "confirmed")}
                  onReject={() => decide(link, "rejected")}
                  onReset={() => decide(link, "proposed")}
                />
              </div>
              {link.reviewed_by && (
                <p className="mt-1 text-[10px] text-slate-500">
                  Last decision by {link.reviewed_by}
                  {link.reviewed_at ? ` · ${new Date(link.reviewed_at).toLocaleString()}` : ""} · recorded in the
                  audit trail
                </p>
              )}
              <p className="mt-2 text-[10px] italic text-slate-500">{link.disclaimer}</p>
            </article>
          );
        })
      )}
    </section>
  );
}
