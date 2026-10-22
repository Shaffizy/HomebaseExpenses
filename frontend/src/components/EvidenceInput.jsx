import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Plus, Trash2, Upload, X } from "lucide-react";
import toast from "../lib/notifications";
import { EVIDENCE_CATEGORIES } from "../lib/evidence";
import { StyledSelect } from "./StyledSelect";
export function EvidenceInput({ documents, onChange, disabled, onPendingChange }) {
    const [open, setOpen] = useState(false);
    const [category, setCategory] = useState("IDENTIFICATION");
    const [label, setLabel] = useState("");
    const [files, setFiles] = useState([]);
    const dialog = useRef(null);
    const input = useRef(null);
    const titleId = useId();
    useEffect(() => {
        if (open && !dialog.current?.open)
            dialog.current?.showModal();
        if (!open && dialog.current?.open)
            dialog.current.close();
    }, [open]);
    const close = () => {
        setOpen(false);
        setFiles([]);
        setLabel("");
        setCategory("IDENTIFICATION");
        if (input.current)
            input.current.value = "";
        onPendingChange(false);
    };
    const selectFiles = (selected) => {
        if (selected.some((file) => !file.size || file.size > 10 * 1024 * 1024 || !/\.(pdf|png|jpe?g)$/i.test(file.name))) {
            toast.error("Select nonempty PDF, PNG, or JPEG files up to 10 MB each");
            return;
        }
        setFiles(selected);
        onPendingChange(selected.length > 0);
    };
    const attach = () => {
        if (disabled || !files.length || (category === "OTHER" && !label.trim()))
            return;
        onChange([...documents, ...files.map((file) => ({ id: crypto.randomUUID(), category, label: label.trim(), file }))]);
        close();
    };
    return <section className="space-y-3 border-t border-[var(--color-line)] pt-5">
    <div className="flex items-center justify-between gap-3"><h2 className="text-lg font-semibold">Invoice</h2>
      <button type="button" disabled={disabled} onClick={() => setOpen(true)} className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-line)] px-3 py-2 text-sm font-semibold disabled:opacity-50"><Plus size={16}/>Add invoice</button>
    </div>
    <ul className="divide-y divide-[var(--color-line)]">{documents.map((document) => <li key={document.id} className="flex items-center gap-3 py-2">
      <div className="min-w-0 flex-1"><p className="break-words text-sm font-semibold">{document.label || EVIDENCE_CATEGORIES.find((c) => c.value === document.category)?.label}</p><p className="break-all text-xs text-black/50">{document.file.name}</p></div>
      <button type="button" disabled={disabled} aria-label={`Remove ${document.file.name}`} title="Remove" onClick={() => onChange(documents.filter((item) => item.id !== document.id))} className="p-2 text-red-700"><Trash2 size={18}/></button>
    </li>)}</ul>
    {createPortal(<dialog ref={dialog} aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); close(); }} className="fixed inset-0 m-auto max-h-[85dvh] w-[calc(100%-2rem)] max-w-lg overflow-y-auto rounded-lg border border-[var(--color-line)] bg-white p-6 text-[var(--color-ink)] shadow-xl backdrop:bg-black/40">
      <div className="mb-5 flex items-center justify-between gap-3"><h2 id={titleId} className="text-lg font-semibold">Attach invoice</h2><button type="button" onClick={close} aria-label="Close attachment dialog" title="Close" className="p-2"><X size={18}/></button></div>
      <div className="space-y-4">
        <StyledSelect label="Invoice type" value={category} onChange={setCategory} options={EVIDENCE_CATEGORIES} portalContainer={dialog.current}/>
        <input aria-label="Invoice title" placeholder={category === "OTHER" ? "Document title (required)" : "Document title (optional)"} maxLength={150} value={label} onChange={(event) => setLabel(event.target.value)} className="w-full rounded-lg border border-[var(--color-line)] p-2 text-sm"/>
        <div onDragOver={(event) => event.preventDefault()} onDrop={(event) => { event.preventDefault(); selectFiles(Array.from(event.dataTransfer.files)); }} className="rounded-lg border-2 border-dashed border-[var(--color-line)] p-6 text-center">
          <Upload size={28} className="mx-auto mb-3 text-black/50"/>
          <button type="button" onClick={() => input.current?.click()} className="rounded-lg border border-[var(--color-line)] px-4 py-2 text-sm font-semibold">Choose files</button>
          <input ref={input} type="file" aria-label="Invoice files" accept=".pdf,.png,.jpg,.jpeg" multiple onChange={(event) => selectFiles(Array.from(event.target.files ?? []))} className="sr-only"/>
        </div>
        <ul className="space-y-1">{files.map((file, index) => <li key={`${file.name}-${index}`} className="break-all text-sm">{file.name} <span className="text-black/50">({Math.ceil(file.size / 1024)} KB)</span></li>)}</ul>
        <div className="flex justify-end gap-2"><button type="button" onClick={close} className="rounded-lg border border-[var(--color-line)] px-4 py-2 text-sm font-semibold">Cancel</button><button type="button" disabled={disabled || !files.length || (category === "OTHER" && !label.trim())} onClick={attach} className="rounded-lg bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Attach</button></div>
      </div>
    </dialog>, window.document.body)}
  </section>;
}
