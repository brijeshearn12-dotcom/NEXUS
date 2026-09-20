// ReportDownloadButton.tsx — Triggers PDF report download
"use client";

interface Props {
  caseId: string;
}

export default function ReportDownloadButton({ caseId }: Props) {
  const handleDownload = async () => {
    const url = `${process.env.NEXT_PUBLIC_API_BASE_URL}/report/${caseId}`;
    window.open(url, "_blank");
  };

  return (
    <button
      onClick={handleDownload}
      className="rounded bg-blue-700 px-4 py-2 text-sm font-medium text-white hover:bg-blue-600"
    >
      Download Report
    </button>
  );
}
