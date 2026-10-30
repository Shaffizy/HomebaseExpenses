import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import toast from "../lib/notifications";
import { approveExpense, closeExpense, errorMessage, rejectExpense, returnExpense, api, } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
import { Modal } from "./ui";
const ACTIONS = {
    review: { key: "review", label: "Forward for approval", confirmTitle: "Complete review", style: "bg-[var(--color-moss)] text-white", needsComment: false },
    approve: {
        key: "approve",
        label: "Approve ✓",
        confirmTitle: "Approve expense",
        style: "bg-[var(--color-moss)] hover:bg-[#16563d] text-white",
        needsComment: false,
    },
    return: {
        key: "return",
        label: "Return",
        confirmTitle: "Return expense",
        style: "bg-[#fef3c7] hover:bg-[#fde68a] text-[#7a3d00] ring-1 ring-inset ring-[#f59e0b]/30",
        needsComment: true,
    },
    reject: {
        key: "reject",
        label: "Reject",
        confirmTitle: "Reject expense",
        style: "bg-[var(--color-wine)] hover:bg-[#7a2530] text-white",
        needsComment: true,
    },
};
const SUCCESS_MESSAGES = {
    review: "Expense reviewed and forwarded for approval",
    approve: "Expense approved",
    return: "Expense returned to the requester",
    reject: "Expense rejected",
};
export function availableActions(role, status) {
    if (role === "REVIEWER" && status === "IN_REVIEW") return [ACTIONS.review, ACTIONS.reject, ACTIONS.return];
    if (role === "APPROVER" && status === "SUBMITTED")
        return [ACTIONS.approve, ACTIONS.reject, ACTIONS.return];
    return [];
}
export function ExpenseActions({ expense, role }) {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const [pendingAction, setPendingAction] = useState(null);
    const [comment, setComment] = useState("");
    const [checkingComment, setCheckingComment] = useState(false);
    const invalidate = () => {
        queryClient.invalidateQueries({ queryKey: ["expenses"] });
        queryClient.invalidateQueries({ queryKey: ["expense", String(expense.id)] });
        queryClient.invalidateQueries({ queryKey: ["expense", expense.id] });
        queryClient.invalidateQueries({ queryKey: ["expense-history", String(expense.id)] });
        queryClient.invalidateQueries({ queryKey: ["expense-history", expense.id] });
        queryClient.invalidateQueries({ queryKey: ["expense-comments", expense.id] });
        queryClient.invalidateQueries({ queryKey: ["expense-action-comment", expense.id] });
    };
    const runClose = useMutation({
        mutationFn: () => closeExpense(expense.id),
        onSuccess: () => {
            toast.success("Expense closed");
            invalidate();
        },
        onError: (err) => toast.error(errorMessage(err)),
    });
    const mutation = useMutation({
        mutationFn: ({ action, comment }) => {
            switch (action.key) {
                case "review":
                    return api.post(`/expenses/${expense.id}/review/`).then(({ data }) => data);
                case "approve":
                    return approveExpense(expense.id);
                case "return":
                    return returnExpense(expense.id, comment);
                case "reject":
                    return rejectExpense(expense.id, comment);
            }
        },
        onSuccess: (_data, { action }) => {
            toast.success(SUCCESS_MESSAGES[action.key]);
            invalidate();
            setPendingAction(null);
            setComment("");
        },
        onError: (err) => toast.error(errorMessage(err)),
    });
    const actions = expense.created_by === user?.id ? [] : availableActions(role, expense.status);
    const canClose = ["REQUESTER", "REVIEWER"].includes(role) &&
        expense.created_by === user?.id &&
        (expense.status === "DRAFT" || expense.status === "RETURNED" || expense.status === "REJECTED");
    if (actions.length === 0 && !canClose)
        return null;
    const handleClick = async (action) => {
        if (action.needsComment) {
            setCheckingComment(true);
            try {
                const existing = await queryClient.fetchQuery({
                    queryKey: ["expense-action-comment", expense.id, expense.status, user?.id],
                    queryFn: async () => (await api.get(`/expenses/${expense.id}/action-comment/`)).data,
                    staleTime: 0,
                });
                if (existing?.text?.trim()) {
                    mutation.mutate({ action, comment: "" });
                    return;
                }
            } catch (err) {
                toast.error(errorMessage(err));
            } finally {
                setCheckingComment(false);
            }
            setComment("");
            setPendingAction(action);
        }
        else {
            mutation.mutate({ action, comment: "" });
        }
    };
    const confirm = () => {
        if (!pendingAction || !comment.trim())
            return;
        mutation.mutate({ action: pendingAction, comment: comment.trim() });
    };
    return (<>
      {canClose && (<button onClick={() => runClose.mutate()} disabled={runClose.isPending} className="rounded-full border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-bold text-[var(--color-ink)] hover:bg-[var(--color-linen)] disabled:opacity-60">
          Close
        </button>)}

      {actions.map((action) => (<button type="button" key={action.key} onClick={() => handleClick(action)} disabled={mutation.isPending || checkingComment} className={`rounded-full px-4 py-2 text-sm font-bold shadow-sm disabled:opacity-60 ${action.style}`}>
          {action.label}
        </button>))}

      {createPortal(<Modal open={pendingAction !== null} title={pendingAction?.confirmTitle ?? ""} onClose={() => { if (!mutation.isPending) setPendingAction(null); }}>
        <label htmlFor="action-comment" className="block text-xs font-bold uppercase tracking-normal text-black/55">
          Comment <span className="text-[var(--color-wine)]">*</span>
        </label>
        <textarea id="action-comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={4} autoFocus placeholder="Explain why…" className="mt-1.5 w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-paper)] px-3.5 py-2.5 text-sm focus:border-[var(--color-rust)] focus:outline-none focus:ring-2 focus:ring-[var(--color-rust)]/15"/>
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" disabled={mutation.isPending} onClick={() => setPendingAction(null)} className="rounded-full border border-[var(--color-line)] bg-white px-5 py-2.5 text-sm font-bold text-[var(--color-ink)] hover:bg-[var(--color-linen)]">
            Cancel
          </button>
          <button type="button" onClick={confirm} disabled={!comment.trim() || mutation.isPending} className={`rounded-full px-5 py-2.5 text-sm font-bold shadow-sm disabled:opacity-50 ${pendingAction?.style ?? ""}`}>
            {mutation.isPending ? "Working…" : pendingAction?.label}
          </button>
        </div>
      </Modal>, document.body)}
    </>);
}
