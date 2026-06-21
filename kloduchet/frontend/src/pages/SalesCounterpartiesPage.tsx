import { useEffect, useState } from "react";
import { api, type CounterpartyRow, type Organization } from "../api";

const LEVELS = [
  { value: "legal_entity", label: "Юридическое лицо" },
  { value: "brand", label: "Торговая марка" },
  { value: "counterparty_raw", label: "Исходное представление" },
  { value: "contract_number", label: "Договор" },
];

export default function SalesCounterpartiesPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [level, setLevel] = useState("legal_entity");
  const [rows, setRows] = useState<CounterpartyRow[]>([]);
  const [amountTotal, setAmountTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<Organization[]>("/organizations/").then((res) => setOrganizations(res.data));
  }, []);

  function load() {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("level", level);
    selectedOrgs.forEach((id) => params.append("organization", id));
    api
      .get<{ rows: CounterpartyRow[]; amount_total: number }>(
        `/analytics/sales/counterparties?${params.toString()}`
      )
      .then((res) => {
        setRows(res.data.rows);
        setAmountTotal(res.data.amount_total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [level, selectedOrgs]);

  function exportXlsx() {
    const params = new URLSearchParams();
    params.set("level", level);
    selectedOrgs.forEach((id) => params.append("organization", id));
    window.open(`/api/exports/sales/counterparties?${params.toString()}`, "_blank");
  }

  return (
    <div>
      <h1>Продажи по контрагентам</h1>

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
          Уровень
          <select value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((l) => (
              <option key={l.value} value={l.value}>
                {l.label}
              </option>
            ))}
          </select>
        </label>
        <button onClick={exportXlsx}>Экспорт в Excel</button>
      </div>

      {loading ? (
        <p>Загрузка…</p>
      ) : rows.length === 0 ? (
        <p className="empty-state">
          Данных нет. Загрузите файл продаж на странице «Загрузка данных» или измените фильтры.
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Контрагент</th>
              <th>Сумма продаж</th>
              <th>Возвраты и корректировки</th>
              <th>Чистая сумма</th>
              <th>Количество</th>
              <th>Документов</th>
              <th>Доля в продажах</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{row.key ?? "—"}</td>
                <td>{formatMoney(row.gross_sales_total)}</td>
                <td>{formatMoney(row.returns_total)}</td>
                <td>{formatMoney(row.amount_total)}</td>
                <td>{Number(row.quantity_total).toLocaleString("ru-RU")}</td>
                <td>{row.documents_count}</td>
                <td>{row.share_of_total != null ? formatPercent(row.share_of_total) : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td>Итого</td>
              <td colSpan={2}></td>
              <td>{formatMoney(amountTotal)}</td>
              <td colSpan={3}></td>
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
