import * as Select from "@radix-ui/react-select";
import { Check, ChevronDown, ChevronUp } from "lucide-react";

export function StyledSelect({
    value,
    onChange,
    options,
    label,
    placeholder = "Select an option",
    className = "",
    portalContainer,
    disabled = false,
}) {
    const selectedOption = options.find((o) => o.value === (value ?? ""));
    const isEmpty = !value;
    return (
        <div className={`min-w-0 ${className}`}>
            <Select.Root
                disabled={disabled}
                value={value || "__empty__"}
                onValueChange={(v) => onChange(v === "__empty__" ? "" : v)}
            >
                <Select.Trigger
                    aria-label={label}
                    className={`group flex min-h-11 w-full items-center justify-between gap-3 rounded-lg border border-[var(--color-line)] bg-white px-3.5 py-2.5 text-left text-sm shadow-[0_1px_2px_rgba(14,26,46,0.04)] transition hover:border-black/25 focus:border-[var(--color-rust)] focus:outline-none focus:ring-2 focus:ring-[var(--color-rust)]/15 disabled:cursor-not-allowed disabled:bg-[var(--color-linen)] disabled:opacity-60 ${
                        isEmpty ? "font-medium text-black/50" : "font-semibold text-[var(--color-ink)]"
                    }`}
                >
                    <span className="min-w-0 flex-1 truncate">
                        <Select.Value placeholder={placeholder}>
                            {selectedOption ? selectedOption.label : placeholder}
                        </Select.Value>
                    </span>
                    {selectedOption?.badge && (
                        <span className="shrink-0 rounded-full bg-[var(--color-linen)] px-2 py-0.5 font-mono text-[11px] font-bold text-[var(--color-ink)]">
                            {selectedOption.badge}
                        </span>
                    )}
                    <Select.Icon className="shrink-0 text-black/45 transition-transform duration-150 group-data-[state=open]:rotate-180 group-data-[state=open]:text-[var(--color-ink)]">
                        <ChevronDown size={16} />
                    </Select.Icon>
                </Select.Trigger>
                <Select.Portal container={portalContainer ?? undefined}>
                    <Select.Content
                        position="popper"
                        sideOffset={6}
                        collisionPadding={12}
                        className="z-[120] max-h-[var(--radix-select-content-available-height)] min-w-[var(--radix-select-trigger-width)] max-w-[min(36rem,calc(100vw-24px))] overflow-hidden rounded-xl border border-[var(--color-line)] bg-white shadow-[0_16px_40px_rgba(14,26,46,0.16)] ring-1 ring-black/5"
                    >
                        <Select.ScrollUpButton className="flex h-6 cursor-default items-center justify-center border-b border-[var(--color-line)]/60 bg-white text-black/45">
                            <ChevronUp size={14} />
                        </Select.ScrollUpButton>
                        <Select.Viewport className="max-h-72 overflow-y-auto p-1.5">
                            {options.map((o) => (
                                <Select.Item
                                    key={o.value || "__empty__"}
                                    value={o.value || "__empty__"}
                                    textValue={o.label}
                                    className="relative flex cursor-pointer select-none items-start justify-between gap-3 rounded-lg py-2.5 pl-3 pr-9 text-sm text-[var(--color-ink)] outline-none transition-colors data-[highlighted]:bg-[var(--color-linen)] data-[state=checked]:bg-red-50/60 data-[state=checked]:font-semibold"
                                >
                                    <div className="min-w-0 flex-1">
                                        <Select.ItemText>{o.label}</Select.ItemText>
                                        {o.description && (
                                            <span className="mt-0.5 block text-xs font-normal leading-4 text-black/55">
                                                {o.description}
                                            </span>
                                        )}
                                    </div>
                                    {o.badge && (
                                        <span className="shrink-0 rounded-full border border-[var(--color-line)] bg-white px-2 py-0.5 font-mono text-[11px] font-bold text-[var(--color-ink)]">
                                            {o.badge}
                                        </span>
                                    )}
                                    <Select.ItemIndicator className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[var(--color-rust)]">
                                        <Check size={16} strokeWidth={2.5} />
                                    </Select.ItemIndicator>
                                </Select.Item>
                            ))}
                        </Select.Viewport>
                        <Select.ScrollDownButton className="flex h-6 cursor-default items-center justify-center border-t border-[var(--color-line)]/60 bg-white text-black/45">
                            <ChevronDown size={14} />
                        </Select.ScrollDownButton>
                    </Select.Content>
                </Select.Portal>
            </Select.Root>
        </div>
    );
}
