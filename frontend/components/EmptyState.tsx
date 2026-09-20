// EmptyState.tsx — Shown when a list/view has no data
"use client";

export default function EmptyState({ message = "No data found." }: { message?: string }) {
  return (
    <div className="flex h-40 items-center justify-center text-gray-500">
      <span>{message}</span>
    </div>
  );
}
