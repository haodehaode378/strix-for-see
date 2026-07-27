import type { ReactNode } from "react";

interface PageHeaderProps {
  eyebrow: string;
  title: string;
  description: string;
  actions?: ReactNode;
}

export function PageHeader({ eyebrow, title, description, actions }: PageHeaderProps) {
  return (
    <header className="grid gap-5 border-b border-[var(--border)] pb-7 lg:grid-cols-[1fr_auto] lg:items-end">
      <div>
        <p className="mb-2 text-[11px] font-semibold tracking-[0.16em] text-[var(--accent)] uppercase">
          {eyebrow}
        </p>
        <h1 className="text-3xl font-semibold tracking-[-0.045em] text-[var(--text)] sm:text-4xl">
          {title}
        </h1>
        <p className="mt-3 max-w-[65ch] text-sm leading-6 text-[var(--text-muted)]">
          {description}
        </p>
      </div>
      {actions ? <div className="flex items-center gap-2">{actions}</div> : null}
    </header>
  );
}
