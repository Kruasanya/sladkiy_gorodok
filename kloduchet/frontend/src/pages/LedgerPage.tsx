import { useEffect, useState } from "react";
import { api, type Organization } from "../api";

type LedgerType = "sales" | "receipts" | "payments";

interface LedgerResponse {
  rows: Record<string, unknown>[];
  count: number;
  page: number;
  page_size: number;
  groupable_fields: string[];
  amount_fields: string[];
  aggregation: {
    agg: string;
    agg_field: string;
    group_by: string | null;
    period: string | null;
    results: { group: string | number | null; value: number }[];
  };
}

const TITLES: Record<LedgerType, string> = {
  sales: "Продажи",
  receipts: "Приходы",
  payments: "Оплаты",
};

const COLUMN_LABELS: Record<string, string> = {
  id: "№",
  "organization__name": "Организация",
  sale_date: "Дата",
  operation_date: "Дата",
  payment_date: "Дата",
  counterparty_raw: "Контрагент",
  counterparty_name: "Контрагент",
  legal_entity: "Юр. лицо",
  nomenclature: "Номенклатура",
  sales_doc_type: "Тип документа",
  sales_doc_number: "Документ",
  payment_doc_number: "Документ",
  document_number: "Документ",
  payment_purpose: "Назначение платежа",
  quantity: "Количество",
  amount: "Сумма",
};

const AGG_LABELS: Record<string, string> = {
  sum: "Сумма",
  count: "Количество",
  avg: "Среднее",
  min: "Минимум",
  max: "Максимум",
};

const GROUP_LABELS: Record<string, string> = {
  organization: "Организация",
  legal_entity: "Юр. лицо",
  counterparty: "Контрагент",
  nomenclature: "Номенклатура",
  doc_type: "Тип документа",
};

export default function LedgerPage({ ledgerType }: { ledgerType: LedgerType }) {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [counterparty, setCounterparty] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize] = useState(50);

  const [agg, setAgg] = useState("sum");
  const [aggField, setAggField] = useState("amount");
  const [groupBy, setGroupBy] = useState("");
  const [period, setPeriod] = useState("");

  const [data, setData] = useState<LedgerResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.get<Organization[]>("/organizations/?is_active=true").then((res) => setOrganizations(res.data));
  }, []);

  useEffect(() => {
    setPage(1);
  }, [ledgerType, selectedOrgs, dateFrom, dateTo, counterparty]);

  useEffect(() => {
    setLoading(true);
    const params = new URLSearchParams();
    selectedOrgs.forEach((id) => params.append("organization", id));
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    if (counterparty) params.set("counterparty", counterparty);
    params.set("page", String(page));
    params.set("page_size", String(pageSize));
    params.set("agg", agg);
    params.set("agg_field", aggField);
    if (groupBy) params.set("group_by", groupBy);
    if (period) params.set("period", period);

    api
      .get<LedgerResponse>(`/analytics/ledger/${ledgerType}?${params.toString()}`)
      .then((res) => setData(res.data))
      .finally(() => setLoading(false));
  }, [ledgerType, selectedOrgs, dateFrom, dateTo, counterparty, page, pageSize, agg, aggField, groupBy, period]);

  const columns = data && data.rows[0] ? Object.keys(data.rows[0]) : [];
  const totalPages = data ? Math.max(Math.ceil(data.count / data.page_size), 1) : 1;

  return (
    <div>
      <h1>Бухгалтерия — {TITLES[ledgerType]}</h1>

      <div className="filters-bar">
        <label>
          Организации
          <select
            multiple
            value={selectedOrgs}
            onChange={(e) => setSelectedOrgs(Array.from(e.target.selectedOptions, (o) => o.value))}
          >
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          С
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          По
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
        <label>
          Контрагент
          <input
            type="text"
            value={counterparty}
            onChange={(e) => setCounterparty(e.target.value)}
            placeholder="Поиск по контрагенту"
          />
        </label>
      </div>

      <div className="filters-bar">
        <label>
          Агрегирующая функция
          <select value={agg} onChange={(e) => setAgg(e.target.value)}>
            {Object.entries(AGG_LABELS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Поле
          <select value={aggField} onChange={(e) => setAggField(e.target.value)}>
            {(data?.amount_fields ?? ["amount"]).map((field) => (
              <option key={field} value={field}>
                {COLUMN_LABELS[field] ?? field}
              </option>
            ))}
          </select>
        </label>
        <label>
          Группировка
          <select
            value={groupBy}
            onChange={(e) => {
              setGroupBy(e.target.value);
              if (e.target.value) setPeriod("");
            }}
          >
            <option value="">Без группировки</option>
            {(data?.groupable_fields ?? []).map((field) => (
              <option key={field} value={field}>
                {GROUP_LABELS[field] ?? field}
              </option>
            ))}
          </select>
        </label>
        <label>
          Период
          <select
            value={period}
            onChange={(e) => {
              setPeriod(e.target.value);
              if (e.target.value) setGroupBy("");
            }}
          >
            <option value="">Без периода</option>
            <option value="day">По дням</option>
            <option value="week">По неделям</option>
            <option value="month">По месяцам</option>
          </select>
        </label>
      </div>

      {data && (
        <table className="data-table">
          <thead>
            <tr>
              <th>Группа</th>
              <th>{AGG_LABELS[data.aggregation.agg]} ({COLUMN_LABELS[data.aggregation.agg_field] ?? data.aggregation.agg_field})</th>
            </tr>
          </thead>
          <tbody>
            {data.aggregation.results.map((row, i) => (
              <tr key={i}>
                <td>{row.group ?? "Итого"}</td>
                <td>{formatNumber(row.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Строки ({data?.count ?? 0})</h2>

      {loading ? (
        <p>Загрузка…</p>
      ) : !data || data.rows.length === 0 ? (
        <p className="empty-state">Данных нет. Измените фильтры или загрузите файл.</p>
      ) : (
        <>
          <table className="data-table">
            <thead>
              <tr>
                {columns.map((col) => (
                  <th key={col}>{COLUMN_LABELS[col] ?? col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.rows.map((row, i) => (
                <tr key={i}>
                  {columns.map((col) => (
                    <td key={col}>{formatCell(row[col])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
          <div className="filters-bar">
            <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              ← Назад
            </button>
            <span>
              Страница {page} из {totalPages}
            </span>
            <button disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Вперёд →
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "—";
  if (typeof value === "number") return formatNumber(value);
  return String(value);
}

function formatNumber(value: number) {
  return Number(value).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
