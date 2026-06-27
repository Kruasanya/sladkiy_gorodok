import type { ReactNode } from "react";
import { NavLink, useLocation } from "react-router-dom";

const SECTIONS = [
  {
    title: "Бухгалтерия",
    base: "/ledger",
    links: [
      { to: "/ledger/sales", label: "Продажи" },
      { to: "/ledger/receipts", label: "Приходы" },
      { to: "/ledger/payments", label: "Оплаты" },
    ],
  },
  {
    title: "Аналитика",
    base: "/sales",
    links: [
      { to: "/sales/timeline", label: "Продажи по времени" },
      { to: "/sales/products", label: "Продажи по товарам" },
      { to: "/sales/counterparties", label: "Продажи по контрагентам" },
      { to: "/sales-vs-payments", label: "Продажи и оплаты" },
    ],
  },
  {
    title: "Администрирование",
    base: "/admin",
    links: [
      { to: "/imports", label: "Загрузка данных" },
      { to: "/organizations", label: "Организации" },
      { to: "/catalog/products", label: "Справочники" },
    ],
  },
];

export default function Layout({
  user,
  onLogout,
  children,
}: {
  user: { username: string };
  onLogout: () => void;
  children: ReactNode;
}) {
  const location = useLocation();
  const activeSection =
    SECTIONS.find((section) => section.links.some((link) => location.pathname.startsWith(link.to))) ??
    SECTIONS[1];

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">КлодУчет</div>
        <nav className="section-nav">
          {SECTIONS.map((section) => (
            <NavLink
              key={section.title}
              to={section.links[0].to}
              className={() => (section === activeSection ? "section-link active" : "section-link")}
            >
              {section.title}
            </NavLink>
          ))}
        </nav>
        <div className="user-box">
          <span>{user.username}</span>
          <button onClick={onLogout}>Выйти</button>
        </div>
      </header>
      <nav className="sub-nav">
        {activeSection.links.map((link) => (
          <NavLink key={link.to} to={link.to}>
            {link.label}
          </NavLink>
        ))}
      </nav>
      <main className="app-main">{children}</main>
    </div>
  );
}
