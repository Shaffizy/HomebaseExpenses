import { useState } from "react";
import { Download, LoaderCircle } from "lucide-react";
import toast from "../lib/notifications";
import { getExpense, errorMessage } from "../lib/api";
import { amountInWords } from "./ExpensePrint";

const money = (value) => "NGN " + Number(value).toLocaleString("en-NG", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export async function createExpensePdf(expense, logoData) {
    if (expense.status !== "APPROVED") throw new Error("Only approved expenses can be downloaded.");
    const [{ jsPDF }, { autoTable }] = await Promise.all([import("jspdf"), import("jspdf-autotable")]);
    const doc = new jsPDF({ format: "a5", orientation: "landscape", unit: "mm" });
    doc.setProperties({ title: "Approved Expense " + expense.expense_number, subject: "Homebase expense approval ticket" });
    const top = 9;
    if (logoData) {
        try {
            doc.saveGraphicsState();
            doc.rect(50.8, 6.8, 10.2, 10.2, null).clip();
            doc.discardPath();
            doc.addImage(logoData, "PNG", 50.5, 3.5, 32, 16);
            doc.restoreGraphicsState();
        } catch { doc.restoreGraphicsState(); /* Keep text branding if the logo is unavailable. */ }
    }
    doc.setFont("helvetica", "bold");
    doc.setFontSize(10);
    doc.text("HOMEBASE MORTGAGE BANK LTD", 120, top + 2, { align: "center" });
    doc.setFontSize(9);
    doc.text("EXPENSE TICKET", 120, top + 6.5, { align: "center" });
    doc.setFont("helvetica", "normal");

    autoTable(doc, {
        startY: top + 13, margin: { left: 10, right: 10, top: 10, bottom: 12 },
        theme: "plain", styles: { fontSize: 8, cellPadding: { top: 1.5, bottom: 1.5, left: 0, right: 3 }, textColor: 0, lineColor: 70, lineWidth: { bottom: 0.15 }, overflow: "linebreak" },
        body: [
            ["REQUESTED BY: " + expense.requested_by, "DATE: " + (expense.due_date || expense.created_at?.slice(0, 10) || "")],
            ["PURPOSE: " + expense.category_name, "DEPT: " + expense.department],
            ["BRANCH: " + expense.branch, "EXPENSE NO: " + expense.expense_number],
        ],
        columnStyles: { 0: { cellWidth: 120 }, 1: { cellWidth: 70 } },
    });
    const rows = expense.items.map((item, index) => [String(index + 1), item.description, String(item.quantity), money(item.unit_price), money(item.line_total)]);
    while (rows.length < 5) rows.push(["", "", "", "", ""]);
    rows.push([{ content: "OVERALL COST", colSpan: 4, styles: { halign: "right", fontStyle: "bold" } }, { content: money(expense.total), styles: { fontStyle: "bold" } }]);
    autoTable(doc, {
        startY: doc.lastAutoTable.finalY + 4,
        margin: { left: 10, right: 10, top: 10, bottom: 12 },
        head: [["S/N", "PARTICULAR", "QUANTITY", "UNIT COST", "TOTAL COST"]],
        body: rows, theme: "grid", rowPageBreak: "avoid",
        styles: { fontSize: 8, cellPadding: 1.5, minCellHeight: 6, lineColor: 40, lineWidth: 0.15, textColor: 0, overflow: "linebreak" },
        headStyles: { fillColor: [255, 255, 255], textColor: 0, fontStyle: "bold", halign: "center", minCellHeight: 5 },
        columnStyles: { 0: { cellWidth: 10 }, 1: { cellWidth: 82 }, 2: { cellWidth: 26, halign: "right" }, 3: { cellWidth: 35, halign: "right" }, 4: { cellWidth: 37, halign: "right" } },
    });
    const approvalTime = expense.approved_at ? new Date(expense.approved_at).toLocaleString("en-NG", { timeZone: "Africa/Lagos", dateStyle: "medium", timeStyle: "short" }) : "Not recorded";
    const summary = [
        [{ content: "AMOUNT IN WORDS: " + amountInWords(expense.total), styles: { lineColor: 40, lineWidth: { bottom: 0.2 } } }],
        ["APPROVAL: APPROVED"],
        expense.approved_signature_data ? [{ content: "", styles: { minCellHeight: 14 } }] : ["Signature: not recorded"],
        ["Approved by: " + (expense.approved_by_name || "Not recorded")],
        ["Approval date: " + approvalTime + " (Lagos time)"],
        [expense.approved_signature_data ? "Electronic approval record with the signature saved at approval." : "Electronic approval record. No signature was saved at approval."],
    ];
    autoTable(doc, {
        startY: doc.lastAutoTable.finalY + 4,
        margin: { left: 10, right: 10, top: 10, bottom: 12 }, body: summary,
        theme: "plain", styles: { fontSize: 8, cellPadding: { top: 1, bottom: 1, left: 0, right: 0 }, textColor: 0 }, rowPageBreak: "avoid",
        didDrawCell: (data) => {
            if (data.section !== "body" || data.row.index !== 2 || !expense.approved_signature_data) return;
            const properties = doc.getImageProperties(expense.approved_signature_data);
            const scale = Math.min(48 / properties.width, 12 / properties.height);
            doc.addImage(expense.approved_signature_data, "PNG", data.cell.x, data.cell.y + 1, properties.width * scale, properties.height * scale);
        },
    });
    const pages = doc.getNumberOfPages();
    for (let page = 1; page <= pages; page++) {
        doc.setPage(page);
        doc.setFontSize(7);
        doc.text(expense.expense_number + " | Page " + page + " of " + pages, 105, doc.internal.pageSize.getHeight() - 5, { align: "center" });
    }
    return doc;
}

export function ExpenseDownload({ expense }) {
    const [downloading, setDownloading] = useState(false);
    if (expense.status !== "APPROVED") return null;
    const download = async () => {
        setDownloading(true);
        try {
            // Fetch the current, organization-scoped record rather than trusting a stale list row.
            const current = await getExpense(expense.id);
            let logo;
            try {
                const response = await fetch("/homebase-logo.png");
                if (response.ok) logo = new Uint8Array(await response.arrayBuffer());
            } catch { /* The ticket remains usable without a logo. */ }
            const doc = await createExpensePdf(current, logo);
            const name = String(current.expense_number).replace(/[^a-zA-Z0-9_-]/g, "_");
            doc.save(name + "-approved.pdf");
            toast.success("Approved expense downloaded");
        } catch (err) {
            toast.error(errorMessage(err) || "Unable to download the expense.");
        } finally {
            setDownloading(false);
        }
    };
    return <button type="button" onClick={download} disabled={downloading} aria-label={"Download approved expense " + expense.expense_number} title="Download approved ticket as PDF" className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--color-line)] bg-white px-3 py-1.5 text-xs font-semibold hover:bg-gray-50 disabled:opacity-50">
        {downloading ? <LoaderCircle size={15} className="animate-spin"/> : <Download size={15}/>}
        {downloading ? "Downloading..." : "Download"}
    </button>;
}
