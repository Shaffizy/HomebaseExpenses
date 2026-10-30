import { STATUS_LABELS } from "../lib/types";
export function buildTimeline(history, expense) {
    const steps = [];
    const chronological = [...history].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime());
    for (const entry of chronological) {
        const statusChange = entry.changes.status;
        if (!statusChange)
            continue;
        const next = statusChange[1];
        if (!next)
            continue;
        steps.push({ status: next, user: entry.user, date: entry.date });
    }
    if (steps.length === 0 || steps[steps.length - 1].status !== expense.status) {
        steps.push({ status: expense.status, user: null, date: expense.updated_at });
    }
    return steps;
}
const DOT = {
    DRAFT: "bg-[#a3a3a3]",
    IN_REVIEW: "bg-[#e0e7ff] text-[#3730a3]",
    SUBMITTED: "bg-[#60a5fa]",
    APPROVED: "bg-[#22c55e]",
    RETURNED: "bg-[#f59e0b]",
    REJECTED: "bg-[#ef4444]",
    CLOSED: "bg-[#a8a29e]",
};
export function StatusTimeline({ history, expense }) {
    const steps = buildTimeline(history, expense);
    return (<ol className="space-y-0">
      {steps.map((step, index) => {
            const isCurrent = index === steps.length - 1;
            const isLast = index === steps.length - 1;
            return (<li key={`${step.status}-${index}`} className="relative flex gap-3 pb-6 last:pb-0">
            {!isLast && (<span className="absolute left-[7px] top-5 h-full w-px bg-[var(--color-line)]" aria-hidden/>)}
            <span className={`mt-1.5 h-3 w-3 shrink-0 rounded-full ring-4 ${isCurrent ? `${DOT[step.status] ?? "bg-[var(--color-rust)]"} ring-[var(--color-rust)]/15` : "bg-black/15 ring-black/5"}`}/>
            <div className="min-w-0">
              <p className={`flex flex-wrap items-center gap-2 text-sm font-bold ${isCurrent ? "text-[var(--color-ink)]" : "text-black/60"}`}>
                {STATUS_LABELS[step.status]}
                {isCurrent && (<span className="rounded-full bg-[var(--color-ink)] px-2 py-0.5 font-mono text-[10px] font-bold uppercase tracking-normal text-white">
                    current
                  </span>)}
              </p>
              <p className="font-mono text-xs leading-4 text-black/45">
                {step.date ? new Date(step.date).toLocaleString() : ""}
                {step.user ? ` · ${step.user}` : ""}
              </p>
            </div>
          </li>);
        })}
    </ol>);
}
