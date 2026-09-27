import { useId } from "react";

// Single source for the QuestAI mark. Import from here everywhere.
export default function QuestMark({ size = 40 }) {
  const id = useId();
  return (
    <svg width={size} height={size} viewBox="0 0 256 256" aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#2563eb" />
          <stop offset="1" stopColor="#7c3aed" />
        </linearGradient>
      </defs>
      <rect width="256" height="256" rx="56" fill={`url(#${id})`} />
      <path d="M78 150 L108 122 L128 140 L168 100" stroke="#fff" strokeWidth="20"
        fill="none" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M140 100 L168 100 L168 128" stroke="#fff" strokeWidth="20"
        fill="none" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
