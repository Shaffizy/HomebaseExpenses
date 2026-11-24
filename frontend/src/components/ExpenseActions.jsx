import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { createPortal } from "react-dom";
import toast from "../lib/notifications";
import { approveExpense, closeExpense, errorMessage, rejectExpense, returnExpense, api, } from "../lib/api";
import { calculateWhtBreakdown, DEFAULT_WHT_CLASSIFICATIONS } from "../lib/expenseCosts";
import { useAuth } from "../auth/AuthContext";
import { Modal } from "./ui";
const ACTIONS = {
    review: { key: "review", label: "Forward to FinCon", confirmTitle: "Complete departmental review", style: "bg-[var(--color-moss)] text-white", needsComment: false },
    finconReview: { key: "finconReview", label: "Calculate WHT & Forward", confirmTitle: "FinCon Withholding Tax (WHT) Review", style: "bg-[var(--color-moss)] text-white", needsComment: false },
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
    review: "Departmental review completed and forwarded to FinCon",
    finconReview: "Withholding tax calculated and forwarded for approval",
    approve: "Expense approved",
    return: "Expense returned to the requester",
    reject: "Expense rejected",
};
export function availableActions(role, status, isOwner = false) {
    if (role === "REVIEWER" && status === "IN_REVIEW") {
        return isOwner ? [] : [ACTIONS.review, ACTIONS.reject, ACTIONS.return];
    }
    if (role === "REVIEWER" && status === "IN_FINCON_REVIEW") {
        return isOwner ? [ACTIONS.finconReview] : [ACTIONS.finconReview, ACTIONS.reject, ACTIONS.return];
    }
    if (role === "APPROVER" && status === "SUBMITTED")
        return isOwner ? [] : [ACTIONS.approve, ACTIONS.reject, ACTIONS.return];
    return [];
}
export function ExpenseActions({ expense, role }) {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const [pendingAction, setPendingAction] = useState(null);
    const [comment, setComment] = useState("");
    const [whtClassification, setWhtClassification] = useState(expense.wht_classification || "");
    const [checkingComment, setCheckingComment] = useState(false);
    const options = useQuery({
        queryKey: ["expense-options"],
        queryFn: async () => (await api.get("/expenses/options/")).data,
        enabled: expense.status === "IN_FINCON_REVIEW" && role === "REVIEWER",
    });
    const whtClassifications = options.data?.wht_classifications?.length
        ? options.data.wht_classifications
        : DEFAULT_WHT_CLASSIFICATIONS;
    const whtPreview = calculateWhtBreakdown(expense.total, whtClassification, whtClassifications);
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
        mutationFn: ({ action, comment, wht_classification }) => {
            switch (action.key) {
                case "review":
                    return api.post(`/expenses/${expense.id}/review/`).then(({ data }) => data);
                case "finconReview":
                    return api.post(`/expenses/${expense.id}/review/`, { wht_classification }).then(({ data }) => data);
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
    const isOwner = expense.created_by === user?.id;
    const canActAsReviewer = role !== "REVIEWER" || (
        expense.assigned_reviewer === user?.id && (
            (expense.status === "IN_REVIEW" && user?.department === expense.department) ||
            (expense.status === "IN_FINCON_REVIEW" && user?.department === "FinCon")
        )
    );
    const actions = canActAsReviewer ? availableActions(role, expense.status, isOwner) : [];
    const canClose = ["REQUESTER", "REVIEWER"].includes(role) &&
        isOwner &&
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
        else if (action.key === "approve" || action.key === "finconReview") {
            setComment("");
            if (action.key === "finconReview" && !whtClassification) {
                setWhtClassification(expense.wht_classification || "");
            }
            setPendingAction(action);
        }
        else {
            mutation.mutate({ action, comment: "" });
        }
    };
    const confirm = () => {
        if (!pendingAction)
            return;
        if (pendingAction.needsComment && !comment.trim())
            return;
        if (pendingAction.key === "finconReview" && !whtClassification)
            return;
        mutation.mutate({
            action: pendingAction,
            comment: comment.trim(),
            wht_classification: whtClassification,
        });
    };
    return (<>
      {canClose && (<button onClick={() => runClose.mutate()} disabled={runClose.isPending} className="rounded-full border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-bold text-[var(--color-ink)] hover:bg-[var(--color-linen)] disabled:opacity-60">
          Close
        </button>)}

      {actions.map((action) => (<button type="button" key={action.key} onClick={() => handleClick(action)} disabled={mutation.isPending || checkingComment} className={`rounded-full px-4 py-2 text-sm font-bold shadow-sm disabled:opacity-60 ${action.style}`}>
          {action.label}
        </button>))}

      {createPortal(<Modal open={pendingAction !== null} title={pendingAction?.confirmTitle ?? ""} onClose={() => { if (!mutation.isPending) setPendingAction(null); }}>
        {pendingAction?.key === "approve" && <p className="text-sm">Approve expense <strong>{expense.expense_number}</strong> as <strong>{user?.name}</strong>?</p>}
        {pendingAction?.key === "finconReview" && (<div className="space-y-4">
          <p className="text-sm text-black/70">
            Select the Nigeria Withholding Tax (WHT) classification for <strong>{expense.expense_number}</strong> ({expense.category_name}).
          </p>
          <div>
            <label htmlFor="wht-classification" className="block text-xs font-bold uppercase tracking-normal text-black/55">
              WHT Classification &amp; Rate <span className="text-[var(--color-wine)]">*</span>
            </label>
            <select
              id="wht-classification"
              value={whtClassification}
              onChange={(e) => setWhtClassification(e.target.value)}
              className="mt-1.5 w-full rounded-lg border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm font-medium text-[var(--color-ink)] focus:border-[var(--color-rust)] focus:outline-none focus:ring-2 focus:ring-[var(--color-rust)]/15"
            >
              <option value="">Select WHT classification...</option>
              {whtClassifications.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
          <div className="rounded-lg border border-[var(--color-line)] bg-[var(--color-linen)]/60 p-3.5 text-sm space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-black/65">Gross Total (Overall Cost)</span>
              <span className="font-mono font-semibold tabular-nums">₦{whtPreview.grossFormatted}</span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-black/65">Withholding Tax ({whtPreview.rate}%)</span>
              <span className="font-mono font-semibold tabular-nums text-[var(--color-wine)]">-₦{whtPreview.whtFormatted}</span>
            </div>
            <div className="flex items-center justify-between border-t border-[var(--color-line)] pt-2 font-bold text-[var(--color-ink)]">
              <span>Net Payable</span>
              <span className="font-mono text-base tabular-nums">₦{whtPreview.netFormatted}</span>
            </div>
          </div>
        </div>)}
        {pendingAction?.needsComment && <><label htmlFor="action-comment" className="block text-xs font-bold uppercase tracking-normal text-black/55">
          Comment <span className="text-[var(--color-wine)]">*</span>
        </label>
        <textarea id="action-comment" value={comment} onChange={(e) => setComment(e.target.value)} rows={4} autoFocus placeholder="Explain why…" className="mt-1.5 w-full rounded-lg border border-[var(--color-line)] bg-[var(--color-paper)] px-3.5 py-2.5 text-sm focus:border-[var(--color-rust)] focus:outline-none focus:ring-2 focus:ring-[var(--color-rust)]/15"/>
        </>}
        <div className="mt-4 flex justify-end gap-2">
          <button type="button" disabled={mutation.isPending} onClick={() => setPendingAction(null)} className="rounded-full border border-[var(--color-line)] bg-white px-5 py-2.5 text-sm font-bold text-[var(--color-ink)] hover:bg-[var(--color-linen)]">
            Cancel
          </button>
          <button type="button" onClick={confirm} disabled={(pendingAction?.needsComment && !comment.trim()) || (pendingAction?.key === "finconReview" && !whtClassification) || mutation.isPending} className={`rounded-full px-5 py-2.5 text-sm font-bold shadow-sm disabled:opacity-50 ${pendingAction?.style ?? ""}`}>
            {mutation.isPending ? "Working…" : pendingAction?.key === "approve" ? "Confirm approval" : pendingAction?.key === "finconReview" ? "Confirm WHT & Forward" : pendingAction?.label}
          </button>
        </div>
      </Modal>, document.body)}
    </>);
}
