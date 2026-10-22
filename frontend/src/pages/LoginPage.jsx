import { useState } from "react";
import toast from "../lib/notifications";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthContext";
import { errorMessage } from "../lib/api";
import { Spinner } from "../components/ui";

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  if (loading) return <div className="grid min-h-screen place-items-center"><Spinner /></div>;
  if (user) return <Navigate to={location.state?.from?.pathname ?? "/"} replace />;
  const submit = async (event) => {
    event.preventDefault();
    if (submitting) return;
    setSubmitting(true); setError(null);
    try { await login(username.trim(), password); navigate(location.state?.from?.pathname ?? "/", { replace: true }); }
    catch (error) { const message = errorMessage(error); setError(message); toast.error(message); }
    finally { setSubmitting(false); }
  };
  return <main className="flex min-h-screen items-center justify-center border-t-4 border-[var(--color-rust)] bg-white px-6 py-12">
    <div className="w-full max-w-sm">
      <img src="/homebase-logo.png" alt="Homebase Mortgage Bank" className="mb-10 h-16 w-52 object-contain object-left" />
      <h1 className="text-2xl font-semibold">Expense portal</h1>
      <p className="mt-2 text-sm text-black/50">Sign in to your account</p>
      <form onSubmit={submit} className="mt-8 space-y-5">
        <fieldset disabled={submitting} className="space-y-5">
          <div><label htmlFor="username" className="mb-2 block text-sm font-semibold">Username or email</label><input id="username" value={username} onChange={(event) => setUsername(event.target.value)} autoComplete="username" required className="login-input w-full rounded-lg border border-[var(--color-line)] bg-white text-sm outline-none focus:border-[var(--color-rust)] focus:ring-2 focus:ring-red-100" /></div>
          <div><label htmlFor="password" className="mb-2 block text-sm font-semibold">Password</label><input id="password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required className="login-input w-full rounded-lg border border-[var(--color-line)] bg-white text-sm outline-none focus:border-[var(--color-rust)] focus:ring-2 focus:ring-red-100" /></div>
          {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
          <button type="submit" className="flex w-full items-center justify-center gap-2 rounded-lg bg-[var(--color-rust)] px-4 py-3 text-sm font-semibold text-white hover:bg-[var(--color-rust-hover)]">{submitting && <Spinner className="h-4 w-4" />}{submitting ? "Signing in..." : "Sign in"}</button>
        </fieldset>
      </form>
    </div>
  </main>;
}
