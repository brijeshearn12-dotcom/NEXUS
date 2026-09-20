// ConfirmRejectControl/index.tsx — Approve or reject an entity extraction
"use client";

interface Props {
  onConfirm: () => void;
  onReject: () => void;
  disabled?: boolean;
}

export default function ConfirmRejectControl({ onConfirm, onReject, disabled = false }: Props) {
  return (
    <div className="flex gap-2">
      <button
        onClick={onConfirm}
        disabled={disabled}
        className="rounded bg-green-700 px-3 py-1 text-xs font-medium text-white hover:bg-green-600 disabled:opacity-40"
      >
        ✓ Confirm
      </button>
      <button
        onClick={onReject}
        disabled={disabled}
        className="rounded bg-red-700 px-3 py-1 text-xs font-medium text-white hover:bg-red-600 disabled:opacity-40"
      >
        ✗ Reject
      </button>
    </div>
  );
}
