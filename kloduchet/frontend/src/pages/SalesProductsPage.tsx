import { useEffect, useMemo, useState } from "react";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type Organization, type ProductRow } from "../api";
import { formatMoney, formatMoneyCompact } from "../utils/money";
import type { ProductReference } from "./CatalogPage";

interface TimeseriesPoint {
  period: string;
  value: number;
}
interface TimeseriesSeries {
  name: string;
  points: TimeseriesPoint[];
}
interface TimeseriesResponse {
  group: string;
  metric: string;
  value_type: string;
  dimension: string;
  series: TimeseriesSeries[];
}

const COLORS = ["#3461ff", "#ff7a45", "#36b37e", "#bf2600", "#6554c0", "#00b8d9", "#ffab00"];

const VALUE_TYPES = [
  { value: "net", label: "Чистая сумма" },
  { value: "gross", label: "Сумма продаж" },
  { value: "returns", label: "Возвраты и корректировки" },
];

export default function SalesProductsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [products, setProducts] = useState<ProductReference[]>([]);
  const [nomenclature, setNomenclature] = useState("");
  const [selectedDisplayNames, setSelectedDisplayNames] = useState<string[]>([]);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const [rows, setRows] = useState<ProductRow[]>([]);
  const [amountTotal, setAmountTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const [chartGroup, setChartGroup] = useState("month");
  const [chartMetric, setChartMetric] = useState("amount");
  const [chartValueType, setChartValueType] = useState("net");
  const [chartDimension, setChartDimension] = useState("display_name");
  const [timeseries, setTimeseries] = useState<TimeseriesResponse | null>(null);

  useEffect(() => {
    api.get<Organization[]>("/organizations/?is_active=true").then((res) => setOrganizations(res.data));
    api.get<ProductReference[]>("/catalog/products/").then((res) => setProducts(res.data));
  }, []);

  const displayNames = useMemo(
    () => Array.from(new Set(products.map((p) => p.display_name).filter(Boolean))).sort(),
    [products]
  );

  function buildParams() {
    const params = new URLSearchParams();
    selectedOrgs.forEach((id) => params.append("organization", id));
    if (nomenclature) params.set("nomenclature", nomenclature);
    selectedDisplayNames.forEach((name) => params.append("display_name", name));
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return params;
  }

  useEffect(() => {
    setLoading(true);
    api
      .get<{ rows: ProductRow[]; amount_total: number }>(
        `/analytics/sales/products?${buildParams().toString()}`
      )
      .then((res) => {
        setRows(res.data.rows);
        setAmountTotal(res.data.amount_total);
      })
      .finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgs, nomenclature, selectedDisplayNames, dateFrom, dateTo]);

  useEffect(() => {
    const params = buildParams();
    params.set("group", chartGroup);
    params.set("metric", chartMetric);
    params.set("value_type", chartValueType);
    params.set("dimension", chartDimension);
    api
      .get<TimeseriesResponse>(`/analytics/sales/products/timeseries?${params.toString()}`)
      .then((res) => setTimeseries(res.data));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedOrgs, nomenclature, selectedDisplayNames, dateFrom, dateTo, chartGroup, chartMetric, chartValueType, chartDimension]);

  const chartData = useMemo(() => {
    if (!timeseries) return [];
    const periods = timeseries.series[0]?.points.map((p) => p.period) ?? [];
    return periods.map((period, i) => {
      const point: Record<string, string | number> = { period };
      timeseries.series.forEach((s) => {
        point[s.name] = s.points[i]?.value ?? 0;
      });
      return point;
    });
  }, [timeseries]);

  function exportXlsx() {
    window.open(`/api/exports/sales/products?${buildParams().toString()}`, "_blank");
  }

  function formatChartValue(v: number) {
    return chartMetric === "amount" ? formatMoney(v) : Number(v).toLocaleString("ru-RU");
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
        <label>
          Номенклатура (1С)
          <input
            type="text"
            value={nomenclature}
            onChange={(e) => setNomenclature(e.target.value)}
            placeholder="Поиск по сырому названию"
          />
        </label>
        <label>
          Товары
          <select
            multiple
            value={selectedDisplayNames}
            onChange={(e) =>
              setSelectedDisplayNames(Array.from(e.target.selectedOptions, (o) => o.value))
            }
          >
            {displayNames.map((name) => (
              <option key={name} value={name as string}>
                {name}
              </option>
            ))}
          </select>
          <span className="hint">Ничего не выбрано = все товары</span>
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

      <h2>Динамика продаж</h2>
      <p className="hint">На графике показаны только активные товары из справочника.</p>
      <div className="filters-bar">
        <label>
          Период
          <select value={chartGroup} onChange={(e) => setChartGroup(e.target.value)}>
            <option value="day">По дням</option>
            <option value="week">По неделям</option>
            <option value="month">По месяцам</option>
          </select>
        </label>
        <label>
          Метрика
          <select value={chartMetric} onChange={(e) => setChartMetric(e.target.value)}>
            <option value="amount">Сумма</option>
            <option value="quantity">Количество</option>
          </select>
        </label>
        <label>
          Показатель
          <select value={chartValueType} onChange={(e) => setChartValueType(e.target.value)}>
            {VALUE_TYPES.map((vt) => (
              <option key={vt.value} value={vt.value}>
                {vt.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Разрез
          <select value={chartDimension} onChange={(e) => setChartDimension(e.target.value)}>
            <option value="display_name">По общему названию</option>
            <option value="nomenclature">По номенклатуре (1С)</option>
          </select>
        </label>
      </div>

      {timeseries && timeseries.series.length > 0 ? (
        <div className="chart-box">
          <ResponsiveContainer width="100%" height={360}>
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="period" />
              <YAxis
                width={90}
                tickFormatter={(v) =>
                  chartMetric === "amount" ? formatMoneyCompact(Number(v)) : Number(v).toLocaleString("ru-RU")
                }
              />
              <Tooltip formatter={(value) => formatChartValue(Number(value))} />
              <Legend />
              {timeseries.series.map((s, i) => (
                <Line
                  key={s.name}
                  type="monotone"
                  dataKey={s.name}
                  stroke={COLORS[i % COLORS.length]}
                  dot={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <p className="empty-state">Нет данных для графика.</p>
      )}

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
              <th>Общее название</th>
              <th>Сумма продаж</th>
              <th>Возвраты и корректировки</th>
              <th>Чистая сумма</th>
              <th>Количество продаж</th>
              <th>Количество возвратов</th>
              <th>Средняя цена</th>
              <th>Доля в продажах</th>
              <th>Доля возвратов</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => (
              <tr key={i}>
                <td>{row.nomenclature ?? "—"}</td>
                <td>{row.display_name ?? "—"}</td>
                <td>{formatMoney(row.gross_sales_total)}</td>
                <td>{formatMoney(row.returns_total)}</td>
                <td>{formatMoney(row.amount_total)}</td>
                <td>{Number(row.gross_quantity_total).toLocaleString("ru-RU")}</td>
                <td>{Number(row.returns_quantity_total).toLocaleString("ru-RU")}</td>
                <td>{row.average_price != null ? formatMoney(row.average_price) : "—"}</td>
                <td>{row.share_of_total != null ? formatPercent(row.share_of_total) : "—"}</td>
                <td>{row.returns_share != null ? formatPercent(row.returns_share) : "—"}</td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2}>Итого</td>
              <td colSpan={2}></td>
              <td>{formatMoney(amountTotal)}</td>
              <td colSpan={5}></td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  );
}

function formatPercent(value: number) {
  return `${(value * 100).toFixed(1)}%`;
}
