import { StyledSelect } from "./StyledSelect";
export function PersonSelect({ label, value, options, placeholder = "None", onChange }) {
    return <div>{label && <span className="mb-1.5 block text-xs font-bold text-black/55">{label}</span>}<StyledSelect label={label || placeholder} value={value == null ? "" : String(value)} onChange={(v) => onChange(v ? Number(v) : null)} options={[{ value: "", label: placeholder }, ...options.map((p) => ({ value: String(p.id), label: p.name || p.username, description: p.email || p.username }))]}/></div>;
}
