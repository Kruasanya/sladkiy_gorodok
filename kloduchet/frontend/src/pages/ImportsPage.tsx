import { useEffect, useState, type FormEvent } from "react";
import { api, type ImportBatch, type Organization } from "../api";

const STATUS_LABELS: Record<string, string> = {
  uploaded: "Загружен",
  queued: "В очереди",
  processing: "Обрабатывается",
  validated: "Проверен",
  completed: "Завершен",
  failed: "Ошибка",
  cancelled: "Отменен",
};

export default function ImportsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [batches, setBatches] = useState<ImportBatch[]>([]);
  const [organization, setOrganization] = useState("");
  const [dataType, setDataType] = useState("sales");
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function loadBatches() {
    api.get<ImportBatch[]>("/imports/").then((res) => setBatches(res.data));
  }

  useEffect(() => {
    api.get<Organization[]>("/organizations/?is_active=true").then((res) => {
      setOrganizations(res.data);
      if (res.data.length > 0) setOrganization(res.data[0].id);
    });
    loadBatches();
  }, []);

  // Раздел 18 tech_spec.md: при асинхронной обработке (Celery) опрашиваем
  // статус не чаще раза в 2 секунды, пока есть незавершенные пакеты.
  useEffect(() => {
    const hasPending = batches.some((b) =>
      ["uploaded", "queued", "processing", "validated"].includes(b.status)
    );
    if (!hasPending) return;
    const timer = setInterval(loadBatches, 2000);
    return () => clearInterval(timer);
  }, [batches]);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!file || !organization) return;
    setError(null);
    setUploading(true);

    const formData = new FormData();
    formData.append("organization", organization);
    formData.append("data_type", dataType);
    formData.append("file", file);

    try {
      await api.post("/imports/", formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });
      setFile(null);
      loadBatches();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось загрузить файл.");
    } finally {
      setUploading(false);
    }
  }

  async function handleCancel(id: string) {
    await api.post(`/imports/${id}/cancel/`);
    loadBatches();
  }

  return (
    <div>
      <h1>Загрузка данных</h1>

      <form className="upload-form" onSubmit={handleSubmit}>
        <label>
          Организация
          <select value={organization} onChange={(e) => setOrganization(e.target.value)} required>
            {organizations.map((org) => (
              <option key={org.id} value={org.id}>
                {org.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Тип данных
          <select value={dataType} onChange={(e) => setDataType(e.target.value)}>
            <option value="sales">Продажи по контрагентам (.xls)</option>
            <option value="payments">Продажи по контрагентам по оплате (.xls)</option>
            <option value="bank">Банковские выписки (.xlsx)</option>
          </select>
        </label>
        <label>
          Файл ({dataType === "bank" ? ".xlsx" : ".xls"})
          <input
            type="file"
            accept={dataType === "bank" ? ".xlsx" : ".xls"}
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            required
          />
        </label>
        <button type="submit" disabled={uploading || organizations.length === 0}>
          {uploading ? "Загружаем и обрабатываем…" : "Загрузить и обработать"}
        </button>
      </form>
      {error && <div className="error-box">{error}</div>}
      {organizations.length === 0 && (
        <p className="empty-state">Сначала создайте организацию на странице «Организации».</p>
      )}

      <h2>Прошлые загрузки</h2>
      {batches.length === 0 ? (
        <p className="empty-state">Загрузок пока нет.</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Файл</th>
              <th>Организация</th>
              <th>Тип</th>
              <th>Статус</th>
              <th>Период</th>
              <th>Строк</th>
              <th>Сумма</th>
              <th>Предупреждения / ошибка</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {batches.map((batch) => (
              <tr key={batch.id}>
                <td>
                  <a href={`/api/imports/${batch.id}/file/`} target="_blank">
                    {batch.original_filename}
                  </a>
                </td>
                <td>{batch.organization_name}</td>
                <td>{batch.data_type}</td>
                <td>
                  <span className={`status-badge status-${batch.status}`}>
                    {STATUS_LABELS[batch.status] ?? batch.status}
                  </span>
                </td>
                <td>
                  {batch.period_start && batch.period_end
                    ? `${formatDate(batch.period_start)} – ${formatDate(batch.period_end)}`
                    : "—"}
                </td>
                <td>{batch.row_count}</td>
                <td>{batch.amount_total ? formatMoney(batch.amount_total) : "—"}</td>
                <td>
                  {batch.error_message && <div className="error-text">{batch.error_message}</div>}
                  {batch.warnings?.map((w, i) => (
                    <div key={i} className="warning-text">
                      {w}
                    </div>
                  ))}
                </td>
                <td>
                  {batch.status === "completed" && (
                    <button onClick={() => handleCancel(batch.id)}>Отменить</button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

function formatDate(value: string) {
  const [y, m, d] = value.split("-");
  return `${d}.${m}.${y}`;
}

function formatMoney(value: string) {
  return Number(value).toLocaleString("ru-RU", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}
