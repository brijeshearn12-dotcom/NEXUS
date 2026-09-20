// GraphSearch.tsx — Search bar for filtering graph nodes by name
"use client";

import { useState } from "react";

interface Props {
  onSearch: (query: string) => void;
}

export default function GraphSearch({ onSearch }: Props) {
  const [value, setValue] = useState("");

  return (
    <input
      type="search"
      placeholder="Search entities…"
      value={value}
      onChange={(e) => {
        setValue(e.target.value);
        onSearch(e.target.value);
      }}
      className="w-full rounded border border-gray-600 bg-gray-900 px-3 py-1.5 text-sm text-gray-200 placeholder-gray-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
    />
  );
}
