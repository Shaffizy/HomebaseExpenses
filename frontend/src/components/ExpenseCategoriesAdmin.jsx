import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, Pencil, X, Search, ChevronLeft, ChevronRight } from "lucide-react";
import toast from "../lib/notifications";
import { api, errorMessage } from "../lib/api";
import { categoryPage } from "../lib/categoryList";
import { StyledSelect } from "./StyledSelect";
import { PageHeader } from "./ui";

export function ExpenseCategoriesAdmin() {
  const cache = useQueryClient();
  const [form, setForm] = useState(null);
  const [error, setError] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const dialog = useRef(null);
  const query = useQuery({ queryKey: ["expense-categories", "admin"], queryFn: async () => (await api.get("/expense-categories/", { params: { include_inactive: "1" } })).data });
  const result = useMemo(() => categoryPage(query.data ?? [], { search, status, page, pageSize }), [query.data, search, status, page, pageSize]);
  useEffect(() => {
    if (form && !dialog.current.open) dialog.current.showModal();
    if (!form && dialog.current.open) dialog.current.close();
  }, [form]);
  const close = () => { if (!save.isPending) { setForm(null); setError(""); } };
  const clearFilters = () => { setSearch(""); setStatus("all"); setPage(1); };
  const save = useMutation({
    mutationFn: () => form.id ? api.patch(`/expense-categories/${form.id}/?include_inactive=1`, { name: form.name.trim(), is_active: form.is_active }) : api.post("/expense-categories/", { name: form.name.trim(), is_active: form.is_active }),
    onSuccess: () => { cache.invalidateQueries({ queryKey: ["expense-categories"] }); setForm(null); setError(""); toast.success("Category saved"); },
    onError: (error) => { const message = errorMessage(error); setError(message); toast.error(message); },
  });
  return <section>
    <PageHeader title="Categories" actions={<button type="button" onClick={() => { setError(""); setForm({ name: "", is_active: true }); }} className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-rust)] px-4 py-2 text-sm font-semibold text-white hover:bg-[var(--color-rust-hover)]"><Plus size={16}/>Add category</button>}/>
    <div className="mb-4 flex flex-wrap items-center gap-3">
      <div className="relative min-w-0 flex-1 basis-52">
        <Search size={17} aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-black/40" />
        <input aria-label="Search categories" value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search categories" className="min-h-11 w-full rounded-lg border border-[var(--color-line)] bg-white py-2 pl-10 pr-3 text-sm outline-none focus:border-[var(--color-rust)]" />
      </div>
      <StyledSelect className="w-40" label="Category status" value={status} onChange={(value) => { setStatus(value); setPage(1); }} options={[{ value: "all", label: "All statuses" }, { value: "active", label: "Active" }, { value: "inactive", label: "Inactive" }]} />
    </div>
    {query.isLoading ? <p role="status" className="py-8 text-sm">Loading categories...</p> : query.isError ? <p role="alert" className="py-4 text-sm text-red-700">{errorMessage(query.error)} <button type="button" onClick={() => query.refetch()} className="underline">Retry</button></p> : result.count === 0 ? <div className="border-y border-[var(--color-line)] py-8 text-sm text-black/50">
      <p>{query.data?.length ? "No matching categories." : "No expense categories."}</p>
      {(search || status !== "all") && <button type="button" onClick={clearFilters} className="mt-3 font-semibold text-[var(--color-rust)]">Clear filters</button>}
    </div> : <div className="overflow-x-auto">
      <table className="w-full table-fixed text-left text-sm"><colgroup><col className="w-[60%]" /><col className="w-[25%]" /><col className="w-[15%]" /></colgroup>
        <thead><tr className="border-y border-[var(--color-line)] bg-[var(--color-linen)]"><th className="px-3 py-3 font-semibold">Category</th><th className="px-3 py-3 font-semibold">Status</th><th className="px-2 py-3 text-right font-semibold">Edit</th></tr></thead>
        <tbody>{result.rows.map((category) => <tr key={category.id} className="border-b border-[var(--color-line)]">
          <td className="break-words px-3 py-3 font-medium">{category.name}</td>
          <td className="px-3 py-3"><span className={category.is_active ? "text-green-700" : "text-black/50"}>{category.is_active ? "Active" : "Inactive"}</span></td>
          <td className="px-2 py-2 text-right"><button type="button" title="Edit category" aria-label={`Edit ${category.name}`} onClick={() => { setError(""); setForm({ ...category }); }} className="inline-flex h-9 w-9 items-center justify-center rounded-lg hover:bg-gray-100"><Pencil size={17} /></button></td>
        </tr>)}</tbody>
      </table>
    </div>}
    {!query.isLoading && !query.isError && <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
      <p aria-live="polite" className="text-xs text-black/50">{result.start}-{result.end} of {result.count}{search || status !== "all" ? ` matching / ${query.data?.length ?? 0} total` : " categories"}</p>
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-xs text-black/50">Rows</span>
        <StyledSelect className="w-20" label="Categories per page" value={String(pageSize)} onChange={(value) => { setPageSize(Number(value)); setPage(1); }} options={[10, 20, 50].map((size) => ({ value: String(size), label: String(size) }))} />
        <span className="text-xs text-black/50">Page {result.page} of {result.totalPages}</span>
        <button type="button" title="Previous page" aria-label="Previous categories page" disabled={result.page <= 1} onClick={() => setPage(result.page - 1)} className="grid h-9 w-9 place-items-center rounded-lg border disabled:opacity-30"><ChevronLeft size={18} /></button>
        <button type="button" title="Next page" aria-label="Next categories page" disabled={result.page >= result.totalPages} onClick={() => setPage(result.page + 1)} className="grid h-9 w-9 place-items-center rounded-lg border disabled:opacity-30"><ChevronRight size={18} /></button>
      </div>
    </div>}
    <dialog ref={dialog} onCancel={(event) => { event.preventDefault(); close(); }} aria-labelledby="category-dialog-title" className="fixed inset-0 m-auto w-[calc(100%-2rem)] max-w-md rounded-lg bg-white p-6 text-[var(--color-ink)] shadow-xl backdrop:bg-black/40">
      {form && <form onSubmit={(event) => { event.preventDefault(); if (!save.isPending && form.name.trim()) save.mutate(); }} className="space-y-4">
        <div className="flex items-center justify-between"><h2 id="category-dialog-title" className="text-lg font-semibold">{form.id ? "Edit category" : "New category"}</h2><button type="button" disabled={save.isPending} onClick={close} aria-label="Close category dialog" className="p-2"><X size={18} /></button></div>
        <label className="block text-sm font-semibold">Category name<input autoFocus required maxLength={100} value={form.name} disabled={save.isPending} onChange={(event) => setForm({ ...form, name: event.target.value })} className="mt-2 w-full rounded-lg border border-[var(--color-line)] p-3 text-sm" /></label>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} disabled={save.isPending} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />Active</label>
        {error && <p role="alert" className="text-sm text-red-700">{error}</p>}
        <div className="flex justify-end gap-2"><button type="button" disabled={save.isPending} onClick={close} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button type="submit" disabled={save.isPending || !form.name.trim()} className="rounded-lg bg-[var(--color-rust)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{save.isPending ? "Saving..." : "Save category"}</button></div>
      </form>}
    </dialog>
  </section>;
}
