import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errorMessage, listExpenses } from "../lib/api";
import { ALL_STATUSES, STATUS_LABELS } from "../lib/types";
import { StyledSelect } from "../components/StyledSelect";
import { ExpenseDownload } from "../components/ExpenseDownload";
import { Card, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge, formatMoney, } from "../components/ui";
const PAGE_SIZE = 20;
function useDebounced(value, delayMs = 300) {
    const [debounced, setDebounced] = useState(value);
    useEffect(() => {
        const timer = setTimeout(() => setDebounced(value), delayMs);
        return () => clearTimeout(timer);
    }, [value, delayMs]);
    return debounced;
}
export function ExpensesPage() {
    const { user } = useAuth();
    const [searchInput, setSearchInput] = useState("");
    const search = useDebounced(searchInput);
    const [status, setStatus] = useState("");
    const [page, setPage] = useState(1);
    const searchPending = searchInput !== search;
    const query = useQuery({
        queryKey: ["expenses", { page, search, status }],
        queryFn: () => listExpenses({ page, search, status: status }),
    });
    const totalPages = Math.max(1, Math.ceil((query.data?.count ?? 0) / PAGE_SIZE));
    return (<div>
      <PageHeader title="Expenses" subtitle="Search, filter, and open any expense in your organization." actions={["REQUESTER", "REVIEWER"].includes(user?.role) && (<Link to="/expenses/new" className="rounded-full bg-[var(--color-rust)] px-5 py-2.5 text-sm font-bold text-white shadow-[0_8px_18px_rgba(230,23,29,0.12)] hover:bg-[var(--color-rust-hover)]">
              New expense
            </Link>)}/>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative">
          <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-black/35">
            <SearchIcon />
          </span>
          <input value={searchInput} onChange={(e) => { setSearchInput(e.target.value); setPage(1); }} placeholder="Search number, name, department..." className="w-[300px] rounded-full border border-[var(--color-line)] bg-white py-2.5 pl-9 pr-4 text-sm font-medium text-[var(--color-ink)] placeholder:text-black/35 focus:border-[var(--color-rust)] focus:outline-none focus:ring-2 focus:ring-[var(--color-rust)]/15"/>
        </div>
        <StyledSelect className="w-48 max-w-full" label="Expense status" value={status} onChange={(value) => { setStatus(value); setPage(1); }} options={[{ value: "", label: "All statuses" }, ...ALL_STATUSES.map((s) => ({ value: s, label: STATUS_LABELS[s] }))]}/>
      </div>

      {query.isLoading ? (<div className="flex justify-center py-20">
          <Spinner className="h-8 w-8"/>
        </div>) : query.isError ? (<ErrorState message={errorMessage(query.error)} onRetry={() => query.refetch()}/>) : query.data && query.data.results.length === 0 ? (<EmptyState title="No expenses found" description={search || status ? "Try clearing the search or filter." : "Create your first expense to get started."} action={["REQUESTER", "REVIEWER"].includes(user?.role) && !search && !status ? (<Link to="/expenses/new" className="rounded-full bg-[var(--color-ink)] px-5 py-2.5 text-sm font-bold text-white hover:bg-[var(--color-ink-soft)]">
                New expense
              </Link>) : undefined}/>) : (<Card className="!p-0 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-[var(--color-line)] text-sm">
              <thead className="bg-[var(--color-linen)]">
                <tr className="text-left font-mono text-[11px] font-bold uppercase tracking-normal text-black/50">
                  <th className="px-4 py-3">Expense</th>
                  <th className="px-4 py-3">Assigned to</th>
                  <th className="px-4 py-3">Department</th>
                  <th className="px-4 py-3 text-right">Total</th>
                  <th className="px-4 py-3">Branch</th>
                  <th className="px-4 py-3">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--color-line)] bg-white">
                {query.data?.results.map((expense) => (<tr key={expense.id} className="transition hover:bg-[var(--color-linen)]/55">
                    <td className="px-4 py-3.5">
                      <Link to={`/expenses/${expense.id}`} className="group inline-flex flex-col">
                        <span className="font-mono text-xs font-bold tracking-normal text-[var(--color-ink)] group-hover:underline">
                          {expense.expense_number}
                        </span>
                        <span className="max-w-[22ch] truncate text-sm font-semibold leading-4 text-[var(--color-ink)]">
                          {expense.category_name}
                        </span>
                      </Link>
                    </td>
                    <td className="px-4 py-3.5 text-sm font-medium text-black/70">
                      {expense.assigned_approver_name ?? (<span className="text-black/35">— Default —</span>)}
                    </td>
                    <td className="px-4 py-3.5 text-sm text-black/70">{expense.department}</td>
                    <td className="px-4 py-3.5 text-right font-mono text-sm font-semibold tabular-nums text-[var(--color-ink)]">
                      {formatMoney(expense.currency, expense.total)}
                    </td>
                    <td className="px-4 py-3.5 font-mono text-xs text-black/55">{expense.branch ?? "—"}</td>
                    <td className="px-4 py-3.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={expense.status}/>
                        <ExpenseDownload expense={expense}/>
                      </div>
                    </td>
                  </tr>))}
              </tbody>
            </table>
          </div>
        </Card>)}

      {query.data && query.data.count > PAGE_SIZE && (<div className="mt-4 flex items-center justify-between text-sm">
          <button onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={page <= 1 || query.isFetching || searchPending} className="rounded-full border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-semibold text-[var(--color-ink)] hover:bg-[var(--color-linen)] disabled:opacity-40">
            Previous
          </button>
          <span className="font-mono text-xs font-semibold tracking-normal text-black/50">
            Page {page} of {totalPages} · {query.data.count} expenses
          </span>
          <button onClick={() => setPage((p) => Math.min(totalPages, p + 1))} disabled={page >= totalPages || query.isFetching || searchPending} className="rounded-full border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-semibold text-[var(--color-ink)] hover:bg-[var(--color-linen)] disabled:opacity-40">
            Next
          </button>
        </div>)}
    </div>);
}
function SearchIcon() {
    return (<svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden>
      <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M11 11L13.5 13.5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>);
}
