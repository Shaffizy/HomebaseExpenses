import { renderToStaticMarkup } from "react-dom/server";
import { Printer } from "lucide-react";
import toast from "../lib/notifications";

const small = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen", "seventeen", "eighteen", "nineteen"];
const tens = ["", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"];
function words(number) {
    if (number < 20) return small[number];
    if (number < 100) return tens[Math.floor(number / 10)] + (number % 10 ? "-" + small[number % 10] : "");
    if (number < 1000) return small[Math.floor(number / 100)] + " hundred" + (number % 100 ? " and " + words(number % 100) : "");
    for (const [scale, label] of [[1e12, "trillion"], [1e9, "billion"], [1e6, "million"], [1000, "thousand"]]) {
        if (number >= scale) return words(Math.floor(number / scale)) + " " + label + (number % scale ? " " + words(number % scale) : "");
    }
}
export function amountInWords(amount) {
    const text = String(amount);
    if (!/^\d{1,14}(\.\d{1,2})?$/.test(text)) return "Amount unavailable";
    const [whole, fraction = ""] = text.split(".");
    const kobo = Number(fraction.padEnd(2, "0"));
    const result = words(Number(whole)) + " naira" + (kobo ? " and " + words(kobo) + " kobo" : "") + " only";
    return result[0].toUpperCase() + result.slice(1);
}
function money(amount) {
    return "NGN " + Number(amount).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
const printStyles = `
    @page { size: A5 landscape; margin: 10mm; }
    * { box-sizing: border-box; }
    body { margin: 0; color: #111; background: white; font-family: Arial, sans-serif; font-size: 8pt; }
    main { width: 190mm; margin: 20px auto; }
    header { display: flex; align-items: center; justify-content: center; gap: 2mm; margin-bottom: 5mm; }
    .bank-mark { position: relative; flex-shrink: 0; width: 11mm; height: 11mm; overflow: hidden; }
    .bank-mark img { position: absolute; width: 35mm; height: 17.5mm; max-width: none; left: -0.3mm; top: -3.5mm; }
    h1 { font-size: 10pt; margin: 0 0 1mm; }
    h2 { font-size: 9pt; margin: 0; }
    .fields { display: grid; grid-template-columns: 1.7fr 1fr; gap: 2mm 5mm; margin-bottom: 4mm; }
    .field { display: flex; gap: 8px; align-items: baseline; min-width: 0; }
    .field strong { flex-shrink: 0; font-size: 8pt; }
    .field span { flex: 1; border-bottom: 0.5pt solid #333; padding-bottom: 1mm; overflow-wrap: anywhere; }
    table { width: 100%; border-collapse: collapse; table-layout: fixed; margin: 4mm 0; }
    th, td { border: 0.5pt solid #333; padding: 1.5mm; height: 6mm; overflow-wrap: anywhere; }
    th { font-size: 8pt; text-align: center; }
    .number { text-align: right; }
    tr { break-inside: avoid; }
    thead { display: table-header-group; }
    tfoot { display: table-row-group; font-weight: bold; }
    .words { margin: 3mm 0; line-height: 1.5; border-bottom: 0.5pt solid #333; padding-bottom: 1.5mm; }
    .approval { margin-top: 3mm; break-inside: avoid; }
    .approval p { margin: 1.5mm 0; }
    .note { font-size: 7pt; color: #444; }
    .signature { display: block; max-width: 48mm; max-height: 12mm; object-fit: contain; object-position: left center; margin: 1mm 0; }
    nav { display: flex; gap: 10px; justify-content: center; padding: 16px; border-bottom: 1px solid #ddd; }
    nav button { padding: 10px 16px; cursor: pointer; background: white; border: 1px solid #888; border-radius: 4px; }
    @media print { nav { display: none; } main { margin: 0; width: 100%; } }
    @media screen and (max-width: 760px) { main { margin: 12px; } }
`;
export function ExpenseTicket({ expense, logoUrl }) {
    const approvedDate = expense.approved_at ? new Date(expense.approved_at).toLocaleString("en-NG", { timeZone: "Africa/Lagos", dateStyle: "medium", timeStyle: "short" }) : "Not recorded";
    return <main>
        <header><span className="bank-mark"><img src={logoUrl} alt="Homebase Mortgage Bank"/></span><div><h1>HOMEBASE MORTGAGE BANK LTD</h1><h2>EXPENSE TICKET</h2></div></header>
        <section className="fields">
            <div className="field"><strong>REQUESTED BY:</strong><span>{expense.requested_by}</span></div>
            <div className="field"><strong>DATE:</strong><span>{expense.due_date || expense.created_at?.slice(0, 10)}</span></div>
            <div className="field"><strong>PURPOSE:</strong><span>{expense.category_name}</span></div>
            <div className="field"><strong>DEPT:</strong><span>{expense.department}</span></div>
            <div className="field"><strong>BRANCH:</strong><span>{expense.branch}</span></div>
            <div className="field"><strong>EXPENSE NO:</strong><span>{expense.expense_number}</span></div>
        </section>
        <table>
            <colgroup><col style={{ width: "5%" }}/><col style={{ width: "43%" }}/><col style={{ width: "14%" }}/><col style={{ width: "18%" }}/><col style={{ width: "20%" }}/></colgroup>
            <thead><tr><th>S/N</th><th>PARTICULAR</th><th className="number">QUANTITY</th><th className="number">UNIT COST</th><th className="number">TOTAL COST</th></tr></thead>
            <tbody>{expense.items.map((item, index) => <tr key={item.id ?? index}><td>{index + 1}</td><td>{item.description}</td><td className="number">{item.quantity}</td><td className="number">{money(item.unit_price)}</td><td className="number">{money(item.line_total)}</td></tr>)}
                {Array.from({ length: Math.max(0, 5 - expense.items.length) }, (_, index) => <tr key={"blank-" + index}><td>&nbsp;</td><td/><td/><td/><td/></tr>)}
            </tbody>
            <tfoot><tr><td colSpan={4} className="number">OVERALL COST</td><td className="number">{money(expense.total)}</td></tr></tfoot>
        </table>
        <div className="words"><strong>AMOUNT IN WORDS:</strong> {amountInWords(expense.total)}</div>
        <section className="approval"><strong>APPROVAL: APPROVED</strong>
            {expense.approved_signature_data ? <img className="signature" src={expense.approved_signature_data} alt="Approver signature"/> : <p>Signature: not recorded</p>}
            <p>Approved by: {expense.approved_by_name || "Not recorded"}</p><p>Approval date: {approvedDate} (Lagos time)</p>
            <p className="note">{expense.approved_signature_data ? "Electronic approval record with the signature saved at approval." : "Electronic approval record. No signature was saved at approval."}</p>
        </section>
    </main>;
}
export function ExpensePrint({ expense }) {
    if (expense.status !== "APPROVED") return null;
    const print = () => {
        const preview = window.open("", "_blank");
        if (!preview) { toast.error("Allow popups to open the expense ticket."); return; }
        preview.opener = null;
        const markup = renderToStaticMarkup(<ExpenseTicket expense={expense} logoUrl={new URL("/homebase-logo.png", window.location.origin).href}/>);
        preview.document.write('<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Approved Expense Ticket</title><style>' + printStyles + '</style></head><body><nav><button id="print" type="button">Print / Save as PDF</button><button id="close" type="button">Close</button></nav>' + markup + '</body></html>');
        preview.document.close();
        preview.document.title = "Expense " + expense.expense_number;
        preview.document.getElementById("print").addEventListener("click", async () => {
            await Promise.all(Array.from(preview.document.images, async (image) => {
                try { await image.decode(); } catch { /* Keep the record printable if an image is unavailable. */ }
            }));
            preview.focus();
            preview.print();
        });
        preview.document.getElementById("close").addEventListener("click", () => preview.close());
    };
    return <button type="button" onClick={print} className="inline-flex items-center gap-2 rounded-lg border border-[var(--color-line)] bg-white px-4 py-2 text-sm font-semibold hover:bg-gray-50"><Printer size={16}/>Print / Save PDF</button>;
}
