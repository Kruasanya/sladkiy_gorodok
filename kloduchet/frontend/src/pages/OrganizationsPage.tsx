import { useEffect, useState, type FormEvent } from "react";
import { api, type Organization } from "../api";

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [name, setName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [inn, setInn] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function load() {
    setLoading(true);
    api
      .get<Organization[]>("/organizations/")
      .then((res) => setOrganizations(res.data))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/organizations/", { name, legal_name: legalName, inn });
      setName("");
      setLegalName("");
      setInn("");
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось создать организацию.");
    }
  }

  return (
    <div>
      <h1>Организации</h1>

      <form className="inline-form" onSubmit={handleSubmit}>
        <input
          placeholder="Название организации"
          value={name}
          onChange={(e) => setName(e.target.value)}
          required
        />
        <input
          placeholder="Юридическое название"
          value={legalName}
          onChange={(e) => setLegalName(e.target.value)}
        />
        <input placeholder="ИНН" value={inn} onChange={(e) => setInn(e.target.value)} />
        <button type="submit">Создать организацию</button>
      </form>
      {error && <div className="error-box">{error}</div>}

      {loading ? (
        <p>Загрузка…</p>
      ) : organizations.length === 0 ? (
        <p className="empty-state">
          Организаций пока нет. Создайте минимум две, чтобы начать загрузку данных.
        </p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Название</th>
              <th>Юр. лицо</th>
              <th>ИНН</th>
              <th>Статус</th>
            </tr>
          </thead>
          <tbody>
            {organizations.map((org) => (
              <tr key={org.id}>
                <td>{org.name}</td>
                <td>{org.legal_name || "—"}</td>
                <td>{org.inn || "—"}</td>
                <td>{org.is_active ? "Действует" : "Архивная"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
