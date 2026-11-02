import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { AUTH_LOGGED_OUT_EVENT, loginRequest, meRequest, tokenStore, errorMessage } from "../lib/api";
const AuthContext = createContext(null);
export function AuthProvider({ children }) {
    const queryClient = useQueryClient();
    const authGeneration = useRef(0);
    const [user, setUser] = useState(null);
    const [loading, setLoading] = useState(true);
    const [authError, setAuthError] = useState(null);
    const [attempt, setAttempt] = useState(0);
    const retryAuth = useCallback(() => { setAuthError(null); setLoading(true); setAttempt((value) => value + 1); }, []);
    useEffect(() => {
        let cancelled = false;
        const generation = authGeneration.current;
        if (!tokenStore.access) {
            setLoading(false);
            return;
        }
        meRequest()
            .then((me) => {
            if (!cancelled && generation === authGeneration.current)
                setUser(me);
        })
            .catch((error) => {
            if (cancelled || generation !== authGeneration.current) return;
            if ([400, 401, 403].includes(error.response?.status)) {
                tokenStore.clear();
                setUser(null);
            } else {
                setAuthError(errorMessage(error));
            }
        })
            .finally(() => {
            if (!cancelled && generation === authGeneration.current)
                setLoading(false);
        });
        return () => {
            cancelled = true;
        };
    }, [attempt]);
    useEffect(() => {
        const onLoggedOut = () => { authGeneration.current++; queryClient.clear(); setUser(null); setAuthError(null); setLoading(false); };
        window.addEventListener(AUTH_LOGGED_OUT_EVENT, onLoggedOut);
        return () => window.removeEventListener(AUTH_LOGGED_OUT_EVENT, onLoggedOut);
    }, [queryClient]);
    const login = useCallback(async (username, password) => {
        const generation = ++authGeneration.current;
        const data = await loginRequest(username, password);
        if (generation !== authGeneration.current) throw new Error("Sign-in was cancelled.");
        await queryClient.cancelQueries();
        if (generation !== authGeneration.current) throw new Error("Sign-in was cancelled.");
        tokenStore.startSession(data.access, data.refresh);
        queryClient.clear();
        setUser(data.user);
        setLoading(false);
        setAuthError(null);
        return data.user;
    }, [queryClient]);
    const logout = useCallback(() => {
        authGeneration.current++;
        tokenStore.clear();
        queryClient.clear();
        setUser(null);
        setAuthError(null);
        setLoading(false);
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
