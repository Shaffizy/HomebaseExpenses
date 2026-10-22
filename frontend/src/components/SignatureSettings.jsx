import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Upload, Trash2 } from "lucide-react";
import toast from "../lib/notifications";
import { api, errorMessage } from "../lib/api";
import { ErrorState, Spinner } from "./ui";

export function SignatureSettings() {
    const client = useQueryClient();
    const [file, setFile] = useState(null);
    const [preview, setPreview] = useState("");
    const previewUrl = useRef("");
    const [password, setPassword] = useState("");
    const [inputKey, setInputKey] = useState(0);
    const query = useQuery({ queryKey: ["own-signature"], queryFn: async () => (await api.get("/auth/signature")).data });
    useEffect(() => () => { if (previewUrl.current) URL.revokeObjectURL(previewUrl.current); }, []);
    const selectFile = (selected) => {
        if (previewUrl.current) URL.revokeObjectURL(previewUrl.current);
        previewUrl.current = selected ? URL.createObjectURL(selected) : "";
        setPreview(previewUrl.current);
        setFile(selected);
    };
    const clear = () => { selectFile(null); setPassword(""); setInputKey((key) => key + 1); };
    const save = useMutation({
        mutationFn: async () => {
            const body = new FormData();
            body.append("file", file);
            body.append("current_password", password);
            return (await api.post("/auth/signature", body)).data;
        },
        onSuccess: (data) => { client.setQueryData(["own-signature"], data); clear(); toast.success("Signature saved"); },
        onError: (error) => toast.error(errorMessage(error)),
    });
    const remove = useMutation({
        mutationFn: () => api.delete("/auth/signature", { data: { current_password: password } }),
        onSuccess: () => { client.setQueryData(["own-signature"], { signature_data: "" }); clear(); toast.success("Signature removed"); },
        onError: (error) => toast.error(errorMessage(error)),
    });
    const busy = save.isPending || remove.isPending;
    if (query.isLoading) return <Spinner/>;
    if (query.isError) return <ErrorState message={errorMessage(query.error)} onRetry={() => query.refetch()}/>;
    const image = preview || query.data?.signature_data;
    return <section className="max-w-lg">
        <h2 className="mb-4 text-lg font-semibold">Approval signature</h2>
        {image ? <div className="mb-5 flex h-36 items-center justify-center border border-[var(--color-line)] bg-white p-4"><img src={image} alt={preview ? "Selected signature preview" : "Saved approval signature"} className="max-h-full max-w-full object-contain"/></div> : <p className="mb-5 text-sm text-black/50">No signature uploaded.</p>}
        <form onSubmit={(event) => { event.preventDefault(); if (file && password && !busy) save.mutate(); }} className="space-y-5">
            <fieldset disabled={busy} className="space-y-5">
                <div><label htmlFor="signature-file" className="mb-2 block text-sm font-semibold">Signature image (PNG or JPEG, up to 1 MB)</label>
                    <input key={inputKey} id="signature-file" type="file" accept="image/png,image/jpeg" onChange={(event) => {
                        const selected = event.target.files?.[0];
                        if (selected && (selected.size > 1024 * 1024 || !["image/png", "image/jpeg"].includes(selected.type))) { toast.error("Choose a PNG or JPEG image up to 1 MB."); event.target.value = ""; selectFile(null); return; }
                        selectFile(selected ?? null);
                    }} className="w-full text-sm"/>
                </div>
                <div><label htmlFor="signature-password" className="mb-2 block text-sm font-semibold">Current password</label>
                    <input id="signature-password" type="password" autoComplete="current-password" maxLength={1024} value={password} onChange={(event) => setPassword(event.target.value)} className="w-full rounded-lg border border-[var(--color-line)] bg-white px-3 py-3 text-sm"/>
                </div>
                <div className="flex flex-wrap gap-3">
                    <button type="submit" disabled={!file || !password || busy} className="inline-flex items-center gap-2 rounded-lg bg-[var(--color-rust)] px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-50"><Upload size={16}/>{save.isPending ? "Saving..." : "Save signature"}</button>
                    {query.data?.signature_data && <button type="button" disabled={!password || busy} onClick={() => { if (window.confirm("Remove your saved signature? Existing approvals will keep their signature.")) remove.mutate(); }} className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-line)] px-4 py-2.5 text-sm font-semibold text-red-700 disabled:opacity-50"><Trash2 size={16}/>{remove.isPending ? "Removing..." : "Remove"}</button>}
                </div>
            </fieldset>
        </form>
    </section>;
}
