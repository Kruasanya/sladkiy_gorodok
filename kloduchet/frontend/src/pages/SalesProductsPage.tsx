import { useEffect, useState } from "react";
import { api, type Organization, type ProductRow } from "../api";

export default function SalesProductsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [rows, setRows] = useState<ProductRow[]>([]);
  const [amountTotal, setAmountTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<Organization[]>("/organizations/").then((res) => setOrganizations(res.data));
  }, []);

  function load() {
    setLoading(true);
    const params = new URLSearchParams();
    selectedOrgs.forEach((id) => params.append("organization", id));
    api
      .get<{ rows: ProductRow[]; amount_total: number }>(
        `/analytics/sales/products?${params.toString()}`
      )
      .then((res) => {
        setRows(res.data.rows);
        setAmountTotal(res.data.amount_total);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, [selectedOrgs]);

  function exportXlsx() {
    const params = new URLSearchParams();
    selectedOrgs.forEach((id) => params.append("organization", id));
    window.open(`/api/exports/sales/products?${params.toString()}`, "_blank");
  }

  return (
    <div>
      <h1>Продажи по товарам</h1>

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
              <th>Номенклатура</th>
              <th>Сумма продаж</th>
              <th>Возвраты и корректировки</th>
              <th>Чистая сумма</th>
              <th>Количество</th>
              <th>Средняя цена</th>
              <th>Доля в продажах</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{row.nomenclature ?? "—"}</td>
                <td>{formatMoney(row.gross_sales_total)}</td>
                <td>{formatMoney(row.returns_total)}</td>
                <td>{formatMoney(row.amount_total)}</td>
                <td>{Number(row.quantity_total).toLocaleString("ru-RU")}</td>
                <td>{row.average_price != null ? formatMoney(row.average_price) : "—"}</td>
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
