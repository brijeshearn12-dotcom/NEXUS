"use client";

import { useCallback, useEffect, useState } from "react";

interface HealthState {
  status: "loading" | "ok" | "error";
  message?: string;
  timestamp?: string;
}

interface DbHealthState {
  status: "loading" | "ok" | "error";
  database?: string;
  message?: string;
  timestamp?: string;
}

export default function Home() {
  const apiUrl =
    process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

  const [apiHealth, setApiHealth] = useState<HealthState>({
    status: "loading",
  });
  const [dbHealth, setDbHealth] = useState<DbHealthState>({
    status: "loading",
  });
  const [checking, setChecking] = useState<boolean>(false);

  const checkConnectivity = useCallback(async () => {
    setChecking(true);
    const now = new Date().toLocaleTimeString();

    // 1. Check API /health
    try {
      const res = await fetch(`${apiUrl}/health`, {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const data = (await res.json()) as { status: string };
      setApiHealth({
        status: data.status === "ok" ? "ok" : "error",
        message: data.status,
        timestamp: now,
      });
    } catch (err: unknown) {
      setApiHealth({
        status: "error",
        message:
          err instanceof Error ? err.message : "Failed to reach backend",
        timestamp: now,
      });
    }

    // 2. Check Database /health/db
    try {
      const res = await fetch(`${apiUrl}/health/db`, {
        method: "GET",
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      const data = (await res.json()) as {
        status?: string;
        database?: string;
        message?: string;
      };
      if (res.ok && data.status === "ok") {
        setDbHealth({
          status: "ok",
          database: data.database || "connected",
          timestamp: now,
        });
      } else {
        setDbHealth({
          status: "error",
          message: data.message || `HTTP ${res.status}`,
          timestamp: now,
        });
      }
    } catch (err: unknown) {
      setDbHealth({
        status: "error",
        message:
          err instanceof Error
            ? err.message
            : "Failed to query database status",
        timestamp: now,
      });
    } finally {
      setChecking(false);
    }
  }, [apiUrl]);

  useEffect(() => {
    checkConnectivity();
  }, [checkConnectivity]);

  return (
    <main className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 antialiased">
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl p-8 shadow-2xl space-y-8">
        {/* Header */}
        <div className="space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-xs font-semibold bg-emerald-950/80 text-emerald-400 border border-emerald-800/60">
            <span className="h-2 w-2 rounded-full bg-emerald-400 animate-pulse" />
            TASK 1.3: REPOSITORY SKELETON
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-white">
            NEXUS
          </h1>
          <p className="text-slate-400 text-sm sm:text-base leading-relaxed">
            AI-Powered Criminal Network Analysis System &middot; SIH26189GREEN &middot; Ministry of Home Affairs
          </p>
        </div>

        {/* Backend & Database Status Cards */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-xs uppercase tracking-wider text-slate-400 font-semibold">
              System Health &amp; Connectivity
            </h2>
            <span className="text-xs font-mono text-slate-400">
              API: {apiUrl}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* FastAPI Backend Status */}
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-300">
                  FastAPI Backend
                </span>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    apiHealth.status === "ok"
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800/60"
                      : apiHealth.status === "loading"
                        ? "bg-amber-950 text-amber-300 border border-amber-800/60"
                        : "bg-rose-950 text-rose-300 border border-rose-800/60"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      apiHealth.status === "ok"
                        ? "bg-emerald-400 animate-pulse"
                        : apiHealth.status === "loading"
                          ? "bg-amber-400 animate-ping"
                          : "bg-rose-400"
                    }`}
                  />
                  {apiHealth.status === "ok"
                    ? "Online"
                    : apiHealth.status === "loading"
                      ? "Checking..."
                      : "Offline"}
                </span>
              </div>
              <div className="text-xs text-slate-400 font-mono">
                GET /health &rarr;{" "}
                <span className="text-slate-200">
                  {apiHealth.status === "loading"
                    ? "requesting..."
                    : apiHealth.status === "ok"
                      ? "200 OK (ok)"
                      : apiHealth.message}
                </span>
              </div>
              {apiHealth.timestamp && (
                <div className="text-[11px] text-slate-400">
                  Last checked: {apiHealth.timestamp}
                </div>
              )}
            </div>

            {/* MongoDB Atlas Status */}
            <div className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-5 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-slate-300">
                  MongoDB Atlas
                </span>
                <span
                  className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${
                    dbHealth.status === "ok"
                      ? "bg-emerald-950 text-emerald-400 border border-emerald-800/60"
                      : dbHealth.status === "loading"
                        ? "bg-amber-950 text-amber-300 border border-amber-800/60"
                        : "bg-rose-950 text-rose-300 border border-rose-800/60"
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${
                      dbHealth.status === "ok"
                        ? "bg-emerald-400 animate-pulse"
                        : dbHealth.status === "loading"
                          ? "bg-amber-400 animate-ping"
                          : "bg-rose-400"
                    }`}
                  />
                  {dbHealth.status === "ok"
                    ? "Connected"
                    : dbHealth.status === "loading"
                      ? "Checking..."
                      : "Disconnected"}
                </span>
              </div>
              <div className="text-xs text-slate-400 font-mono">
                GET /health/db &rarr;{" "}
                <span className="text-slate-200">
                  {dbHealth.status === "loading"
                    ? "pinging..."
                    : dbHealth.status === "ok"
                      ? "200 OK (connected)"
                      : dbHealth.message}
                </span>
              </div>
              {dbHealth.timestamp && (
                <div className="text-[11px] text-slate-400">
                  Last checked: {dbHealth.timestamp}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center justify-between pt-2 border-t border-slate-800/80">
          <p className="text-xs text-slate-400">
            Phase: Local Repository Skeleton &amp; Service Verification
          </p>
          <button
            type="button"
            onClick={() => checkConnectivity()}
            disabled={checking}
            className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 disabled:text-slate-500 text-white transition duration-150 ease-in-out cursor-pointer shadow"
          >
            {checking ? "Checking..." : "Recheck Status"}
          </button>
        </div>
      </div>
    </main>
  );
}
