import { useEffect, useState, type FormEvent } from "react";
import { api, type Organization } from "../api";

export default function OrganizationsPage() {
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [name, setName] = useState("");
  const [legalName, setLegalName] = useState("");
  const [inn, setInn] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<Organization>>({});

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

  function startEdit(org: Organization) {
    setEditingId(org.id);
    setEditDraft({ name: org.name, legal_name: org.legal_name, inn: org.inn, kpp: org.kpp });
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft({});
  }

  async function saveEdit(id: string) {
    setError(null);
    try {
      await api.patch(`/organizations/${id}/`, editDraft);
      setEditingId(null);
      setEditDraft({});
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось сохранить изменения организации.");
    }
  }

  async function toggleActive(org: Organization) {
    setError(null);
    try {
      await api.post(`/organizations/${org.id}/${org.is_active ? "deactivate" : "activate"}/`);
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось изменить статус организации.");
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
              <th>КПП</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {organizations.map((org) =>
              editingId === org.id ? (
                <tr key={org.id}>
                  <td>
                    <input
                      value={editDraft.name ?? ""}
                      onChange={(e) => setEditDraft((d) => ({ ...d, name: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      value={editDraft.legal_name ?? ""}
                      onChange={(e) => setEditDraft((d) => ({ ...d, legal_name: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      value={editDraft.inn ?? ""}
                      onChange={(e) => setEditDraft((d) => ({ ...d, inn: e.target.value }))}
                    />
                  </td>
                  <td>
                    <input
                      value={editDraft.kpp ?? ""}
                      onChange={(e) => setEditDraft((d) => ({ ...d, kpp: e.target.value }))}
                    />
                  </td>
                  <td>{org.is_active ? "Действует" : "Архивная"}</td>
                  <td>
                    <button onClick={() => saveEdit(org.id)}>Сохранить</button>
                    <button onClick={cancelEdit}>Отмена</button>
                  </td>
                </tr>
              ) : (
                <tr key={org.id}>
                  <td>{org.name}</td>
                  <td>{org.legal_name || "—"}</td>
                  <td>{org.inn || "—"}</td>
                  <td>{org.kpp || "—"}</td>
                  <td>{org.is_active ? "Действует" : "Архивная"}</td>
                  <td>
                    <button onClick={() => startEdit(org)}>Изменить</button>
                    <button onClick={() => toggleActive(org)}>
                      {org.is_active ? "Удалить" : "Восстановить"}
                    </button>
                  </td>
                </tr>
              )
            )}
          </tbody>
        </table>
      )}
    </div>
  );
}
