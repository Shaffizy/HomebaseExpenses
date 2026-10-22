import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
export function StyledSelect({ value, onChange, options, label, className = "", portalContainer, disabled = false }) {
    return <div className={`min-w-0 ${className}`}><Select.Root disabled={disabled} value={value || "__empty__"} onValueChange={(v) => onChange(v === "__empty__" ? "" : v)}>
    <Select.Trigger aria-label={label} className="flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-[var(--color-line)] bg-white px-3 py-2 text-left text-sm font-semibold text-[var(--color-ink)] focus:ring-2 focus:ring-[var(--color-rust)]/25"><span className="min-w-0 truncate"><Select.Value /></span><Select.Icon><ChevronDown size={16}/></Select.Icon></Select.Trigger>
    <Select.Portal container={portalContainer ?? undefined}><Select.Content position="popper" sideOffset={6} collisionPadding={12} className="z-[100] max-h-[var(--radix-select-content-available-height)] min-w-[var(--radix-select-trigger-width)] max-w-[calc(100vw-24px)] overflow-hidden rounded-lg border border-[var(--color-line)] bg-white shadow-xl"><Select.Viewport className="max-h-72 p-1">
      {options.map((o) => <Select.Item key={o.value} value={o.value || "__empty__"} textValue={o.label} className="relative cursor-default rounded-md py-2 pl-3 pr-9 text-sm text-[var(--color-ink)] outline-none data-[highlighted]:bg-[var(--color-linen)] data-[state=checked]:font-semibold"><Select.ItemText>{o.label}</Select.ItemText>{o.description && <span className="block truncate text-xs font-normal text-black/50">{o.description}</span>}<Select.ItemIndicator className="absolute right-3 top-1/2 -translate-y-1/2"><Check size={16}/></Select.ItemIndicator></Select.Item>)}
    </Select.Viewport></Select.Content></Select.Portal>
  </Select.Root></div>;
}
