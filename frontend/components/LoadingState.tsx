// LoadingState.tsx — Generic loading skeleton/spinner
"use client";

export default function LoadingState({ message = "Loading…" }: { message?: string }) {
  return (
    <div className="flex h-40 items-center justify-center text-gray-400">
      <span className="mr-2 animate-spin">⏳</span>
      {message}
    </div>
  );
}
