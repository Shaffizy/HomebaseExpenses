import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./auth/ProtectedRoute";
import { Layout } from "./components/Layout";
import { AdminPage } from "./pages/AdminPage";
import { ExpenseDetailPage } from "./pages/ExpenseDetailPage";
import { ExpenseFormPage } from "./pages/ExpenseFormPage";
import { ExpensesPage } from "./pages/ExpensesPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { SettingsPage } from "./pages/SettingsPage";
export default function App() {
    return (<Routes>
      <Route path="/login" element={<LoginPage />}/>
      <Route element={<ProtectedRoute>
            <Layout />
          </ProtectedRoute>}>
        <Route path="/" element={<DashboardPage />}/>
        <Route path="/expenses" element={<ExpensesPage />}/>
        <Route path="/expenses/new" element={<ExpenseFormPage />}/>
        <Route path="/expenses/:id" element={<ExpenseDetailPage />}/>
        <Route path="/admin" element={<AdminPage />}/>
        <Route path="/settings" element={<SettingsPage />}/>
        <Route path="/settings/email-callback" element={<Navigate to="/settings?section=email" replace />}/>
      </Route>
      <Route path="*" element={<Navigate to="/" replace/>}/>
    </Routes>);
}
