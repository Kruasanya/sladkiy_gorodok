import { useEffect, useState } from "react";
import { api } from "../api";

export interface ProductReference {
  id: number;
  nomenclature_raw: string;
  display_name: string;
  is_active: boolean;
  shelf_life_days: number | null;
  unit_cost: string | null;
  first_sale_date: string | null;
  last_sale_date: string | null;
  comment: string;
}

export default function CatalogPage() {
  const [products, setProducts] = useState<ProductReference[]>([]);
  const [loading, setLoading] = useState(false);

  function load() {
    setLoading(true);
    api
      .get<ProductReference[]>("/catalog/products/")
      .then((res) => setProducts(res.data))
      .finally(() => setLoading(false));
  }

  useEffect(load, []);

  function updateField(id: number, field: keyof ProductReference, value: unknown) {
    setProducts((prev) => prev.map((p) => (p.id === id ? { ...p, [field]: value } : p)));
  }

  function save(product: ProductReference) {
    api.patch(`/catalog/products/${product.id}/`, {
      display_name: product.display_name,
      is_active: product.is_active,
      shelf_life_days: product.shelf_life_days,
      unit_cost: product.unit_cost,
      comment: product.comment,
    });
  }

  return (
    <div>
      <h1>Справочники — товары</h1>
      <p className="hint">
        Связывает сырые названия номенклатуры из продаж с общим названием товара, актуальностью,
        сроком годности и себестоимостью.
      </p>

      {loading ? (
        <p>Загрузка…</p>
      ) : (
        <table className="data-table">
          <thead>
            <tr>
              <th>Номенклатура (1С)</th>
              <th>Общее название</th>
              <th>Актуален</th>
              <th>Срок годности, дней</th>
              <th>Себестоимость за ед.</th>
              <th>Первая продажа</th>
              <th>Последняя продажа</th>
              <th>Комментарий</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {products.map((p) => (
              <tr key={p.id}>
                <td title={p.nomenclature_raw}>{p.nomenclature_raw}</td>
                <td>
                  <input
                    value={p.display_name}
                    onChange={(e) => updateField(p.id, "display_name", e.target.value)}
                  />
                </td>
                <td>
                  <input
                    type="checkbox"
                    checked={p.is_active}
                    onChange={(e) => updateField(p.id, "is_active", e.target.checked)}
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={p.shelf_life_days ?? ""}
                    onChange={(e) =>
                      updateField(p.id, "shelf_life_days", e.target.value ? Number(e.target.value) : null)
                    }
                  />
                </td>
                <td>
                  <input
                    type="number"
                    value={p.unit_cost ?? ""}
                    onChange={(e) => updateField(p.id, "unit_cost", e.target.value || null)}
                  />
                </td>
                <td>{p.first_sale_date ?? "—"}</td>
                <td>{p.last_sale_date ?? "—"}</td>
                <td>
                  <input value={p.comment} onChange={(e) => updateField(p.id, "comment", e.target.value)} />
                </td>
                <td>
                  <button onClick={() => save(p)}>Сохранить</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
