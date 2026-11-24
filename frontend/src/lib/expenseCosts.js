function hundredths(value) {
  const text = String(value ?? "");
  if (!/^\d{1,14}(\.\d{1,2})?$/.test(text)) return 0n;
  const [whole, fraction = ""] = text.split(".");
  return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
}
export function lineCostCents(item) {
  return (hundredths(item?.quantity) * hundredths(item?.unit_price) + 50n) / 100n;
}
export function overallCostCents(items = []) {
  return items.reduce((sum, item) => sum + lineCostCents(item), 0n);
}
export function formatCost(cents) {
  return (cents / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",") + "." + (cents % 100n).toString().padStart(2, "0");
}

export const DEFAULT_WHT_CLASSIFICATIONS = [
  { value: "NON_TAXABLE_0", label: "Non-Taxable (0%) — Health Related / HMO / Exempt", rate: "0.00" },
  { value: "RATE_2_NETWORK_DATA", label: "2% — Network Infrastructure & Data Services (MTN, IPNX, Cobranet)", rate: "2.00" },
  { value: "RATE_2_SUPPLY_GOODS", label: "2% — Supply of Goods / General Commerce", rate: "2.00" },
  { value: "RATE_2_AGRO", label: "2% — Agriculture & Agro-Allied (Raw Farm Produce, Primary Production, Agro-Processing)", rate: "2.00" },
  { value: "RATE_2_CONSTRUCTION", label: "2% — Civil Engineering, Building & Infrastructure Development", rate: "2.00" },
  { value: "RATE_5_TECH_ICT", label: "5% — ICT, Software Licensing, Cloud Hosting, IT Consultancy & Managed Services", rate: "5.00" },
  { value: "RATE_5_PROFESSIONAL", label: "5% — Professional, Legal, Accounting, Management Consultancy, Financial & Insurance Services", rate: "5.00" },
  { value: "RATE_5_SUBCONTRACT_PROPERTY", label: "5% — Specialized Sub-Contracting (Electrical, Plumbing), Property Management & Agro Services", rate: "5.00" },
  { value: "RATE_5_COMMERCE_SERVICES", label: "5% — Logistics, Freight, Transport, Advertising, Marketing, Events & Commissions", rate: "5.00" },
  { value: "RATE_5_NON_RESIDENT_INFRA", label: "5% (Non-Resident) — Network Infrastructure, Building & Civil Engineering", rate: "5.00" },
  { value: "RATE_10_RENT_LEASE", label: "10% — Commercial & Residential Property Rent or Lease", rate: "10.00" },
  { value: "RATE_10_DIRECTORS_ROYALTIES", label: "10% (Resident) — Directors' Fees, Royalties & Intellectual Property", rate: "10.00" },
  { value: "RATE_10_NON_RESIDENT_SERVICES", label: "10% (Non-Resident) — Professional, ICT, Consultancy, Supply of Goods & General Services", rate: "10.00" },
  { value: "RATE_20_NON_RESIDENT_DIRECTORS_ROYALTIES", label: "20% (Non-Resident) — Directors' Fees, Royalties & Intellectual Property", rate: "20.00" },
];

export function calculateWhtBreakdown(grossAmount, whtClassification, classifications = DEFAULT_WHT_CLASSIFICATIONS) {
  const grossCents = hundredths(grossAmount);
  const found = (classifications?.length ? classifications : DEFAULT_WHT_CLASSIFICATIONS).find(
    (entry) => entry.value === whtClassification
  );
  const rateText = found?.rate ?? "0.00";
  const rateHundredths = hundredths(rateText);
  const whtCents = (grossCents * rateHundredths + 5000n) / 10000n;
  const netCents = grossCents >= whtCents ? grossCents - whtCents : 0n;
  return {
    classification: found?.value ?? "",
    label: found?.label ?? "",
    rate: rateText,
    grossCents,
    whtCents,
    netCents,
    grossFormatted: formatCost(grossCents),
    whtFormatted: formatCost(whtCents),
    netFormatted: formatCost(netCents),
  };
}
