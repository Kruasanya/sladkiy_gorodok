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
import LedgerPage from "./pages/LedgerPage";
import CatalogPage from "./pages/CatalogPage";
import CashFlowPage from "./pages/CashFlowPage";
import UsersPage from "./pages/UsersPage";

export default function App() {
  const [user, setUser] = useState<
    { username: string; is_staff: boolean; is_test_client: boolean } | null | "loading"
  >("loading");
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
        <Route path="/ledger/sales" element={<LedgerPage ledgerType="sales" />} />
        <Route path="/ledger/receipts" element={<LedgerPage ledgerType="receipts" />} />
        <Route path="/ledger/payments" element={<LedgerPage ledgerType="payments" />} />
        <Route path="/ledger/cashflow" element={<CashFlowPage />} />
        <Route path="/sales/timeline" element={<SalesTimelinePage />} />
        <Route path="/sales/products" element={<SalesProductsPage />} />
        <Route path="/sales/counterparties" element={<SalesCounterpartiesPage />} />
        <Route path="/sales-vs-payments" element={<SalesVsPaymentsPage />} />
        <Route
          path="/imports"
          element={user.is_test_client ? <Navigate to="/sales/timeline" replace /> : <ImportsPage />}
        />
        <Route
          path="/organizations"
          element={
            user.is_test_client ? <Navigate to="/sales/timeline" replace /> : <OrganizationsPage />
          }
        />
        <Route
          path="/catalog/products"
          element={user.is_test_client ? <Navigate to="/sales/timeline" replace /> : <CatalogPage />}
        />
        <Route
          path="/admin/users"
          element={
            user.is_staff && !user.is_test_client ? (
              <UsersPage />
            ) : (
              <Navigate to="/sales/timeline" replace />
            )
          }
        />
        <Route path="*" element={<Navigate to="/sales/timeline" replace />} />
      </Routes>
    </Layout>
  );
}
