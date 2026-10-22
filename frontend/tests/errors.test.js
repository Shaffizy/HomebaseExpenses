import assert from "node:assert/strict";
import test from "node:test";
import { errorMessage, fieldErrors, retryQuery } from "../src/lib/errors.js";

const failure = (status, data, url = "/expenses/") => ({ isAxiosError: true, config: { url, method: "get" }, response: { status, data } });

test("server details, HTML, SQL and exception messages never reach users", () => {
  for (const payload of ["<html>SECRET traceback</html>", { detail: "OperationalError SECRET postgres://private" }, { detail: "C:\\private\\secret.env" }]) {
    for (const status of [400, 500, 502, 503]) assert.doesNotMatch(errorMessage(failure(status, payload)), /SECRET|traceback|OperationalError|postgres|secret\.env|html/i);
  }
  assert.doesNotMatch(errorMessage(new Error("PRIVATE internal failure")), /PRIVATE|internal/);
});

test("login failures and expired sessions have different safe messages", () => {
  assert.match(errorMessage(failure(401, { detail: "token_not_valid" }, "/auth/login")), /password don't match/);
  assert.match(errorMessage(failure(401, { detail: "token_not_valid" })), /session has expired/);
});

test("common HTTP failures have useful nontechnical messages", () => {
  for (const [status, expected] of [[403, /permission/], [404, /no longer available/], [409, /expense has changed/], [410, /no longer available/], [413, /file is too large/], [429, /wait/], [500, /temporarily unavailable/]]) {
    assert.match(errorMessage(failure(status, {})), expected);
  }
});

test("field validation stays actionable without echoing backend values", () => {
  const error = failure(400, { email: ["Enter a valid email address."], items: [{ quantity: ["Ensure this value is greater than or equal to 0."] }] });
  const message = errorMessage(error);
  assert.match(message, /Email address: Enter a valid email address/);
  assert.match(message, /Quantity: Use zero or a positive amount/);
  assert.doesNotMatch(message, /greater than or equal|items\[/);
});

test("password errors are sanitized for inline fields", () => {
  const error = failure(400, { current_password: ["Current password is incorrect."], new_password: ["SECRET database error"], debug: "SECRET" });
  assert.deepEqual(fieldErrors(error), { current_password: ["Your current password is incorrect."] });
  assert.deepEqual(fieldErrors(failure(500, { current_password: "SECRET" })), {});
});

test("missing required comments produce a clear business message", () => {
  assert.equal(errorMessage(failure(400, { detail: "A comment is required." })), "Add a comment before continuing.");
});

test("network failures never display Axios internals", () => {
  const error = { isAxiosError: true, code: "ERR_NETWORK", message: "Network Error", config: { method: "get", url: "/expenses/" } };
  assert.match(errorMessage(error), /couldn't reach Homebase/);
  assert.doesNotMatch(errorMessage(error), /Axios|ERR_NETWORK|Network Error/);
  error.config.method = "post";
  assert.match(errorMessage(error), /couldn't confirm the change/);
  error.config.url = "/auth/refresh";
  assert.match(errorMessage(error), /couldn't reach Homebase/);
});

test("unknown and oversized validation payloads have a safe bounded fallback", () => {
  assert.equal(errorMessage(failure(400, { debug: "SECRET" })), "Check the details you entered and try again.");
  assert.equal(errorMessage(null), "We couldn't complete that. Please try again.");
  assert.ok(errorMessage(failure(400, { items: Array.from({ length: 100 }, () => ({ quantity: ["This field is required."] })) })).length < 400);
});

test("query retries are limited to transient failures", () => {
  for (const status of [400, 401, 403, 404, 409, 429]) assert.equal(retryQuery(0, failure(status, {})), false);
  assert.equal(retryQuery(0, failure(503, {})), true);
  assert.equal(retryQuery(1, failure(503, {})), false);
  assert.equal(retryQuery(0, {}), true);
});
