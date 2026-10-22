import { zodResolver } from "@hookform/resolvers/zod";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { useQuery } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { z } from "zod";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage } from "../lib/api";
import { StyledSelect } from "./StyledSelect";
import { EvidenceInput } from "./EvidenceInput";
import { lineCostCents, formatCost, overallCostCents } from "../lib/expenseCosts";

const decimal = z.string().regex(/^\d{1,12}(\.\d{1,2})?$/, "Enter a nonnegative number with up to two decimal places");
const schema = z.object({
  title: z.string().trim().min(1, "Enter an expense name").max(255, "Use no more than 255 characters"),
  department: z.string().min(1, "Select a department"),
  branch: z.string().min(1, "Select a branch"),
  due_date: z.string().optional(),
  items: z.array(z.object({ description: z.string().trim().min(1, "Enter a particular"), quantity: decimal, unit_price: decimal })).min(1, "Add at least one item"),
});
const inputClass = "w-full rounded-lg border border-[var(--color-line)] bg-white px-3 py-2.5 text-sm outline-none focus:border-[var(--color-rust)] focus:ring-2 focus:ring-red-100";
function FieldError({ message }) { return message ? <p role="alert" className="mt-1 text-xs text-red-700">{message}</p> : null; }

export function ExpenseForm({ expense, onSave, onSubmitAndSend, saving }) {
  const { user } = useAuth();
  const [evidence, setEvidence] = useState([]);
  const [pendingEvidence, setPendingEvidence] = useState(false);
  const options = useQuery({ queryKey: ["expense-options"], queryFn: async () => (await api.get("/expenses/options/")).data });
  const { register, control, handleSubmit, watch, setValue, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
    defaultValues: {
      title: expense?.title ?? expense?.category_name ?? "",
      department: expense?.department ?? "",
      branch: expense?.branch ?? "",
      due_date: expense ? expense.due_date ?? "" : new Intl.DateTimeFormat("en-CA", { timeZone: "Africa/Lagos", year: "numeric", month: "2-digit", day: "2-digit" }).format(new Date()),
      items: expense?.items.map((item) => ({ description: item.description, quantity: item.quantity, unit_price: item.unit_price })) ?? [{ description: "", quantity: "1", unit_price: "0" }],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const values = watch();
  const blocked = saving || pendingEvidence || options.isLoading || options.isError;
  const payload = (values) => ({ title: values.title.trim(), department: values.department, branch: values.branch, due_date: values.due_date || null, currency: "NGN", items: values.items });
  const send = (values, submit) => { if (!blocked) (submit ? onSubmitAndSend : onSave)(payload(values), evidence); };
  return <form onSubmit={handleSubmit((values) => send(values, false))} className="space-y-6">
    <section className="space-y-4">
      <h2 className="text-lg font-semibold">Expense details</h2>
      {options.isLoading && <p role="status" className="text-sm">Loading expense options...</p>}
      {options.isError && <div role="alert" className="text-sm text-red-700">{errorMessage(options.error)} <button type="button" onClick={() => options.refetch()} className="underline">Retry</button></div>}
      <fieldset disabled={saving} className="grid gap-4 sm:grid-cols-2">
        <div><label className="mb-2 block text-sm font-semibold">Requested by</label><input aria-label="Requested by" readOnly value={expense?.requested_by ?? user?.name ?? ""} className={inputClass + " bg-gray-50"} /></div>
        <div><label htmlFor="expense-title" className="mb-2 block text-sm font-semibold">Expense name</label><input id="expense-title" maxLength={255} {...register("title")} aria-invalid={Boolean(errors.title)} aria-describedby={errors.title ? "expense-title-error" : undefined} className={inputClass} />{errors.title && <p id="expense-title-error" role="alert" className="mt-1 text-xs text-red-700">{errors.title.message}</p>}</div>
        <div><label className="mb-2 block text-sm font-semibold">Department</label><StyledSelect label="Department" value={values.department} onChange={(value) => setValue("department", value, { shouldValidate: true })} options={[{ value: "", label: "Select department" }, ...(options.data?.departments ?? [])]} disabled={saving || options.isLoading} /><FieldError message={errors.department?.message} /></div>
        <div><label className="mb-2 block text-sm font-semibold">Branch</label><StyledSelect label="Branch" value={values.branch} onChange={(value) => setValue("branch", value, { shouldValidate: true })} options={[{ value: "", label: "Select branch" }, ...(options.data?.branches ?? [])]} disabled={saving || options.isLoading} /><FieldError message={errors.branch?.message} /></div>
        <div><label htmlFor="expense-date" className="mb-2 block text-sm font-semibold">Date</label><input id="expense-date" type="date" {...register("due_date")} className={inputClass} /><FieldError message={errors.due_date?.message} /></div>
      </fieldset>
    </section>
    <section className="border-t border-[var(--color-line)] pt-5">
      <div className="mb-4 flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Items</h2><button type="button" disabled={saving} onClick={() => append({ description: "", quantity: "1", unit_price: "0" })} className="inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm font-semibold"><Plus size={16} />Add item</button></div>
      <FieldError message={errors.items?.message} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[620px] table-fixed text-sm"><colgroup><col className="w-[42%]" /><col className="w-[16%]" /><col className="w-[21%]" /><col className="w-[21%]" /></colgroup>
          <thead><tr className="border-b bg-[var(--color-linen)] text-left"><th className="p-3">Particular</th><th className="p-3">Quantity</th><th className="p-3">Unit Cost (₦)</th><th className="p-3 text-right">Total Cost (₦)</th></tr></thead>
          <tbody>{fields.map((field, index) => <tr key={field.id} className="border-b border-[var(--color-line)] align-top">
            <td className="p-2"><div className="flex items-center gap-2"><input aria-label={`Particular ${index + 1}`} disabled={saving} {...register(`items.${index}.description`)} className={inputClass} /><button type="button" title="Remove item" aria-label={`Remove item ${index + 1}`} disabled={saving || fields.length === 1} onClick={() => remove(index)} className="shrink-0 p-1 text-red-700 disabled:opacity-30"><Trash2 size={16} /></button></div><FieldError message={errors.items?.[index]?.description?.message} /></td>
            <td className="p-2"><input aria-label={`Quantity ${index + 1}`} disabled={saving} inputMode="decimal" {...register(`items.${index}.quantity`)} className={inputClass} /><FieldError message={errors.items?.[index]?.quantity?.message} /></td>
            <td className="p-2"><input aria-label={`Unit cost ${index + 1}`} disabled={saving} inputMode="decimal" {...register(`items.${index}.unit_price`)} className={inputClass} /><FieldError message={errors.items?.[index]?.unit_price?.message} /></td>
            <td className="p-3 text-right font-mono tabular-nums"><output aria-label={`Total cost ${index + 1}`}>{formatCost(lineCostCents(values.items?.[index]))}</output></td>
          </tr>)}</tbody>
        </table>
      </div>
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t-2 border-[var(--color-ink)] py-4"><span className="font-semibold">Overall Cost</span><output aria-label="Overall cost" className="font-mono text-xl font-semibold">₦{formatCost(overallCostCents(values.items))}</output></div>
    </section>
    {!expense && <EvidenceInput documents={evidence} onChange={setEvidence} disabled={saving} onPendingChange={setPendingEvidence} />}
    <div className="flex flex-wrap gap-3"><button type="submit" disabled={blocked} className="rounded-lg border px-5 py-3 text-sm font-semibold disabled:opacity-50">{saving ? "Saving..." : "Save draft"}</button><button type="button" disabled={blocked} onClick={handleSubmit((values) => send(values, true))} className="rounded-lg bg-[var(--color-rust)] px-5 py-3 text-sm font-semibold text-white disabled:opacity-50">Save &amp; submit</button></div>
  </form>;
}
