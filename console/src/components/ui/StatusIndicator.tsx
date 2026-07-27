interface StatusIndicatorProps {
  tone: "loading" | "success" | "danger" | "neutral";
  label: string;
}

const toneClasses = {
  loading: "bg-[var(--warning)]",
  success: "bg-[var(--accent)]",
  danger: "bg-[var(--danger)]",
  neutral: "bg-[var(--text-muted)]",
};

export function StatusIndicator({ tone, label }: StatusIndicatorProps) {
  return (
    <span className="inline-flex items-center gap-2 text-xs font-medium text-[var(--text-muted)]">
      <span className={`size-1.5 rounded-full ${toneClasses[tone]}`} aria-hidden="true" />
      {label}
    </span>
  );
}
