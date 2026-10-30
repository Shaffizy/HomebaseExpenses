import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import toast from "../lib/notifications";
import { useAuth } from "../auth/AuthContext";
import { errorMessage, listComments, postComment } from "../lib/api";
import { Card, Spinner } from "./ui";
import { useQuery } from "@tanstack/react-query";
export function canComment(user, expense) {
    if (!user)
        return false;
    return (["REQUESTER", "REVIEWER"].includes(user.role) && user.id === expense.created_by && expense.status === "RETURNED") ||
        (user.role === "REVIEWER" && expense.created_by !== user.id && expense.assigned_reviewer === user.id && expense.status === "IN_REVIEW") ||
        (user.role === "APPROVER" && expense.status === "SUBMITTED");
}
export function CommentThread({ expense }) {
    const { user } = useAuth();
    const queryClient = useQueryClient();
    const [text, setText] = useState("");
    const query = useQuery({
        queryKey: ["expense-comments", expense.id],
        queryFn: () => listComments(expense.id),
    });
    const mutation = useMutation({
        mutationFn: () => postComment(expense.id, text.trim()),
        onSuccess: () => {
            toast.success("Comment posted");
            setText("");
            queryClient.invalidateQueries({ queryKey: ["expense-comments", expense.id] });
            queryClient.invalidateQueries({ queryKey: ["expense-action-comment", expense.id] });
        },
        onError: (err) => toast.error(errorMessage(err)),
    });
    const allowed = canComment(user, expense);
    const handlePost = (event) => {
        event.preventDefault();
        if (!text.trim())
            return;
        mutation.mutate();
    };
    return (<Card>
      <h2 className="font-display text-[15px] font-bold tracking-normal text-[var(--color-ink)]">
        Comments
      </h2>

      {query.isLoading ? (<div className="flex justify-center py-8">
          <Spinner />
        </div>) : query.isError ? (<p className="mt-4 text-sm font-medium text-[var(--color-wine)]">{errorMessage(query.error)}</p>) : query.data && query.data.length === 0 ? (<p className="mt-4 rounded-lg border border-dashed border-[var(--color-line)] bg-[var(--color-paper)]/60 px-4 py-6 text-center text-sm text-black/45">
          No comments yet.
        </p>) : (<ul className="mt-4 space-y-3">
          {query.data?.map((comment) => (<li key={comment.id} className="rounded-lg border border-[var(--color-line)] bg-[var(--color-paper)]/70 px-4 py-3">
              <div className="flex items-baseline justify-between gap-3">
                <span className="text-sm font-bold text-[var(--color-ink)]">{comment.author_name}</span>
                <span className="font-mono text-[11px] text-black/40">
                  {new Date(comment.created_at).toLocaleString()}
                </span>
              </div>
              <p className="mt-1 whitespace-pre-wrap text-sm leading-6 text-black/70">{comment.text}</p>
            </li>))}
        </ul>)}

      <form onSubmit={handlePost} className="mt-5">
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3} disabled={!allowed || mutation.isPending} placeholder={allowed
            ? "Write a comment…"
            : ["REQUESTER", "REVIEWER"].includes(user?.role)
                ? "You can reply after the expense is returned to you."
                : "Comments are unavailable at this stage."} className="w-full rounded-lg border border-[var(--color-line)] bg-white px-3.5 py-2.5 text-sm placeholder:text-black/30 focus:border-[var(--color-rust)] focus:outline-none focus:ring-2 focus:ring-[var(--color-rust)]/15 disabled:bg-[var(--color-linen)] disabled:text-black/30"/>
        <div className="mt-3 flex justify-end">
          <button type="submit" disabled={!allowed || !text.trim() || mutation.isPending} className="rounded-full bg-[var(--color-ink)] px-5 py-2 text-sm font-bold text-white hover:bg-[var(--color-ink-soft)] disabled:opacity-40">
            {mutation.isPending ? "Posting…" : "Post comment"}
          </button>
        </div>
      </form>
    </Card>);
}
