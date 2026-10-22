import assert from "node:assert/strict";
import { afterEach, beforeEach, test } from "node:test";
import axios from "axios";
import { api, tokenStore, AUTH_LOGGED_OUT_EVENT } from "../src/lib/api.js";

const originalAdapter = axios.defaults.adapter;
const originalApiAdapter = api.defaults.adapter;
let values;

function response(config, status = 200, data = {}) {
  return { config, status, data, headers: {}, statusText: String(status) };
}
function unauthorized(config) {
  return new axios.AxiosError("PRIVATE: expired token", "ERR_BAD_REQUEST", config, null, response(config, 401));
}

beforeEach(() => {
  values = new Map();
  globalThis.localStorage = { getItem: (key) => values.get(key) ?? null, setItem: (key, value) => values.set(key, value), removeItem: (key) => values.delete(key) };
  globalThis.window = new EventTarget();
  tokenStore.set("old-access", "valid-refresh");
});
afterEach(() => {
  axios.defaults.adapter = originalAdapter;
  api.defaults.adapter = originalApiAdapter;
});

test("401 refreshes once and retries with the new access token", async () => {
  let refreshes = 0;
  axios.defaults.adapter = async (config) => { refreshes++; return response(config, 200, { access: "new-access", refresh: "new-refresh" }); };
  api.defaults.adapter = async (config) => {
    if (config.headers.Authorization === "Bearer old-access") throw unauthorized(config);
    return response(config, 200, { ok: true });
  };
  const result = await api.get("/auth/me");
  assert.equal(result.data.ok, true);
  assert.equal(refreshes, 1);
  assert.equal(tokenStore.access, "new-access");
});

test("concurrent expired requests share one refresh", async () => {
  let refreshes = 0;
  axios.defaults.adapter = async (config) => { refreshes++; await new Promise((resolve) => setTimeout(resolve, 10)); return response(config, 200, { access: "new-access" }); };
  api.defaults.adapter = async (config) => {
    if (config.headers.Authorization === "Bearer old-access") throw unauthorized(config);
    return response(config);
  };
  await Promise.all([api.get("/auth/me"), api.get("/expenses/"), api.get("/expense-categories/")]);
  assert.equal(refreshes, 1);
});

test("a refresh network failure does not destroy the saved login", async () => {
  api.defaults.adapter = async (config) => { throw unauthorized(config); };
  axios.defaults.adapter = async (config) => { throw new axios.AxiosError("PRIVATE network details", "ERR_NETWORK", config); };
  await assert.rejects(api.get("/auth/me"), (error) => error.code === "ERR_NETWORK");
  assert.equal(tokenStore.refresh, "valid-refresh");
  assert.equal(tokenStore.access, "old-access");
});

test("an invalid refresh token clears the session", async () => {
  let loggedOut = 0;
  window.addEventListener(AUTH_LOGGED_OUT_EVENT, () => loggedOut++);
  api.defaults.adapter = async (config) => { throw unauthorized(config); };
  axios.defaults.adapter = async (config) => { throw unauthorized(config); };
  await assert.rejects(api.get("/auth/me"));
  assert.equal(tokenStore.access, null);
  assert.equal(tokenStore.refresh, null);
  assert.equal(loggedOut, 1);
});

test("writes are not retried after timeouts", async () => {
  let attempts = 0;
  api.defaults.adapter = async (config) => { attempts++; throw new axios.AxiosError("timeout", "ECONNABORTED", config); };
  await assert.rejects(api.post("/expenses/1/approve/"));
  assert.equal(attempts, 1);
  assert.equal(tokenStore.access, "old-access");
});
