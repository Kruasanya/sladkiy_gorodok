import { useEffect, useMemo, useState } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type CashFlowResponse, type Organization } from "../api";
import { formatMoney, formatMoneyCompact } from "../utils/money";

const HORIZON_OPTIONS = [7, 14, 30, 60, 90];

interface ChartPoint {
  isoDate: string;
  date: string;
  inflow: number | null;
  outflow: number | null;
  net: number | null;
  forecast_inflow: number | null;
  forecast_outflow: number | null;
  forecast_net: number | null;
}

export default function CashFlowPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [selectedOrgs, setSelectedOrgs] = useState<string[]>([]);
  const [horizonDays, setHorizonDays] = useState(30);
  const [data, setData] = useState<CashFlowResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  useEffect(() => {
    api.get<Organization[]>("/organizations/?is_active=true").then((res) => setOrganizations(res.data));
  }, []);

  useEffect(() => {
    setLoading(true);
    setError(null);
    const params = new URLSearchParams();
    selectedOrgs.forEach((id) => params.append("organization", id));
    params.set("horizon_days", String(horizonDays));
    api
      .get<CashFlowResponse>(`/analytics/cashflow?${params.toString()}`)
      .then((res) => setData(res.data))
      .catch((err) => setError(err?.response?.data?.detail ?? "Не удалось построить прогноз Cash Flow."))
      .finally(() => setLoading(false));
  }, [selectedOrgs, horizonDays]);

  const allPoints: ChartPoint[] = useMemo(() => {
    if (!data) return [];
    const actualPoints: ChartPoint[] = data.actual.map((row) => ({
      isoDate: row.date,
      date: formatPeriod(row.date),
      inflow: row.inflow,
      outflow: -row.outflow,
      net: row.net_cash_flow,
      forecast_inflow: null,
      forecast_outflow: null,
      forecast_net: null,
    }));
    const forecastPoints: ChartPoint[] = data.forecast.map((row) => ({
      isoDate: row.date,
      date: formatPeriod(row.date),
      inflow: null,
      outflow: null,
      net: null,
      forecast_inflow: row.predicted_inflow,
      forecast_outflow: -row.predicted_outflow,
      forecast_net: row.predicted_net_cash_flow,
    }));
    return [...actualPoints, ...forecastPoints];
  }, [data]);

  const chartData = useMemo(
    () =>
      allPoints.filter((p) => (!dateFrom || p.isoDate >= dateFrom) && (!dateTo || p.isoDate <= dateTo)),
    [allPoints, dateFrom, dateTo]
  );

  const lastActualLabel = data?.actual.length ? formatPeriod(data.actual[data.actual.length - 1].date) : null;

  const stats = useMemo(() => {
    const actualInRange = (data?.actual ?? []).filter(
      (r) => (!dateFrom || r.date >= dateFrom) && (!dateTo || r.date <= dateTo)
    );
    const forecastInRange = (data?.forecast ?? []).filter(
      (r) => (!dateFrom || r.date >= dateFrom) && (!dateTo || r.date <= dateTo)
    );
    return {
      actualInflow: actualInRange.reduce((s, r) => s + r.inflow, 0),
      actualOutflow: actualInRange.reduce((s, r) => s + r.outflow, 0),
      forecastInflow: forecastInRange.reduce((s, r) => s + r.predicted_inflow, 0),
      forecastOutflow: forecastInRange.reduce((s, r) => s + r.predicted_outflow, 0),
    };
  }, [data, dateFrom, dateTo]);

  return (
    <div>
      <h1>Cash Flow</h1>
      <p className="hint">
        Фактические поступления и списания по банку, а также прогноз модели Cash Flow на выбранное
        количество дней вперед.
      </p>

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
          <span className="hint">Ничего не выбрано = все организации</span>
        </label>
        <label>
          Горизонт прогноза
          <select value={horizonDays} onChange={(e) => setHorizonDays(Number(e.target.value))}>
            {HORIZON_OPTIONS.map((d) => (
              <option key={d} value={d}>
                {d} дней
              </option>
            ))}
          </select>
        </label>
        <label>
          С даты
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </label>
        <label>
          По дату
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </label>
      </div>

      {error && <div className="error-box">{error}</div>}

      {loading ? (
        <p>Загрузка…</p>
      ) : chartData.length === 0 ? (
        <p className="empty-state">
          Данных нет. Загрузите банковскую выписку на странице «Загрузка данных» или измените фильтры.
        </p>
      ) : (
        <>
          <div className="chart-box">
            <ResponsiveContainer width="100%" height={400}>
              <ComposedChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis tickFormatter={(v) => formatMoneyCompact(Number(v))} width={90} />
                <Tooltip formatter={(v) => formatMoney(Number(v))} />
                <Legend />
                {lastActualLabel && (
                  <ReferenceLine x={lastActualLabel} stroke="#888" strokeDasharray="4 4" label="Прогноз" />
                )}
                <Bar dataKey="inflow" fill="#3b6ea5" name="Поступления (факт)" />
                <Bar dataKey="outflow" fill="#c0392b" name="Списания (факт)" />
                <Bar dataKey="forecast_inflow" fill="#9fc1e0" name="Поступления (прогноз)" />
                <Bar dataKey="forecast_outflow" fill="#e6a39a" name="Списания (прогноз)" />
                <Line
                  type="monotone"
                  dataKey="net"
                  stroke="#1f2d3d"
                  strokeWidth={2}
                  dot={false}
                  name="Чистый поток (факт)"
                />
                <Line
                  type="monotone"
                  dataKey="forecast_net"
                  stroke="#1f2d3d"
                  strokeWidth={2}
                  strokeDasharray="5 4"
                  dot={false}
                  name="Чистый поток (прогноз)"
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          <table className="data-table">
            <thead>
              <tr>
                <th></th>
                <th>Поступления</th>
                <th>Списания</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>Факт за период</td>
                <td>{formatMoney(stats.actualInflow)}</td>
                <td>{formatMoney(stats.actualOutflow)}</td>
              </tr>
              <tr>
                <td>Прогноз за период</td>
                <td>{formatMoney(stats.forecastInflow)}</td>
                <td>{formatMoney(stats.forecastOutflow)}</td>
              </tr>
            </tbody>
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
