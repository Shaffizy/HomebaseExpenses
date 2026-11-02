import test from "node:test";
import assert from "node:assert/strict";
import { expenseCategoryOptions, expenseCategoryPayload } from "../src/lib/expenseCategorySelection.js";

test("category dropdown uses active admin categories, retaining an inactive saved category", () => {
  const options = expenseCategoryOptions([{id: 1, name: "Transport", is_active: true}, {id: 2, name: "Old", is_active: false}], {category: 2, expense_category_name: "Old"});
  assert.deepEqual(options, [{value: "", label: "Select category"}, {value: "2", label: "Old (inactive)"}, {value: "1", label: "Transport"}]);
  assert.deepEqual(expenseCategoryOptions([{id: 2, name: "Old", is_active: false}]), [{value: "", label: "Select category"}]);
});

test("category selection sends numeric IDs and preserves unchanged legacy categories", () => {
  assert.deepEqual(expenseCategoryPayload("3"), {category: 3});
  assert.deepEqual(expenseCategoryPayload(""), {category: null});
  assert.deepEqual(expenseCategoryPayload("2", {category: 2}), {});
  assert.deepEqual(expenseCategoryPayload("3", {category: 2}), {category: 3});
  assert.deepEqual(expenseCategoryPayload("", {category: 2}), {category: null});
});
