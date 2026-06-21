import { useEffect, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Organization, type TimelineRow } from "../api";

export default function SalesTimelinePage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [group, setGroup] = useState("month");
  const [rows, setRows] = useState<TimelineRow[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<Organization[]>("/organizations/").then((res) => setOrganizations(res.data));
  }, []);

  function load() {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("group", group);
    selectedOrgs.forEach((id) => params.append("organization", id));
    api
      .get<{ rows: TimelineRow[] }>(`/analytics/sales/timeline?${params.toString()}`)
      .then((res) => setRows(res.data.rows))
      .finally(() => setLoading(false));
  }

  useEffect(load, [group, selectedOrgs]);

  const totalAmount = rows.reduce((sum, r) => sum + Number(r.amount_total), 0);
  const totalGross = rows.reduce((sum, r) => sum + Number(r.gross_sales_total), 0);
  const totalReturns = rows.reduce((sum, r) => sum + Number(r.returns_total), 0);
  const totalQuantity = rows.reduce((sum, r) => sum + Number(r.quantity_total), 0);

  function exportXlsx() {
    const params = new URLSearchParams();
    params.set("group", group);
    selectedOrgs.forEach((id) => params.append("organization", id));
    window.open(`/api/exports/sales/timeline?${params.toString()}`, "_blank");
  }

  return (
    <div>
      <h1>Продажи по времени</h1>

      <div className="filters-bar">
        <label>
          Организации
          <select
            multiple
            value={selectedOrgs}
            onChange={(e) =>
              setSelectedOrgs(Array.from(e.target.selectedOptions, (o) => o.value))
            }
          >
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
          <span className="hint">Ничего не выбрано = все организации</span>
        </label>
        <label>
          Группировка
          <select value={group} onChange={(e) => setGroup(e.target.value)}>
            <option value="day">День</option>
            <option value="week">Неделя</option>
            <option value="month">Месяц</option>
          </select>
        </label>
        <button onClick={exportXlsx}>Экспорт в Excel</button>
      </div>

      {loading ? (
        <p>Загрузка…</p>
      ) : rows.length === 0 ? (
        <p className="empty-state">
          За выбранный период и фильтры данных нет. Загрузите файл продаж на странице «Загрузка
          данных» или измените фильтры.
        </p>
      ) : (
        <>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={280}>
              <BarChart data={rows.map((r) => ({ ...r, label: formatPeriod(r.period) }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" />
                <YAxis />
                <Tooltip formatter={(v) => formatMoney(Number(v))} />
                <Bar dataKey="amount_total" fill="#3b6ea5" name="Сумма продаж" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th>Период</th>
                <th>Сумма продаж</th>
                <th>Возвраты и корректировки</th>
                <th>Чистая сумма</th>
                <th>Количество</th>
                <th>Документов</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={row.period}>
                  <td>{formatPeriod(row.period)}</td>
                  <td>{formatMoney(row.gross_sales_total)}</td>
                  <td>{formatMoney(row.returns_total)}</td>
                  <td>{formatMoney(row.amount_total)}</td>
                  <td>{Number(row.quantity_total).toLocaleString("ru-RU")}</td>
                  <td>{row.documents_count}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr>
                <td>Итого</td>
                <td>{formatMoney(totalGross)}</td>
                <td>{formatMoney(totalReturns)}</td>
                <td>{formatMoney(totalAmount)}</td>
                <td>{totalQuantity.toLocaleString("ru-RU")}</td>
                <td>—</td>
              </tr>
            </tfoot>
          </table>
        </>
      )}
    </div>
  );
}

function formatPeriod(value: string) {
  const [y, m, d] = value.split("-");
  return `${d}.${m}.${y}`;
}

function formatMoney(value: number) {
  return Number(value).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
