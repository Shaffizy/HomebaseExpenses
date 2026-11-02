import axios from "axios";
export { errorMessage, fieldErrors } from "./errors.js";
const BASE_URL = import.meta.env?.VITE_API_URL ?? "/api";
const ACCESS_KEY = "billmgmt.access";
const REFRESH_KEY = "billmgmt.refresh";
let sessionVersion = 0;
export const tokenStore = {
    get version() { return sessionVersion; },
    startSession(access, refresh) {
        this.clear();
        this.set(access, refresh);
    },
    get access() {
        return sessionStorage.getItem(ACCESS_KEY);
    },
    get refresh() {
        return sessionStorage.getItem(REFRESH_KEY);
    },
    set(access, refresh) {
        sessionStorage.setItem(ACCESS_KEY, access);
        sessionStorage.setItem(REFRESH_KEY, refresh);
    },
    clear() {
        sessionVersion++;
        sessionStorage.removeItem(ACCESS_KEY);
        sessionStorage.removeItem(REFRESH_KEY);
    },
};
/** Fired when the refresh token is dead and the user must log in again. */
export const AUTH_LOGGED_OUT_EVENT = "auth:logged-out";
export const api = axios.create({ baseURL: BASE_URL, timeout: 30000 });
api.interceptors.request.use((config) => {
    config._sessionVersion ??= tokenStore.version;
    if (config._sessionVersion !== tokenStore.version) throw new axios.CanceledError("Account changed. Request cancelled.");
    const access = tokenStore.access;
    if (access)
        config.headers.Authorization = `Bearer ${access}`;
    return config;
});
let refreshing = null;
function expireSession(version = tokenStore.version) {
    if (version !== tokenStore.version) return;
    tokenStore.clear();
    window.dispatchEvent(new Event(AUTH_LOGGED_OUT_EVENT));
}
async function refreshAccess(version) {
    const refresh = tokenStore.refresh;
    if (!refresh) {
        expireSession(version);
        return null;
    }
    try {
        const { data } = await axios.post(`${BASE_URL}/auth/refresh`, { refresh }, { timeout: 15000 });
        if (version !== tokenStore.version) throw new axios.CanceledError("Account changed. Refresh cancelled.");
        tokenStore.set(data.access, data.refresh ?? refresh);
        return data.access;
    }
    catch (error) {
        if ([400, 401, 403].includes(error.response?.status)) {
            expireSession(version);
            return null;
        }
        // A network outage is not proof that the refresh token is invalid.
        throw error;
    }
}
api.interceptors.response.use((response) => {
    if (response.config._sessionVersion !== tokenStore.version) throw new axios.CanceledError("Account changed. Response ignored.");
    return response;
}, async (error) => {
    const original = error.config;
    if (original && original._sessionVersion !== tokenStore.version) throw new axios.CanceledError("Account changed. Request cancelled.");
    const url = original?.url ?? "";
    const isAuthUrl = url.includes("/auth/login") || url.includes("/auth/refresh");
    if (error.response?.status === 401 && original?._retry && !isAuthUrl) expireSession(original._sessionVersion);
    if (error.response?.status === 401 && original && !original._retry && !isAuthUrl) {
        original._retry = true;
        const version = original._sessionVersion;
        if (!refreshing || refreshing.version !== version) {
            const pending = { version };
            pending.promise = refreshAccess(version).finally(() => {
                if (refreshing === pending) refreshing = null;
            });
            refreshing = pending;
        }
        const access = await refreshing.promise;
        if (version !== tokenStore.version) throw new axios.CanceledError("Account changed. Retry cancelled.");
        if (access) {
            original.headers.Authorization = `Bearer ${access}`;
            return api(original);
        }
    }
    return Promise.reject(error);
});
// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------
export async function loginRequest(username, password) {
    const { data } = await axios.post(`${BASE_URL}/auth/login`, { username, password }, { timeout: 15000 });
    return data;
}
export async function meRequest() {
    const { data } = await api.get("/auth/me");
    return data;
}
export async function listExpenses(params) {
    const query = {};
    if (params.page)
        query.page = params.page;
    if (params.search)
        query.search = params.search;
    if (params.status)
        query.status = params.status;
    const { data } = await api.get("/expenses/", { params: query });
    return data;
}
export async function getExpense(id) {
    const { data } = await api.get(`/expenses/${id}/`);
    return data;
}
export async function createExpense(payload) {
    const { data } = await api.post("/expenses/", payload);
    return data;
}
export async function updateExpense(id, payload) {
    const { data } = await api.patch(`/expenses/${id}/`, payload);
    return data;
}
export async function closeExpense(id) {
    const { data } = await api.post(`/expenses/${id}/close/`);
    return data;
}
export async function submitExpense(id) {
    const { data } = await api.post(`/expenses/${id}/submit/`);
    return data;
}
export async function approveExpense(id) {
    const { data } = await api.post(`/expenses/${id}/approve/`);
    return data;
}
export async function returnExpense(id, comment) {
    const { data } = await api.post(`/expenses/${id}/return/`, { comment });
    return data;
}
export async function rejectExpense(id, comment) {
    const { data } = await api.post(`/expenses/${id}/reject/`, { comment });
    return data;
}
export async function listComments(id) {
    const { data } = await api.get(`/expenses/${id}/comments/`);
    return data;
}
export async function postComment(id, text) {
    const { data } = await api.post(`/expenses/${id}/comments/`, { text });
    return data;
}
export async function getHistory(id) {
    const { data } = await api.get(`/expenses/${id}/history/`);
    return data;
}
