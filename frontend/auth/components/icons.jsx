// Inline SVG icon set (stroke style, currentColor). No emoji anywhere.
function base({ size = 18, children, ...props }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" {...props}>
      {children}
    </svg>
  );
}

export function BellIcon(props) {
  return base({
    ...props,
    children: (
      <>
        <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
        <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
      </>
    ),
  });
}

export function MenuIcon(props) {
  return base({
    ...props,
    children: (
      <>
        <path d="M4 6h16" />
        <path d="M4 12h16" />
        <path d="M4 18h16" />
      </>
    ),
  });
}

export function SendIcon(props) {
  return base({
    ...props,
    children: (
      <>
        <path d="m22 2-7 20-4-9-9-4Z" />
        <path d="M22 2 11 13" />
      </>
    ),
  });
}

export function SparkleIcon({ size = 14, ...props }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor"
      aria-hidden="true" {...props}>
      <path d="M12 2l2.1 6.1L20.5 10l-6.4 1.9L12 18l-2.1-6.1L3.5 10l6.4-1.9Z" />
    </svg>
  );
}

export function ChevronDownIcon({ size = 14, ...props }) {
  return base({
    size,
    ...props,
    children: <path d="M6 9l6 6 6-6" />,
  });
}

export function CheckIcon({ size = 14, ...props }) {
  return base({
    size,
    strokeWidth: 2.5,
    ...props,
    children: <path d="M20 6L9 17l-5-5" />,
  });
}

export function BriefcaseIcon(props) {
  return base({
    ...props,
    children: (
      <>
        <rect x="2" y="7" width="20" height="14" rx="2" />
        <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
      </>
    ),
  });
}

export function SunIcon(props) {
  return base({
    ...props,
    children: (
      <>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2" />
        <path d="M12 20v2" />
        <path d="m4.93 4.93 1.41 1.41" />
        <path d="m17.66 17.66 1.41 1.41" />
        <path d="M2 12h2" />
        <path d="M20 12h2" />
        <path d="m6.34 17.66-1.41 1.41" />
        <path d="m19.07 4.93-1.41 1.41" />
      </>
    ),
  });
}

export function MoonIcon(props) {
  return base({
    ...props,
    children: <path d="M12 3a6 6 0 0 0 9 9 9 9 0 1 1-9-9Z" />,
  });
}
