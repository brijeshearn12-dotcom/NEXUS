// ValidationBadge.tsx — Shows Noordin Top validation status
"use client";

interface Props {
  status: "validated" | "unvalidated" | "partial";
}

const COLOUR_MAP: Record<Props["status"], string> = {
  validated: "bg-green-700 text-green-100",
  partial: "bg-yellow-700 text-yellow-100",
  unvalidated: "bg-gray-700 text-gray-300",
};

export default function ValidationBadge({ status }: Props) {
  return (
    <span className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${COLOUR_MAP[status]}`}>
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}
