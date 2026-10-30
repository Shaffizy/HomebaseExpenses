import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { Card, ErrorState, PageHeader, Spinner, StatusBadge, formatMoney } from "../components/ui";
import { errorMessage, listExpenses } from "../lib/api";
import { ALL_STATUSES, STATUS_LABELS } from "../lib/types";
function actionStatusesFor(role) {
    switch (role) {
        case "REQUESTER":
            return ["DRAFT", "RETURNED"];
        case "REVIEWER":
            return ["IN_REVIEW", "DRAFT", "RETURNED"];
        case "APPROVER":
            return ["SUBMITTED"];
        default:
            return [];
    }
}
const ACTION_LIST_LABEL = {
    REQUESTER: "Your drafts & returns",
    REVIEWER: "Your reviews, drafts and returns",
    APPROVER: "Waiting for your approval",
    ADMIN: "All active expenses",
};
const STATUS_ACCENT = {
    DRAFT: "bg-[#a3a3a3]",
    IN_REVIEW: "bg-[#e0e7ff] text-[#3730a3]",
    SUBMITTED: "bg-[#60a5fa]",
    APPROVED: "bg-[#4ade80]",
    RETURNED: "bg-[#fbbf24]",
    REJECTED: "bg-[#f87171]",
    CLOSED: "bg-[#a8a29e]",
};
export function DashboardPage() {
    const { user } = useAuth();
    const [today] = useState(() => new Date().toLocaleDateString());
    const countResults = useQueries({
        queries: ALL_STATUSES.map((status) => ({
            queryKey: ["expenses", "count", status],
            queryFn: () => listExpenses({ status, page: 1 }),
            staleTime: 30_000,
        })),
    });
    const actionStatuses = actionStatusesFor(user?.role);
    const needsActionQuery = useQuery({
        queryKey: ["expenses", "needs-action", user?.role],
        queryFn: async () => {
            const pages = await Promise.all(actionStatuses.map((status) => listExpenses({ status, page: 1 })));
            return pages.flatMap((page) => page.results);
        },
        enabled: actionStatuses.length > 0,
    });
    const countsLoading = countResults.some((q) => q.isLoading);
    const countsError = countResults.find((q) => q.isError);
    return (<div>
      <PageHeader title="Dashboard" subtitle={user?.role === "ADMIN"
            ? "Admin view — workflow overview for your organization."
            : `Good to see you, ${user?.name ?? ""}. Here is what needs you.`}/>

      {/* strip */}
      <section className="overflow-hidden rounded-lg border border-[var(--color-line)] bg-white shadow-[0_8px_30px_rgba(14,26,46,0.06)]">
        <div className="flex items-center justify-between border-b border-[var(--color-line)] bg-[var(--color-linen)] px-5 py-3">
          <span className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/50">
            Expenses by status
          </span>
          <span className="hidden text-xs font-semibold text-black/40 sm:block">
            {user?.organization.name} · {today}
          </span>
        </div>

        {countsLoading ? (<div className="flex justify-center py-10">
            <Spinner className="h-8 w-8"/>
          </div>) : countsError ? (<div className="p-5">
            <ErrorState message={errorMessage(countsError.error)} onRetry={() => countResults.forEach((q) => q.refetch())}/>
          </div>) : (<div className="grid grid-cols-2 divide-x divide-y divide-[var(--color-line)] sm:grid-cols-4 lg:grid-cols-7">
            {ALL_STATUSES.map((status, index) => (<div key={status} className="bg-white px-4 py-4">
                <div className="flex items-center gap-2">
                  <span className={`h-2 w-2 rounded-full ${STATUS_ACCENT[status] ?? "bg-black/20"}`}/>
                  <span className="text-[11px] font-bold uppercase tracking-normal text-black/55">
                    {STATUS_LABELS[status]}
                  </span>
                </div>
                <p className="font-display mt-2 text-[28px] font-extrabold leading-none tracking-normal text-[var(--color-ink)]">
                  {countResults[index].data?.count ?? 0}
                </p>
              </div>))}
          </div>)}
      </section>

      <section className="mt-7">
        <div className="mb-3 flex items-baseline justify-between gap-3">
          <h2 className="font-display text-[15px] font-bold tracking-normal text-[var(--color-ink)]">
            {ACTION_LIST_LABEL[user?.role ?? ""] ?? "Needs your action"}
          </h2>
          <Link to="/expenses" className="text-xs font-semibold text-[var(--color-rust)] hover:underline">
            View all expenses →
          </Link>
        </div>

        {needsActionQuery.isLoading ? (<div className="flex justify-center py-10">
            <Spinner className="h-8 w-8"/>
          </div>) : needsActionQuery.isError ? (<ErrorState message={errorMessage(needsActionQuery.error)} onRetry={() => needsActionQuery.refetch()}/>) : needsActionQuery.data && needsActionQuery.data.length === 0 ? (<Card>
            <p className="text-sm leading-6 text-black/60">Nothing needs your attention right now.</p>
          </Card>) : (<Card className="!p-0 overflow-hidden">
            <ul className="divide-y divide-[var(--color-line)]">
              {needsActionQuery.data?.map((expense) => (<li key={expense.id}>
                  <Link to={`/expenses/${expense.id}`} className="flex items-center justify-between gap-4 px-5 py-4 transition hover:bg-[var(--color-linen)]/60">
                    <div className="min-w-0">
                      <p className="truncate font-mono text-xs font-bold tracking-normal text-[var(--color-ink)]">
                        {expense.expense_number}
                      </p>
                      <p className="truncate text-sm font-semibold text-[var(--color-ink)]">{expense.category_name}</p>
                      <p className="truncate text-xs text-black/55">
                        {expense.department}
                        {expense.assigned_approver_name ? ` · → ${expense.assigned_approver_name}` : ""}
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <span className="hidden font-mono text-xs font-semibold tabular-nums text-[var(--color-ink)] sm:inline">
                        {formatMoney(expense.currency, expense.total)}
                      </span>
                      <StatusBadge status={expense.status}/>
                    </div>
                  </Link>
                </li>))}
            </ul>
          </Card>)}
      </section>
    </div>);
}
