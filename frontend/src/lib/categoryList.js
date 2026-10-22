export function categoryPage(categories, { search = "", status = "all", page = 1, pageSize = 10 } = {}) {
  const term = search.trim().toLocaleLowerCase();
  const filtered = categories.filter((category) =>
    category.name.toLocaleLowerCase().includes(term) &&
    (status === "all" || (status === "active" ? category.is_active : !category.is_active))
  ).sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: "base", numeric: true }) || a.id - b.id);
  const size = Math.max(1, Math.floor(Number(pageSize) || 10));
  const totalPages = Math.max(1, Math.ceil(filtered.length / size));
  const currentPage = Math.min(totalPages, Math.max(1, Math.floor(Number(page) || 1)));
  const offset = (currentPage - 1) * size;
  return {
    rows: filtered.slice(offset, offset + size),
    count: filtered.length,
    page: currentPage,
    totalPages,
    start: filtered.length ? offset + 1 : 0,
    end: Math.min(offset + size, filtered.length),
  };
}
