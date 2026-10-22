import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import toast from "../lib/notifications";
import { useAuth } from "../auth/AuthContext";
import { StyledSelect } from "../components/StyledSelect";
import { ErrorState, Modal, PageHeader, Spinner } from "../components/ui";
import { errorMessage } from "../lib/api";
import * as adminApi from "../lib/adminApi";
import { ExpenseCategoriesAdmin } from "../components/ExpenseCategoriesAdmin";

const emptyForm = { username: "", email: "", first_name: "", last_name: "", role: "REQUESTER", password: "", is_active: true };
const fieldClass = "w-full rounded-lg border border-[var(--color-line)] bg-white p-2 text-sm";

export function AdminPage() {
  const { user } = useAuth();
  const [params] = useSearchParams();
  const client = useQueryClient();
  const [form, setForm] = useState(null);
  const [editing, setEditing] = useState(null);
  const [target, setTarget] = useState(null);
  const users = useQuery({ queryKey: ["users", user?.organization.id], enabled: user?.role === "ADMIN", queryFn: () => adminApi.listUsers(user.organization.id) });
  const refresh = () => client.invalidateQueries({ queryKey: ["users"] });
  const save = useMutation({
    mutationFn: () => editing ? adminApi.updateUser(user.organization.id, editing.id, form) : adminApi.registerUser(form),
    onSuccess: () => { toast.success(editing ? "User updated" : "User registered"); setForm(null); setEditing(null); refresh(); },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const deactivate = useMutation({
    mutationFn: () => adminApi.deleteUser(user.organization.id, target.id),
    onSuccess: () => { toast.success("User deactivated"); setTarget(null); refresh(); },
    onError: (error) => toast.error(errorMessage(error)),
  });
  if (user?.role !== "ADMIN") return <ErrorState message="Only administrators can manage users." />;
  if (params.get("section") === "categories") return <ExpenseCategoriesAdmin/>;
  const hasApprover = users.data?.some((person) => person.role === "APPROVER" && person.is_active && person.id !== editing?.id);
  const roles = editing?.role === "ADMIN" ? [{ value: "ADMIN", label: "Admin" }] : [{ value: "REQUESTER", label: "Requester" }, ...(!hasApprover || editing?.role === "APPROVER" ? [{ value: "APPROVER", label: "Approver" }] : [])];
  return <div>
    <PageHeader title="User management" actions={<button type="button" onClick={() => { setEditing(null); setForm({ ...emptyForm }); }} className="rounded-lg bg-[var(--color-ink)] px-4 py-2 text-sm font-semibold text-white">Register user</button>} />
    {users.isLoading ? <Spinner /> : users.isError ? <ErrorState message={errorMessage(users.error)} onRetry={() => users.refetch()} /> : <div className="overflow-x-auto"><table className="w-full text-left text-sm">
      <thead><tr className="border-b"><th className="p-3">Name</th><th className="p-3">Email</th><th className="p-3">Role</th><th className="p-3">Status</th><th className="p-3">Actions</th></tr></thead>
      <tbody>{users.data?.map((person) => <tr key={person.id} className="border-b border-[var(--color-line)]"><td className="p-3">{person.name}</td><td className="p-3">{person.email}</td><td className="p-3">{person.role}</td><td className="p-3">{person.is_active ? "Active" : "Inactive"}</td><td className="p-3"><div className="flex gap-2">
        <button type="button" onClick={() => { setEditing(person); setForm({ email: person.email, first_name: person.first_name, last_name: person.last_name, role: person.role, is_active: person.is_active }); }} className="rounded-lg border px-3 py-1">Edit</button>
        <button type="button" disabled={person.id === user.id || !person.is_active} onClick={() => setTarget(person)} className="rounded-lg border px-3 py-1 text-red-700 disabled:opacity-40">Deactivate</button>
      </div></td></tr>)}</tbody>
    </table></div>}
    <Modal open={!!form} title={editing ? "Edit user" : "Register user"} onClose={() => { if (!save.isPending) setForm(null); }}>
      {form && <form onSubmit={(event) => { event.preventDefault(); if (!save.isPending) save.mutate(); }} className="space-y-3">
        <fieldset disabled={save.isPending} className="space-y-3">
          {!editing && <label className="block text-sm">Username<input required value={form.username} onChange={(event) => setForm({ ...form, username: event.target.value })} className={fieldClass} /></label>}
          <label className="block text-sm">Email<input required type="email" value={form.email} onChange={(event) => setForm({ ...form, email: event.target.value })} className={fieldClass} /></label>
          <label className="block text-sm">First name<input value={form.first_name} onChange={(event) => setForm({ ...form, first_name: event.target.value })} className={fieldClass} /></label>
          <label className="block text-sm">Last name<input value={form.last_name} onChange={(event) => setForm({ ...form, last_name: event.target.value })} className={fieldClass} /></label>
          <StyledSelect label="Role" value={form.role} onChange={(role) => setForm({ ...form, role })} options={roles} />
          {!editing && <label className="block text-sm">Password<input required type="password" minLength={8} value={form.password} onChange={(event) => setForm({ ...form, password: event.target.value })} className={fieldClass} /></label>}
          {editing && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active} onChange={(event) => setForm({ ...form, is_active: event.target.checked })} />Active</label>}
          <button type="submit" className="rounded-lg bg-[var(--color-ink)] px-4 py-2 text-sm text-white">{save.isPending ? "Saving..." : "Save"}</button>
        </fieldset>
      </form>}
    </Modal>
    <Modal open={!!target} title="Deactivate user" onClose={() => { if (!deactivate.isPending) setTarget(null); }}><p className="text-sm">Deactivate {target?.name}? Their expense records will remain.</p><button type="button" disabled={deactivate.isPending} onClick={() => deactivate.mutate()} className="mt-4 rounded-lg bg-red-700 px-4 py-2 text-sm text-white">{deactivate.isPending ? "Deactivating..." : "Deactivate"}</button></Modal>
  </div>;
}
