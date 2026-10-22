import { Component } from "react";
import { RefreshCw } from "lucide-react";

export class AppErrorBoundary extends Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    if (import.meta.env.DEV) console.error("Homebase page failed to render", error, info);
  }

  render() {
    if (!this.state.failed) return this.props.children;
    return <main className="grid min-h-screen place-items-center bg-[var(--color-paper)] px-6">
      <section className="w-full max-w-md text-center" role="alert">
        <img src="/homebase-logo.png" alt="Homebase Mortgage Bank" className="mx-auto mb-8 h-14 w-44 object-contain"/>
        <h1 className="text-xl font-semibold">This page couldn't load</h1>
        <p className="mt-3 text-sm leading-6 text-black/60">Please refresh the page. If it keeps happening, contact your administrator.</p>
        <button type="button" onClick={() => window.location.reload()} className="mt-6 inline-flex items-center gap-2 rounded-lg bg-[var(--color-rust)] px-5 py-3 text-sm font-semibold text-white"><RefreshCw size={16}/>Refresh page</button>
        <a href="/" className="mt-4 block text-sm underline">Return to dashboard</a>
      </section>
    </main>;
  }
}
