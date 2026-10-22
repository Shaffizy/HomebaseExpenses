import { createContext, useCallback, useContext, useEffect, useMemo, useState, } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AUTH_LOGGED_OUT_EVENT, loginRequest, meRequest, tokenStore, errorMessage } from "../lib/api";
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
    const queryClient = useQueryClient();
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [authError, setAuthError] = useState(null);
    const [attempt, setAttempt] = useState(0);
    const retryAuth = useCallback(() => { setAuthError(null); setLoading(true); setAttempt((value) => value + 1); }, []);
    useEffect(() => {
        let cancelled = false;
        if (!tokenStore.access) {
            setLoading(false);
            return;
        }
        meRequest()
            .then((me) => {
            if (!cancelled)
                setUser(me);
        })
            .catch((error) => {
            if (cancelled) return;
            if ([400, 401, 403].includes(error.response?.status)) {
                tokenStore.clear();
                setUser(null);
            } else {
                setAuthError(errorMessage(error));
            }
        })
            .finally(() => {
            if (!cancelled)
                setLoading(false);
        });
        return () => {
            cancelled = true;
        };
    }, [attempt]);
    useEffect(() => {
        const onLoggedOut = () => { queryClient.clear(); setUser(null); setAuthError(null); };
        window.addEventListener(AUTH_LOGGED_OUT_EVENT, onLoggedOut);
        return () => window.removeEventListener(AUTH_LOGGED_OUT_EVENT, onLoggedOut);
    }, [queryClient]);
    const login = useCallback(async (username, password) => {
        const data = await loginRequest(username, password);
        tokenStore.set(data.access, data.refresh);
        setUser(data.user);
        setAuthError(null);
        return data.user;
    }, []);
    const logout = useCallback(() => {
        tokenStore.clear();
        queryClient.clear();
        setUser(null);
        setAuthError(null);
    }, [queryClient]);
    const value = useMemo(() => ({ user, loading, login, logout, authError, retryAuth }), [user, loading, login, logout, authError, retryAuth]);
    return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
export function useAuth() {
    const ctx = useContext(AuthContext);
    if (!ctx)
        throw new Error("useAuth must be used inside AuthProvider");
    return ctx;
}
