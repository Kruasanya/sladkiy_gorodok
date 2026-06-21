import { useState, type FormEvent } from "react";
import { api } from "../api";

export default function LoginPage({
  onLoggedIn,
}: {
  onLoggedIn: (user: { username: string }) => void;
}) {
  const [username, setUsername] = useState("owner");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const res = await api.post("/auth/login", { username, password });
      onLoggedIn(res.data);
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Не удалось войти.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-screen">
      <form className="login-card" onSubmit={handleSubmit}>
        <h1>КлодУчет</h1>
        <p className="muted">Вход в систему управленческого учета</p>
        <label>
          Логин
          <input value={username} onChange={(e) => setUsername(e.target.value)} autoFocus />
        </label>
        <label>
          Пароль
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && <div className="error-box">{error}</div>}
        <button type="submit" disabled={loading}>
          {loading ? "Входим…" : "Войти"}
        </button>
      </form>
    </div>
  );
}
