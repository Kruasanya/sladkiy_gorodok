import { useEffect, useState } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { api } from "./api";
import Layout from "./Layout";
import LoginPage from "./pages/LoginPage";
import OrganizationsPage from "./pages/OrganizationsPage";
import ImportsPage from "./pages/ImportsPage";
import SalesTimelinePage from "./pages/SalesTimelinePage";
import SalesProductsPage from "./pages/SalesProductsPage";
import SalesCounterpartiesPage from "./pages/SalesCounterpartiesPage";
import SalesVsPaymentsPage from "./pages/SalesVsPaymentsPage";

export default function App() {
  const [user, setUser] = useState<{ username: string } | null | "loading">("loading");
  const navigate = useNavigate();

  useEffect(() => {
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => setUser(null));
  }, []);

  if (user === "loading") {
    return <div className="page-loading">Загрузка…</div>;
  }

  if (!user) {
    return (
      <LoginPage
        onLoggedIn={(u) => {
          setUser(u);
          navigate("/");
        }}
      />
    );
  }

  return (
    <Layout
      user={user}
      onLogout={async () => {
        await api.post("/auth/logout");
        setUser(null);
      }}
    >
      <Routes>
        <Route path="/" element={<Navigate to="/sales/timeline" replace />} />
        <Route path="/sales/timeline" element={<SalesTimelinePage />} />
        <Route path="/sales/products" element={<SalesProductsPage />} />
        <Route path="/sales/counterparties" element={<SalesCounterpartiesPage />} />
        <Route path="/sales-vs-payments" element={<SalesVsPaymentsPage />} />
        <Route path="/imports" element={<ImportsPage />} />
        <Route path="/organizations" element={<OrganizationsPage />} />
        <Route path="*" element={<Navigate to="/sales/timeline" replace />} />
      </Routes>
    </Layout>
  );
}
