import { Card } from "./ui";
function formatValue(value) {
    if (value === null || value === "")
        return "—";
    return value;
}
export function HistoryList({ history }) {
    if (history.length === 0) {
        return (<Card>
        <p className="text-sm text-black/50">No history recorded yet.</p>
      </Card>);
    }
    return (<Card>
      <h2 className="font-display text-[15px] font-bold tracking-normal text-[var(--color-ink)]">
        Audit history
      </h2>
      <p className="mt-1 text-xs leading-4 text-black/45">Every field change, who made it, and when.</p>
      <ul className="mt-5 divide-y divide-[var(--color-line)]">
        {history.map((entry, index) => (<li key={index} className="py-4 first:pt-0">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <span className="rounded-full bg-[var(--color-ink)] px-2.5 py-1 font-mono text-[11px] font-bold uppercase tracking-normal text-white">
                {entry.type}
                <span className="font-normal opacity-70"> · {entry.source}</span>
              </span>
              <span className="font-mono text-xs text-black/45">
                {new Date(entry.date).toLocaleString()}
                {entry.user ? ` · ${entry.user}` : ""}
              </span>
            </div>
            {Object.keys(entry.changes).length > 0 ? (<dl className="mt-3 space-y-1.5 rounded-lg border border-[var(--color-line)] bg-[var(--color-paper)]/60 p-3">
                {Object.entries(entry.changes).map(([field, [oldValue, newValue]]) => (<div key={field} className="flex flex-wrap items-baseline gap-1.5 text-sm">
                    <span className="font-mono text-xs font-bold uppercase tracking-normal text-black/45">
                      {field}
                    </span>
                    <span className="rounded bg-white px-1.5 py-0.5 font-mono text-xs text-black/50 line-through decoration-black/20">
                      {formatValue(oldValue)}
                    </span>
                    <span className="text-black/30">→</span>
                    <span className="rounded bg-white px-1.5 py-0.5 font-mono text-xs font-semibold text-[var(--color-ink)] ring-1 ring-[var(--color-line)]">
                      {formatValue(newValue)}
                    </span>
                  </div>))}
              </dl>) : (<p className="mt-2 text-sm text-black/40">No field changes</p>)}
          </li>))}
      </ul>
    </Card>);
}
