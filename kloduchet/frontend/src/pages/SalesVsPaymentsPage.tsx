import { useEffect, useState } from "react";
import { api, type Organization, type SalesVsPaymentsRow } from "../api";

export default function SalesVsPaymentsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [rows, setRows] = useState<SalesVsPaymentsRow[]>([]);
  const [disclaimer, setDisclaimer] = useState("");
  const [loading, setLoading] = useState(false);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    api.get<Organization[]>("/organizations/?is_active=true").then((res) => setOrganizations(res.data));
  }, []);

  function buildParams() {
    const params = new URLSearchParams();
    selectedOrgs.forEach((id) => params.append("organization", id));
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return params;
  }

  function load() {
    setLoading(true);
    api
      .get<{ rows: SalesVsPaymentsRow[]; disclaimer: string }>(
        `/analytics/sales-vs-payments?${buildParams().toString()}`
      )
      .then((res) => {
        setRows(res.data.rows);
        setDisclaimer(res.data.disclaimer);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [selectedOrgs, dateFrom, dateTo]);

  function exportXlsx() {
    window.open(`/api/exports/sales-vs-payments?${buildParams().toString()}`, "_blank");
  }

  const totalSales = rows.reduce((sum, r) => sum + Number(r.sales_total), 0);
  const totalPayments = rows.reduce((sum, r) => sum + Number(r.payments_total), 0);

  return (
    <div>
      <h1>Продажи и оплаты</h1>

      <div className="disclaimer-box">{disclaimer}</div>

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
          С даты
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          По дату
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <button onClick={exportXlsx}>Экспорт в Excel</button>
      </div>

      {loading ? (
        <p>Загрузка…</p>
      ) : rows.length === 0 ? (
        <p className="empty-state">
          Данных нет. Загрузите файлы продаж и оплат на странице «Загрузка данных».
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Юр. лицо</th>
              <th>Договор</th>
              <th>Продажи</th>
              <th>Оплаты</th>
              <th>Разница</th>
              <th>Доля оплат</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{row.legal_entity ?? "—"}</td>
                <td>{row.contract_number ?? "—"}</td>
                <td>{formatMoney(row.sales_total)}</td>
                <td>{formatMoney(row.payments_total)}</td>
                <td>{formatMoney(row.difference)}</td>
                <td>{row.payment_share != null ? formatPercent(row.payment_share) : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2}>Итого</td>
              <td>{formatMoney(totalSales)}</td>
              <td>{formatMoney(totalPayments)}</td>
              <td>{formatMoney(totalSales - totalPayments)}</td>
              <td></td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  );
}

function formatMoney(value: number) {
  return Number(value).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}
