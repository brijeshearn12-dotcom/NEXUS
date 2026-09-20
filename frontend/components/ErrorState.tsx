// ErrorState.tsx — Shown when an API call or operation fails
"use client";

export default function ErrorState({ message = "An error occurred." }: { message?: string }) {
  return (
    <div className="flex h-40 items-center justify-center rounded border border-red-700 bg-red-950 text-red-400">
      <span>⚠ {message}</span>
    </div>
  );
}
