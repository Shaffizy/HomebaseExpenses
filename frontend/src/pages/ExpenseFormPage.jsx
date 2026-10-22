import { useMutation } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import toast from "../lib/notifications";
import { ExpenseForm } from "../components/ExpenseForm";
import { ErrorState, PageHeader } from "../components/ui";
import { api, createExpense, errorMessage, submitExpense, updateExpense } from "../lib/api";
import { useAuth } from "../auth/AuthContext";
export function ExpenseFormPage() {
    const navigate = useNavigate();
    const { user } = useAuth();
    const draft = useRef(null);
    const uploaded = useRef(new Map());
    const [savedDraft, setSavedDraft] = useState(null);
    const saveMutation = useMutation({
        mutationFn: async ({ payload, evidence, submit }) => {
            const expense = draft.current === null ? await createExpense(payload) : await updateExpense(draft.current, payload);
            draft.current = expense.id;
            setSavedDraft(expense.id);
            // Keep the same draft and completed uploads when retrying a partial failure.
            for (const [id, documentId] of uploaded.current) {
                if (!evidence.some((document) => document.id === id)) {
                    await api.delete(`/expenses/${expense.id}/evidence/${documentId}/`);
                    uploaded.current.delete(id);
                }
            }
            for (const document of evidence) {
                if (uploaded.current.has(document.id))
                    continue;
                const data = new FormData();
                data.append("category", document.category);
                data.append("label", document.label);
                data.append("file", document.file);
                const response = await api.post(`/expenses/${expense.id}/evidence/`, data);
                uploaded.current.set(document.id, response.data.id);
            }
            return submit ? await submitExpense(expense.id) : expense;
        },
        onSuccess: (expense, variables) => {
            toast.success(variables.submit ? "Expense submitted with invoice attachments" : "Draft saved with invoice attachments");
            navigate(`/expenses/${expense.id}`);
        },
        onError: (err) => toast.error(`${errorMessage(err)}${draft.current ? ". Your draft is saved; retry to finish." : ""}`),
    });
    if (user?.role !== "REQUESTER") {
        return <ErrorState message="Only requesters can create expenses."/>;
    }
    return (<div className="max-w-3xl">
      <PageHeader title="New expense" subtitle="Drafts can be edited until submitted."/>
      {saveMutation.isError && savedDraft && <p role="alert" className="mb-4 text-sm">This expense has not been sent. Retry below or <Link className="underline" to={`/expenses/${savedDraft}`}>open the saved draft</Link>.</p>}
      <ExpenseForm saving={saveMutation.isPending} onSave={(payload, evidence) => saveMutation.mutate({ payload, evidence, submit: false })} onSubmitAndSend={(payload, evidence) => saveMutation.mutate({ payload, evidence, submit: true })}/>
    </div>);
}
