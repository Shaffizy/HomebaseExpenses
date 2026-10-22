import assert from "node:assert/strict";
import test from "node:test";
import rawToast from "react-hot-toast";
import notify from "../src/lib/notifications.js";

test("identical failures reuse one notification instead of stacking", () => {
  const first = notify.error("Homebase is temporarily unavailable.");
  const second = notify.error("Homebase is temporarily unavailable.");
  assert.equal(first, second);
  rawToast.remove();
});

test("success and failure notifications remain distinct", () => {
  assert.notEqual(notify.success("Draft saved"), notify.error("Draft saved"));
  rawToast.remove();
});

test("explicit notification IDs are preserved for callers", () => {
  assert.equal(notify.error("Please try again.", { id: "save-expense" }), "save-expense");
  rawToast.remove();
});
