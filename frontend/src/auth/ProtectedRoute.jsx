import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";
import { ErrorState, Spinner } from "../components/ui";
export function ProtectedRoute({ children }) {
    const { user, loading, authError, retryAuth, logout } = useAuth();
    const location = useLocation();
    if (loading) {
        return (<div className="flex min-h-screen items-center justify-center">
        <Spinner className="h-8 w-8"/>
      </div>);
    }
    if (authError) {
        return <main className="mx-auto max-w-lg px-6 py-16"><ErrorState message={authError} onRetry={retryAuth}/><button type="button" onClick={logout} className="mt-5 text-sm underline">Return to sign in</button></main>;
    }
    if (!user) {
        return <Navigate to="/login" state={{ from: location }} replace/>;
    }
    return <>{children}</>;
}
