import { useEffect, useState, type FormEvent } from "react";
import { api, type AppUser, type Organization } from "../api";

export default function UsersPage() {
  const [users, setUsers] = useState<AppUser[]>([]);
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [isStaff, setIsStaff] = useState(false);
  const [isTestClient, setIsTestClient] = useState(false);
  const [organizationId, setOrganizationId] = useState("");

  const [editingId, setEditingId] = useState<number | null>(null);
  const [editDraft, setEditDraft] = useState<Partial<AppUser> & { organization?: string | null }>({});

  function load() {
    setLoading(true);
    Promise.all([api.get<AppUser[]>("/users/"), api.get<Organization[]>("/organizations/")])
      .then(([usersRes, orgsRes]) => {
        setUsers(usersRes.data);
        setOrganizations(orgsRes.data);
      })
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post("/users/", {
        username,
        password,
        is_staff: isStaff,
        is_test_client: isTestClient,
        organization: organizationId || null,
      });
      setUsername("");
      setPassword("");
      setIsStaff(false);
      setIsTestClient(false);
      setOrganizationId("");
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось создать пользователя.");
    }
  }

  function startEdit(user: AppUser) {
    setEditingId(user.id);
    setEditDraft({
      is_staff: user.is_staff,
      is_active: user.is_active,
      is_test_client: user.is_test_client,
      organization: user.organization,
      password: "",
    });
  }

  function cancelEdit() {
    setEditingId(null);
    setEditDraft({});
  }

  async function saveEdit(id: number) {
    setError(null);
    try {
      const payload: Record<string, unknown> = {
        is_staff: editDraft.is_staff,
        is_active: editDraft.is_active,
        is_test_client: editDraft.is_test_client,
        organization: editDraft.organization || null,
      };
      if (editDraft.password) {
        payload.password = editDraft.password;
      }
      await api.patch(`/users/${id}/`, payload);
      setEditingId(null);
      setEditDraft({});
      load();
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось сохранить изменения пользователя.");
    }
  }

  return (
    <div>
      <h1>Пользователи</h1>
      <p className="empty-state">
        Тестовому клиенту привяжите отдельную тестовую организацию — он увидит только её данные,
        и для Cash Flow они будут показаны с искажением (тренд сохранён, точные суммы — нет).
      </p>

      <form className="inline-form" onSubmit={handleSubmit}>
        <input
          placeholder="Логин"
          value={username}
          onChange={(e) => setUsername(e.target.value)}
          required
        />
        <input
          placeholder="Пароль"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <select value={organizationId} onChange={(e) => setOrganizationId(e.target.value)}>
          <option value="">Все организации</option>
          {organizations.map((org) => (
            <option key={org.id} value={org.id}>
              {org.name}
              {org.is_test ? " (тест)" : ""}
            </option>
          ))}
        </select>
        <label>
          <input type="checkbox" checked={isStaff} onChange={(e) => setIsStaff(e.target.checked)} />
          Админ
        </label>
        <label>
          <input
            type="checkbox"
            checked={isTestClient}
            onChange={(e) => setIsTestClient(e.target.checked)}
          />
          Тестовый клиент
        </label>
        <button type="submit">Создать пользователя</button>
      </form>
      {error && <div className="error-box">{error}</div>}

      {loading ? (
        <p>Загрузка…</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Логин</th>
              <th>Пароль</th>
              <th>Организация</th>
              <th>Админ</th>
              <th>Тестовый клиент</th>
              <th>Статус</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {users.map((user) =>
              editingId === user.id ? (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>
                    <input
                      placeholder="Новый пароль"
                      value={editDraft.password ?? ""}
                      onChange={(e) => setEditDraft((d) => ({ ...d, password: e.target.value }))}
                    />
                  </td>
                  <td>
                    <select
                      value={editDraft.organization ?? ""}
                      onChange={(e) =>
                        setEditDraft((d) => ({ ...d, organization: e.target.value || null }))
                      }
                    >
                      <option value="">Все организации</option>
                      {organizations.map((org) => (
                        <option key={org.id} value={org.id}>
                          {org.name}
                          {org.is_test ? " (тест)" : ""}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={editDraft.is_staff ?? false}
                      onChange={(e) => setEditDraft((d) => ({ ...d, is_staff: e.target.checked }))}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={editDraft.is_test_client ?? false}
                      onChange={(e) =>
                        setEditDraft((d) => ({ ...d, is_test_client: e.target.checked }))
                      }
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={editDraft.is_active ?? true}
                      onChange={(e) => setEditDraft((d) => ({ ...d, is_active: e.target.checked }))}
                    />
                  </td>
                  <td>
                    <button onClick={() => saveEdit(user.id)}>Сохранить</button>
                    <button onClick={cancelEdit}>Отмена</button>
                  </td>
                </tr>
              ) : (
                <tr key={user.id}>
                  <td>{user.username}</td>
                  <td>{user.plaintext_password || "—"}</td>
                  <td>{user.organization_name || "Все организации"}</td>
                  <td>{user.is_staff ? "Да" : "Нет"}</td>
                  <td>{user.is_test_client ? "Да" : "Нет"}</td>
                  <td>{user.is_active ? "Активен" : "Заблокирован"}</td>
                  <td>
                    <button onClick={() => startEdit(user)}>Изменить</button>
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
