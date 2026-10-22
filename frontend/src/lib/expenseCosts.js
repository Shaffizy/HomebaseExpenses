function hundredths(value) {
  const text = String(value ?? "");
  if (!/^\d{1,12}(\.\d{1,2})?$/.test(text)) return 0n;
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
