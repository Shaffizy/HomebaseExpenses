import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { LockKeyhole } from "lucide-react";
import toast from "../lib/notifications";
import { useAuth } from "../auth/AuthContext";
import { api, errorMessage, fieldErrors } from "../lib/api";
import { PageHeader } from "../components/ui";
import { SignatureSettings } from "../components/SignatureSettings";
import { EmailDeliverySettings } from "../components/EmailDeliverySettings";

export function SettingsPage() {
  const { user, logout } = useAuth();
  const [params] = useSearchParams();
  const section = user?.role === "ADMIN" && params.get("section") === "email" ? "email" : user?.role === "APPROVER" && params.get("section") === "signature" ? "signature" : "password";
  const navigate = useNavigate();
  const cache = useQueryClient();
  const [form, setForm] = useState({ current_password: "", new_password: "", confirm_password: "" });
  const [errors, setErrors] = useState({});
  const mutation = useMutation({
    mutationFn: () => api.post("/auth/change-password", form),
    onSuccess: () => { setForm({ current_password: "", new_password: "", confirm_password: "" }); logout(); cache.clear(); toast.success("Password changed. Sign in with your new password."); navigate("/login", { replace: true }); },
    onError: (error) => { setErrors(fieldErrors(error)); toast.error(errorMessage(error)); },
  });
  const submit = (event) => {
    event.preventDefault();
    if (mutation.isPending) return;
    setErrors({});
    if (form.new_password !== form.confirm_password) { setErrors({ confirm_password: ["Passwords do not match."] }); return; }
    mutation.mutate();
  };
  return <div>
    <PageHeader title="Settings" />
    {section === "email" ? <EmailDeliverySettings/> : section === "signature" ? <SignatureSettings/> : <>
    <div className="mb-6 flex items-center gap-3 border-b border-[var(--color-line)] pb-5"><LockKeyhole size={22} className="text-[var(--color-rust)]" /><div><h2 className="text-lg font-semibold">Password</h2><p className="text-sm text-black/50">{user?.name}</p></div></div>
    <form onSubmit={submit} className="max-w-lg space-y-5">
      <fieldset disabled={mutation.isPending} className="space-y-5">
        {[["current_password", "Current password", "current-password"], ["new_password", "New password", "new-password"], ["confirm_password", "Confirm new password", "new-password"]].map(([field, label, autocomplete]) => <div key={field}>
          <label htmlFor={field} className="mb-2 block text-sm font-semibold">{label}</label>
          <input id={field} type="password" autoComplete={autocomplete} required maxLength={1024} minLength={field === "current_password" ? undefined : 8} value={form[field]} onChange={(event) => setForm({ ...form, [field]: event.target.value })} aria-invalid={!!errors[field]} aria-describedby={errors[field] ? field + "-error" : undefined} className="w-full rounded-lg border border-[var(--color-line)] bg-white px-3 py-3 text-sm outline-none focus:border-[var(--color-rust)] focus:ring-2 focus:ring-red-100" />
          {errors[field] && <p id={field + "-error"} role="alert" className="mt-2 text-sm text-red-700">{Array.isArray(errors[field]) ? errors[field].join(" ") : String(errors[field])}</p>}
        </div>)}
        {errors.non_field_errors && <p role="alert" className="text-sm text-red-700">{errors.non_field_errors.join(" ")}</p>}
        <button type="submit" className="rounded-lg bg-[var(--color-rust)] px-5 py-3 text-sm font-semibold text-white hover:bg-[var(--color-rust-hover)] disabled:opacity-50">{mutation.isPending ? "Updating..." : "Change password"}</button>
      </fieldset>
    </form>
    </>}
  </div>;
}
