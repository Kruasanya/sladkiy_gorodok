import type { ReactNode } from "react";
import { NavLink } from "react-router-dom";

export default function Layout({
  user,
  onLogout,
  children,
}: {
  user: { username: string };
  onLogout: () => void;
  children: ReactNode;
}) {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="brand">КлодУчет</div>
        <nav>
          <NavLink to="/sales/timeline">Продажи по времени</NavLink>
          <NavLink to="/sales/products">Продажи по товарам</NavLink>
          <NavLink to="/sales/counterparties">Продажи по контрагентам</NavLink>
          <NavLink to="/sales-vs-payments">Продажи и оплаты</NavLink>
          <NavLink to="/imports">Загрузка данных</NavLink>
          <NavLink to="/organizations">Организации</NavLink>
        </nav>
        <div className="user-box">
          <span>{user.username}</span>
          <button onClick={onLogout}>Выйти</button>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
}
