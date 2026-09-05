import { useEffect } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getCurrentAccount, roleRoutes } from "./auth";
import { PageLoading } from "./components";
import { AdminPage } from "./pages/AdminPage";
import { LoginPage, RegisterPage } from "./pages/AuthPages";
import { CounterPage } from "./pages/CounterPage";
import { CustomerPage } from "./pages/CustomerPage";
import { HistoryPage } from "./pages/HistoryPage";
import { HomePage } from "./pages/HomePage";
import { ManagerPage } from "./pages/ManagerPage";
import { ReceptionPage } from "./pages/ReceptionPage";
import { RecoveryPage } from "./pages/RecoveryPage";

function WorkspaceRouter() {
  const account = useQuery({ queryKey: ["account"], queryFn: getCurrentAccount, retry: false });
  if (account.isLoading) return <PageLoading label="Opening Smart Q" />;
  if (!account.data) return <Navigate to="/login/" replace />;
  return <Navigate to={roleRoutes[account.data.role]} replace />;
}

function SessionExpiryListener() {
  const navigate = useNavigate();
  useEffect(() => {
    const handler = () => {
      const current = window.location.pathname;
      const customerPath = current === "/app/customer/" || current === "/app/recovery/";
      const loginPath = customerPath ? "/login/" : "/staff-login/";
      const next = encodeURIComponent(current);
      navigate(`${loginPath}?expired=1&next=${next}`, { replace: true });
    };
    window.addEventListener("smartq:session-expired", handler);
    return () => window.removeEventListener("smartq:session-expired", handler);
  }, [navigate]);
  return null;
}

export default function App() {
  return <>
    <SessionExpiryListener />
    <Routes>
      <Route path="/" element={<HomePage />} />
      <Route path="/login/" element={<LoginPage />} />
      <Route path="/staff-login/" element={<LoginPage staff />} />
      <Route path="/register/" element={<RegisterPage />} />
      <Route path="/app/" element={<WorkspaceRouter />} />
      <Route path="/app/customer/" element={<CustomerPage />} />
      <Route path="/app/reception/" element={<ReceptionPage />} />
      <Route path="/app/counter/" element={<CounterPage />} />
      <Route path="/app/manager/" element={<ManagerPage />} />
      <Route path="/app/admin/" element={<AdminPage />} />
      <Route path="/app/history/" element={<HistoryPage />} />
      <Route path="/app/recovery/" element={<RecoveryPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  </>;
}
