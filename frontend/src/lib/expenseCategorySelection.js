export function expenseCategoryOptions(categories = [], expense) {
  const result = categories.filter((category) => category.is_active !== false).map((category) => ({ value: String(category.id), label: category.name }));
  if (expense?.category && !result.some((option) => option.value === String(expense.category))) {
    result.unshift({ value: String(expense.category), label: `${expense.expense_category_name || "Existing category"} (inactive)` });
  }
  return [{ value: "", label: "Select category" }, ...result];
}

export function expenseCategoryPayload(value, expense) {
  const category = value ? Number(value) : null;
  // Preserve an unchanged legacy category without trying to select an inactive one again.
  if (expense && category === (expense.category ?? null)) return {};
  return { category };
}
