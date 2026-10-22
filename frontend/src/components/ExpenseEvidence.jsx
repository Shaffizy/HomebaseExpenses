import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Download, Eye, Paperclip, Trash2, X } from "lucide-react";
import toast from "../lib/notifications";
import { api, errorMessage } from "../lib/api";
import { StyledSelect } from "./StyledSelect";
import { EVIDENCE_CATEGORIES as categories } from "../lib/evidence";
export function ExpenseEvidence({ expenseId, editable }) {
    const client = useQueryClient();
    const [category, setCategory] = useState("IDENTIFICATION");
    const [label, setLabel] = useState("");
    const [file, setFile] = useState(null);
    const input = useRef(null);
    const previewDialog = useRef(null);
    const [preview, setPreview] = useState(null);
    useEffect(() => {
        if (preview)
            previewDialog.current?.showModal();
        else
            previewDialog.current?.close();
        return () => { if (preview)
            URL.revokeObjectURL(preview.url); };
    }, [preview]);
    const key = ["expense-evidence", expenseId];
    const url = `/expenses/${expenseId}/evidence/`;
    const query = useQuery({ queryKey: key, queryFn: async () => (await api.get(url)).data });
    const upload = useMutation({
        mutationFn: async () => {
            if (!file)
                throw new Error("Select a file.");
            const data = new FormData();
            data.append("category", category);
            data.append("label", label);
            data.append("file", file);
            await api.post(url, data);
        },
        onSuccess: () => { setFile(null); setLabel(""); if (input.current)
            input.current.value = ""; client.invalidateQueries({ queryKey: key }); toast.success("Invoice attached"); },
        onError: (error) => toast.error(errorMessage(error)),
    });
    const remove = useMutation({ mutationFn: (id) => api.delete(`${url}${id}/`), onSuccess: () => { client.invalidateQueries({ queryKey: key }); toast.success("Invoice removed"); }, onError: (error) => toast.error(errorMessage(error)) });
    const download = useMutation({
        mutationFn: async (document) => {
            const response = await api.get(`${url}${document.id}/`, { responseType: "blob" });
            const objectUrl = URL.createObjectURL(response.data);
            const link = window.document.createElement("a");
            link.href = objectUrl;
            link.download = document.original_name;
            link.click();
            window.setTimeout(() => URL.revokeObjectURL(objectUrl), 1000);
        }, onError: (error) => toast.error(errorMessage(error)),
    });
    const view = useMutation({
        mutationFn: async (document) => {
            const response = await api.get(`${url}${document.id}/`, { responseType: "blob" });
            const pdf = /\.pdf$/i.test(document.original_name);
            const type = pdf ? "application/pdf" : /\.png$/i.test(document.original_name) ? "image/png" : "image/jpeg";
            return { url: URL.createObjectURL(new Blob([response.data], { type })), document, pdf };
        }, onSuccess: setPreview, onError: (error) => toast.error(errorMessage(error)),
    });
    return <section className="border-t border-[var(--color-line)] pt-5">
    <h2 className="mb-3 text-lg font-semibold">Invoice</h2>
    {query.isLoading && <p role="status">Loading invoices...</p>}
    {query.isError && <div role="alert">{errorMessage(query.error)} <button type="button" onClick={() => query.refetch()}>Retry</button></div>}
    {query.data?.length === 0 && <p className="text-sm text-black/50">No invoice attached.</p>}
    <ul className="divide-y divide-[var(--color-line)]">{query.data?.map((document) => <li key={document.id} className="flex items-center gap-3 py-3">
      <div className="min-w-0 flex-1"><p className="break-words text-sm font-semibold">{document.label || categories.find((c) => c.value === document.category)?.label}</p><p className="break-all text-xs text-black/50">{document.original_name} ({Math.ceil(document.size / 1024)} KB)</p></div>
      <button type="button" aria-label={`View ${document.original_name}`} title="View invoice" disabled={view.isPending} onClick={() => view.mutate(document)} className="p-2"><Eye size={18}/></button>
      <button type="button" aria-label={`Download ${document.original_name}`} title="Download" disabled={download.isPending} onClick={() => download.mutate(document)} className="p-2"><Download size={18}/></button>
      {editable && <button type="button" aria-label={`Remove ${document.original_name}`} title="Remove" disabled={remove.isPending} onClick={() => { if (window.confirm("Remove this invoice?"))
            remove.mutate(document.id); }} className="p-2 text-red-700"><Trash2 size={18}/></button>}
    </li>)}</ul>
    <dialog ref={previewDialog} aria-label="Invoice preview" onCancel={() => setPreview(null)} className="fixed inset-0 m-auto w-[calc(100%-2rem)] max-w-4xl max-h-[90dvh] overflow-y-auto rounded-lg bg-white p-4 backdrop:bg-black/40">
      {preview && <><div className="mb-3 flex items-center justify-between gap-3"><h2 className="min-w-0 break-all font-semibold">{preview.document.original_name}</h2><button type="button" title="Close preview" aria-label="Close preview" onClick={() => setPreview(null)} className="p-2"><X size={18}/></button></div>
        {preview.pdf ? <object aria-label={preview.document.original_name} data={preview.url} type="application/pdf" className="h-[65dvh] w-full"><p className="text-sm">PDF preview is unavailable in this browser. Download the file below.</p></object> : <img alt={preview.document.label || preview.document.original_name} src={preview.url} className="max-h-[65dvh] w-full object-contain"/>}
        <button type="button" onClick={() => download.mutate(preview.document)} disabled={download.isPending} className="mt-3 inline-flex items-center gap-2 rounded-lg border px-3 py-2 text-sm"><Download size={16}/>Download</button>
      </>}
    </dialog>
    {editable && <div className="mt-4 space-y-3">
      <StyledSelect label="Invoice type" value={category} onChange={setCategory} options={categories}/>
      {category === "OTHER" && <input aria-label="Document name" placeholder="Document name" value={label} maxLength={150} onChange={(event) => setLabel(event.target.value)} className="w-full rounded-lg border border-[var(--color-line)] p-2 text-sm"/>}
      <input ref={input} aria-label="Invoice file" type="file" accept=".pdf,.png,.jpg,.jpeg" disabled={upload.isPending} onChange={(event) => { const selected = event.target.files?.[0] ?? null; if (selected && selected.size > 10 * 1024 * 1024) {
            toast.error("Maximum file size is 10 MB");
            event.target.value = "";
            setFile(null);
        }
        else
            setFile(selected); }} className="block w-full min-w-0 text-sm"/>
      <button type="button" disabled={!file || upload.isPending || (category === "OTHER" && !label.trim())} onClick={() => upload.mutate()} className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-ink)] px-3 py-2 text-sm font-semibold text-white disabled:opacity-50"><Paperclip size={16}/>{upload.isPending ? "Attaching..." : "Attach invoice"}</button>
    </div>}
  </section>;
}
