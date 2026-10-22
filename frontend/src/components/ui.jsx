import { STATUS_LABELS } from "../lib/types";
import { CircleAlert, RefreshCw } from "lucide-react";
export function Spinner({ className = "h-6 w-6" }) {
    return (<svg className={`animate-spin text-[var(--color-rust)] ${className}`} xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" aria-label="Loading">
      <circle className="opacity-15" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
      <path className="opacity-90" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"/>
    </svg>);
}
export function ErrorState({ message, onRetry }) {
    return (<div role="alert" className="border-y border-[var(--color-line)] px-4 py-8 text-center">
      <CircleAlert size={24} aria-hidden="true" className="mx-auto mb-3 text-black/45"/>
      <p className="mx-auto max-w-[48ch] break-words text-sm font-medium leading-6 text-black/65">{message || "We couldn't load this section. Please try again."}</p>
      {onRetry && (<button type="button" onClick={onRetry} className="mt-4 inline-flex items-center gap-2 rounded-lg border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-semibold hover:bg-gray-50">
          <RefreshCw size={15}/>Try again
        </button>)}
    </div>);
}
export function EmptyState({ title, description, action, }) {
    return (<div className="rounded-lg border border-dashed border-[var(--color-line)] bg-white/70 px-8 py-12 text-center">
      <p className="font-display text-[18px] font-bold text-[var(--color-ink)]">{title}</p>
      {description && <p className="mx-auto mt-2 max-w-[46ch] text-sm leading-6 text-black/60">{description}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>);
}
const STATUS_STYLES = {
    DRAFT: "bg-[#f1ead8] text-[#5a4a1e] ring-[#e6d9b8]",
    SUBMITTED: "bg-[#dbeafe] text-[#1e3a5f] ring-[#bfdbfe]",
    APPROVED: "bg-[#dcfce7] text-[#14532d] ring-[#bbf7d0]",
    RETURNED: "bg-[#fef3c7] text-[#7a3d00] ring-[#fde68a]",
    REJECTED: "bg-[#fee2e2] text-[#7f1d1d] ring-[#fecaca]",
    CLOSED: "bg-[#e7e5e4] text-[#44403c] ring-[#d6d3d1]",
};
export function StatusBadge({ status }) {
    return (<span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-bold uppercase tracking-normal ring-1 ring-inset ${STATUS_STYLES[status]}`}>
      <span className="h-1.5 w-1.5 rounded-full bg-current opacity-70"/>
      {STATUS_LABELS[status]}
    </span>);
}
const CURRENCY_SYMBOLS = {
    NGN: "₦",
    USD: "$",
    EUR: "€",
    GBP: "£",
};
export function formatMoney(currency, amount) {
    const symbol = CURRENCY_SYMBOLS[currency];
    return symbol ? `${symbol}${amount}` : `${currency} ${amount}`;
}
export function Card({ children, className = "", }) {
    return (<div className={`rounded-lg border border-[var(--color-line)] bg-white shadow-[0_8px_30px_rgba(14,26,46,0.06)] ${className}`}>
      <div className="p-6 sm:p-7">{children}</div>
    </div>);
}
export function PageHeader({ title, subtitle, actions, }) {
    return (<div className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-[30px] font-extrabold leading-none tracking-normal text-[var(--color-ink)] sm:text-[34px]">
          {title}
        </h1>
        {subtitle && <p className="mt-2 max-w-[62ch] text-[13px] leading-5 text-black/55">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>);
}
export function Modal({ open, title, onClose, children, }) {
    if (!open)
        return null;
    return (<div className="fixed inset-0 z-50 flex items-center justify-center bg-[var(--color-ink)]/40 p-4 backdrop-blur-[2px]" onClick={onClose} role="dialog" aria-modal="true" aria-label={title}>
      <div className="w-full max-w-md rounded-lg border border-white/10 bg-white p-6 shadow-[0_24px_60px_rgba(14,26,46,0.22)]" onClick={(e) => e.stopPropagation()}>
        <div className="mb-4 flex items-center justify-between gap-4">
          <h2 className="font-display text-[18px] font-bold tracking-normal text-[var(--color-ink)]">
            {title}
          </h2>
          <button onClick={onClose} aria-label="Close" className="grid h-8 w-8 place-items-center rounded-full bg-black/[0.06] text-black/60 hover:bg-black/10 hover:text-black">
            ✕
          </button>
        </div>
        {children}
      </div>
    </div>);
}
