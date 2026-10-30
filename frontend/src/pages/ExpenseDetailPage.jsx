import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import toast from "../lib/notifications";
import { Link, useParams } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { ExpenseActions } from "../components/ExpenseActions";
import { ExpensePrint } from "../components/ExpensePrint";
import { ExpenseDownload } from "../components/ExpenseDownload";
import { ExpenseForm } from "../components/ExpenseForm";
import { ExpenseEvidence } from "../components/ExpenseEvidence";
import { CommentThread } from "../components/CommentThread";
import { HistoryList } from "../components/HistoryList";
import { StatusTimeline } from "../components/StatusTimeline";
import { Card, ErrorState, PageHeader, Spinner, formatMoney, } from "../components/ui";
import { errorMessage, getExpense, getHistory, submitExpense, updateExpense } from "../lib/api";
import { EDITABLE_STATUSES } from "../lib/types";
export function ExpenseDetailPage() {
    const { id } = useParams();
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const [tab, setTab] = useState("details");
    const [editing, setEditing] = useState(false);
    const expenseQuery = useQuery({
        queryKey: ["expense", id],
        queryFn: () => getExpense(id),
    });
    const historyQuery = useQuery({
        queryKey: ["expense-history", id],
        queryFn: () => getHistory(id),
        enabled: tab === "history" || !expenseQuery.isLoading,
    });
    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: ["expense", id] });
        queryClient.invalidateQueries({ queryKey: ["expense-history", id] });
        queryClient.invalidateQueries({ queryKey: ["expenses"] });
    };
    const saveMutation = useMutation({
        mutationFn: (payload) => updateExpense(Number(id), payload),
        onSuccess: () => {
            toast.success("Draft saved");
            invalidate();
            setEditing(false);
        },
        onError: (err) => toast.error(errorMessage(err)),
    });
    const submitMutation = useMutation({
        mutationFn: async (payload) => {
            await updateExpense(Number(id), payload);
            return submitExpense(Number(id));
        },
        onSuccess: () => {
            toast.success("Expense submitted for review");
            invalidate();
            setEditing(false);
        },
        onError: (err) => toast.error(errorMessage(err)),
    });
    if (expenseQuery.isLoading) {
        return (<div className="flex justify-center py-20">
        <Spinner className="h-8 w-8"/>
      </div>);
    }
    if (expenseQuery.isError || !expenseQuery.data) {
        return (<ErrorState message={errorMessage(expenseQuery.error) ?? "Expense not found"} onRetry={() => expenseQuery.refetch()}/>);
    }
    const expense = expenseQuery.data;
    const isExpenseer = ["REQUESTER", "REVIEWER"].includes(user?.role);
    const isOwner = user?.id === expense.created_by;
    const isEditable = isExpenseer && isOwner && EDITABLE_STATUSES.includes(expense.status);
    const showForm = isEditable && editing;
    return (<div>
      <PageHeader title={expense.category_name} subtitle={`${expense.expense_number} · ${expense.department || "Department not set"} · ${expense.branch || "Branch not set"}`} actions={<>
            {/* <StatusBadge status={expense.status}/> */}
            {isEditable && !editing && (<button onClick={() => setEditing(true)} className="rounded-full bg-[var(--color-ink)] px-4 py-2 text-sm font-bold text-white hover:bg-[var(--color-ink-soft)]">
                Edit expense
              </button>)}
            <ExpenseActions expense={expense} role={user?.role}/>
            <ExpensePrint expense={expense}/>
            <ExpenseDownload expense={expense}/>
            <Link to="/expenses" className="rounded-full border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-bold text-[var(--color-ink)] hover:bg-[var(--color-linen)]">
              Back
            </Link>
          </>}/>

      <div className="mb-6 inline-flex rounded-full border border-[var(--color-line)] bg-white p-1 shadow-sm">
        {["details", "history"].map((name) => (<button key={name} onClick={() => setTab(name)} className={`rounded-full px-4 py-1.5 text-sm font-bold capitalize transition ${tab === name
                ? "bg-[var(--color-ink)] text-white shadow-sm"
                : "text-black/55 hover:text-[var(--color-ink)]"}`}>
            {name}
          </button>))}
      </div>

      {tab === "history" ? (historyQuery.isLoading ? (<div className="flex justify-center py-16">
            <Spinner className="h-8 w-8"/>
          </div>) : historyQuery.isError ? (<ErrorState message={errorMessage(historyQuery.error)} onRetry={() => historyQuery.refetch()}/>) : (<HistoryList history={historyQuery.data ?? []}/>)) : showForm ? (<ExpenseForm expense={expense} saving={saveMutation.isPending || submitMutation.isPending} onSave={(payload) => saveMutation.mutate(payload)} onSubmitAndSend={(payload) => submitMutation.mutate(payload)}/>) : (<div className="grid gap-6 lg:grid-cols-[1fr_20rem]">
          <div className="space-y-6">
            <Card>
              <dl className="grid grid-cols-2 gap-x-6 gap-y-4 text-sm sm:grid-cols-3">
                <div><dt className="text-xs font-semibold text-black/50">Requested by</dt><dd className="mt-1 text-sm font-semibold">{expense.requested_by}</dd></div>
                <div><dt className="text-xs font-semibold text-black/50">Branch</dt><dd className="mt-1 text-sm font-semibold">{expense.branch || "Not set"}</dd></div>
                <div>
                  <dt className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">Expense number</dt>
                  <dd className="mt-1 font-mono text-sm font-bold text-[var(--color-ink)]">{expense.expense_number}</dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">Department</dt>
                  <dd className="mt-1 text-sm font-semibold text-[var(--color-ink)]">{expense.department}</dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">Date</dt>
                  <dd className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                    {expense.due_date ?? "—"}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">Currency</dt>
                  <dd className="mt-1 text-sm font-semibold text-[var(--color-ink)]">{expense.currency}</dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">Total</dt>
                  <dd className="mt-1 font-mono text-sm font-bold tabular-nums text-[var(--color-ink)]">
                    {formatMoney(expense.currency, expense.total)}
                  </dd>
                </div>
                <div>
                  <dt className="font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">Created</dt>
                  <dd className="mt-1 text-sm font-semibold text-[var(--color-ink)]">
                    {new Date(expense.created_at).toLocaleDateString()}
                  </dd>
                </div>

              </dl>

              

              <h2 className="mb-3 mt-7 font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">
                Line items
              </h2>
              <div className="overflow-x-auto rounded-lg border border-[var(--color-line)]">
                <table className="min-w-[540px] w-full text-sm">
                  <thead>
                    <tr className="bg-[var(--color-linen)] text-left font-mono text-[11px] font-bold uppercase tracking-normal text-black/45">
                      <th className="px-3 py-2.5">Particular</th>
                      <th className="px-3 py-2.5 text-right">Quantity</th>
                      <th className="px-3 py-2.5 text-right">Unit Cost</th>
                      <th className="px-3 py-2.5 text-right">Total Cost</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--color-line)] bg-white">
                    {expense.items.map((item) => (<tr key={item.id}>
                        <td className="px-3 py-2.5 font-medium text-[var(--color-ink)]">{item.description}</td>
                        <td className="px-3 py-2.5 text-right font-mono tabular-nums text-black/70">
                          {item.quantity}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono tabular-nums text-black/70">
                          {formatMoney(expense.currency, item.unit_price)}
                        </td>
                        <td className="px-3 py-2.5 text-right font-mono font-semibold tabular-nums text-[var(--color-ink)]">
                          {formatMoney(expense.currency, item.line_total)}
                        </td>
                      </tr>))}
                  </tbody>
                  <tfoot>
                    <tr className="border-t-2 border-[var(--color-ink)] bg-[var(--color-linen)]">
                      <td colSpan={3} className="px-3 py-2.5 text-right text-xs font-bold uppercase tracking-normal text-black/60">
                        Overall Cost
                      </td>
                      <td className="px-3 py-2.5 text-right font-mono text-sm font-extrabold tabular-nums text-[var(--color-ink)]">
                        {formatMoney(expense.currency, expense.total)}
                      </td>
                    </tr>
                  </tfoot>
                </table>
              </div>
            </Card>

            <ExpenseEvidence expenseId={expense.id} editable={isEditable}/>
            <CommentThread expense={expense}/>
          </div>

          <Card className="h-fit border-[var(--color-ink)]/10">
            <h2 className="mb-4 font-mono text-[11px] font-bold uppercase tracking-normal text-black/40">
              Status timeline
            </h2>
            <StatusTimeline history={historyQuery.data ?? []} expense={expense}/>
          </Card>
        </div>)}
    </div>);
}
