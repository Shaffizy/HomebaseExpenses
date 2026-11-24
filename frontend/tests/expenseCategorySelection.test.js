import test from "node:test";
import assert from "node:assert/strict";
import { expenseCategoryOptions, expenseCategoryPayload, categoryParticular } from "../src/lib/expenseCategorySelection.js";
import { calculateWhtBreakdown, DEFAULT_WHT_CLASSIFICATIONS } from "../src/lib/expenseCosts.js";

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

test("category fills a blank particular and updates an automatic description without overwriting custom text", () => {
  assert.equal(categoryParticular("", "", "Transport"), "Transport");
  assert.equal(categoryParticular("Transport", "Transport", "Repairs"), "Repairs");
  assert.equal(categoryParticular("Taxi to client", "Transport", "Repairs"), "Taxi to client");
  assert.equal(categoryParticular("", "Transport", "Repairs"), "Repairs");
  assert.equal(categoryParticular("Custom", "Transport", ""), "Custom");
});

test("WHT calculation computes exact gross, withholding tax, and net payable for 0%, 2%, 5%, 10%, and 20% tiers", () => {
  assert.equal(DEFAULT_WHT_CLASSIFICATIONS.length >= 10, true);
  const exempt = calculateWhtBreakdown("50000.00", "NON_TAXABLE_0");
  assert.equal(exempt.rate, "0.00");
  assert.equal(exempt.whtFormatted, "0.00");
  assert.equal(exempt.netFormatted, "50,000.00");

  const network = calculateWhtBreakdown("100000.00", "RATE_2_NETWORK_DATA");
  assert.equal(network.rate, "2.00");
  assert.equal(network.whtFormatted, "2,000.00");
  assert.equal(network.netFormatted, "98,000.00");

  const prof = calculateWhtBreakdown("250000.00", "RATE_5_PROFESSIONAL");
  assert.equal(prof.rate, "5.00");
  assert.equal(prof.whtFormatted, "12,500.00");
  assert.equal(prof.netFormatted, "237,500.00");

  const rent = calculateWhtBreakdown("1200000.00", "RATE_10_RENT_LEASE");
  assert.equal(rent.rate, "10.00");
  assert.equal(rent.whtFormatted, "120,000.00");
  assert.equal(rent.netFormatted, "1,080,000.00");

  const nonResidentDirectors = calculateWhtBreakdown("500000.00", "RATE_20_NON_RESIDENT_DIRECTORS_ROYALTIES");
  assert.equal(nonResidentDirectors.rate, "20.00");
  assert.equal(nonResidentDirectors.whtFormatted, "100,000.00");
  assert.equal(nonResidentDirectors.netFormatted, "400,000.00");
});
