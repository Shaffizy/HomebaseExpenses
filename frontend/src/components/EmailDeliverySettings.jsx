import { useMutation, useQuery } from "@tanstack/react-query";
import { Mail, RefreshCw, Send } from "lucide-react";
import toast from "../lib/notifications";
import { api, errorMessage } from "../lib/api";
import { ErrorState, Spinner } from "./ui";

const buttonClass = "inline-flex items-center gap-2 rounded-lg border border-[var(--color-line)] bg-white px-4 py-2.5 text-sm font-semibold hover:bg-gray-50 disabled:opacity-50";

export function EmailDeliverySettings() {
  const query = useQuery({ queryKey: ["application-email-delivery"], queryFn: async () => (await api.get("/auth/email-delivery")).data });
  const test = useMutation({
    mutationFn: () => api.post("/auth/email-delivery"),
    onSuccess: ({ data }) => toast.success(data.detail, { duration: 7000 }),
    onError: (error) => toast.error(errorMessage(error), { duration: 7000 }),
  });
  if (query.isPending) return <Spinner />;
  if (query.isError) return <ErrorState message={errorMessage(query.error)} onRetry={query.refetch} />;
  const status = query.data;
  return <section className="max-w-2xl">
    <div className="mb-6 flex items-center gap-3 border-b border-[var(--color-line)] pb-5"><Mail size={22} className="text-[var(--color-rust)]"/><h2 className="text-lg font-semibold">Email notifications</h2></div>
    <dl className="divide-y divide-[var(--color-line)] text-sm">
      <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]"><dt className="font-semibold">Sender status</dt><dd className={status.configured ? "text-green-800" : "text-amber-800"}>{status.configured ? "Configured — test required" : status.mode === "console" ? "Local preview only" : "Setup required"}</dd></div>
      <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]"><dt className="font-semibold">Application sender</dt><dd className="break-all">{status.sender}</dd></div>
      <div className="grid gap-2 py-4 sm:grid-cols-[150px_1fr]"><dt className="font-semibold">Test recipient</dt><dd className="break-all">{status.test_recipient || "No administrator email set"}</dd></div>
    </dl>
    <p role="status" className="my-5 text-sm text-black/65">{status.detail}</p>
    {test.isError && <p role="alert" className="mb-4 text-sm text-red-700">{errorMessage(test.error)}</p>}
    <div className="flex flex-wrap gap-3">
      <button type="button" className={buttonClass} disabled={query.isFetching || test.isPending} onClick={() => { test.reset(); query.refetch(); }}><RefreshCw size={16}/>Refresh status</button>
      <button type="button" className={buttonClass} disabled={!status.configured || !status.test_recipient || test.isPending} onClick={() => test.mutate()}><Send size={16}/>{test.isPending ? "Sending..." : "Send test to my email"}</button>
    </div>
  </section>;
}
