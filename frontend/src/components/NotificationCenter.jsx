import toast, { Toaster, resolveValue } from "react-hot-toast";
import { CircleCheck, CircleAlert, X } from "lucide-react";

export function NotificationCenter() {
  return <Toaster position="bottom-right" gutter={10} containerStyle={{ bottom: 20, right: 16, left: 16 }}>
    {(notification) => {
      const failed = notification.type === "error";
      const Icon = failed ? CircleAlert : CircleCheck;
      return <div {...notification.ariaProps} className={`pointer-events-auto flex w-[calc(100vw-32px)] max-w-sm items-start gap-3 rounded-lg border bg-white p-4 shadow-lg transition-all motion-reduce:transition-none ${notification.visible ? "translate-y-0 opacity-100" : "translate-y-2 opacity-0"} ${failed ? "border-red-200" : "border-green-200"}`}>
        <Icon size={20} aria-hidden="true" className={`mt-0.5 shrink-0 ${failed ? "text-red-700" : "text-green-700"}`}/>
        <p className="min-w-0 flex-1 break-words text-sm leading-6 text-[var(--color-ink)]">{resolveValue(notification.message, notification)}</p>
        <button type="button" onClick={() => toast.dismiss(notification.id)} aria-label="Dismiss notification" title="Dismiss notification" className="grid h-7 w-7 shrink-0 place-items-center rounded text-black/50 hover:bg-gray-100 hover:text-black"><X size={16}/></button>
      </div>;
    }}
  </Toaster>;
}
