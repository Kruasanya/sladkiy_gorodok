"""Прогноз дневного Cash Flow на основе моделей из «Обучение моделей»/04_Cash_Flow_и_аномалии.

Переиспользует обученные модели (HurdleExpectedValueModel, CatBoost) и функции
построения признаков из `train_returns_cashflow_models.py`, не дублируя их.
Модуль скрипта загружается под фиксированным именем "train_returns_cashflow_models" —
с этим же именем joblib-артефакты были сохранены при обучении (см.
`Обучение моделей/scripts/run_cashflow_training.py`), поэтому десериализация
кастомных классов модели работает корректно.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pandas as pd
from django.db.models import Count, Q, Sum

from apps.banking.models import BankTransaction

_REPO_ROOT = Path(__file__).resolve().parents[4]
_ML_ROOT = _REPO_ROOT / "Обучение моделей"
_SCRIPT_PATH = _ML_ROOT / "scripts" / "train_returns_cashflow_models.py"
_ARTIFACT_ROOT = _ML_ROOT / "artifacts" / "returns_cashflow"
_MODULE_NAME = "train_returns_cashflow_models"

_CATEGORY_COLUMNS = [
    "operating_inflow",
    "operating_outflow",
    "financing",
    "owner_withdrawal",
    "operating_adjustment",
    "unknown",
    "has_classification",
]


def _load_training_module():
    existing = sys.modules.get(_MODULE_NAME)
    if existing is not None:
        return existing
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, _SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_target_model(module, target_col: str):
    import joblib

    path = _ARTIFACT_ROOT / f"cashflow_{target_col}_model.joblib"
    model = joblib.load(path)
    daily_stub = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01", periods=2, freq="D"),
            "inflow": [0.0, 0.0],
            "outflow": [0.0, 0.0],
            "net_cash_flow": [0.0, 0.0],
            "transaction_count": [0.0, 0.0],
            "credit_transaction_count": [0.0, 0.0],
            "debit_transaction_count": [0.0, 0.0],
            **{col: [0.0, 0.0] for col in _CATEGORY_COLUMNS},
        }
    )
    daily_stub = module.add_calendar_features(daily_stub, "date")
    featured = module.add_cashflow_features(daily_stub, target_col)
    feature_cols = [c for c in featured.columns if c not in ["date", "inflow", "outflow", "net_cash_flow"]]
    return {"model": model, "feature_cols": feature_cols}


def build_daily_from_db(organization_ids: list[str] | None = None) -> pd.DataFrame:
    """Строит дневной Cash Flow из фактических банковских транзакций (только активные организации)."""
    qs = BankTransaction.objects.filter(organization__is_active=True, operation_date__isnull=False)
    if organization_ids:
        qs = qs.filter(organization_id__in=organization_ids)

    rows = list(
        qs.values("operation_date").annotate(
            inflow=Sum("credit"),
            outflow=Sum("debit"),
            transaction_count=Count("id"),
            credit_transaction_count=Count("id", filter=Q(direction="credit")),
            debit_transaction_count=Count("id", filter=Q(direction="debit")),
        )
    )
    daily = pd.DataFrame(rows)
    if daily.empty:
        return daily

    daily = daily.rename(columns={"operation_date": "date"})
    daily["date"] = pd.to_datetime(daily["date"])
    date_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = (
        pd.DataFrame({"date": date_range})
        .merge(daily, on="date", how="left")
        .fillna(0.0)
        .sort_values("date")
        .reset_index(drop=True)
    )
    daily["net_cash_flow"] = daily["inflow"] - daily["outflow"]
    for col in _CATEGORY_COLUMNS:
        daily[col] = 0.0

    module = _load_training_module()
    return module.add_calendar_features(daily, "date")


def forecast_cashflow(organization_ids: list[str] | None, horizon_days: int) -> dict:
    """Возвращает фактический дневной Cash Flow и прогноз на `horizon_days` дней вперед."""
    module = _load_training_module()
    daily = build_daily_from_db(organization_ids)
    if daily.empty:
        return {"actual": [], "forecast": []}

    target_models = {
        "inflow": _load_target_model(module, "inflow"),
        "outflow": _load_target_model(module, "outflow"),
    }
    forecast_df = module.forecast_cashflow(daily, target_models, horizon_days=horizon_days)

    actual = [
        {
            "date": row["date"].date().isoformat(),
            "inflow": float(row["inflow"]),
            "outflow": float(row["outflow"]),
            "net_cash_flow": float(row["net_cash_flow"]),
        }
        for _, row in daily.iterrows()
    ]
    forecast = [
        {
            "date": row["date"],
            "predicted_inflow": float(row["predicted_inflow"]),
            "predicted_outflow": float(row["predicted_outflow"]),
            "predicted_net_cash_flow": float(row["predicted_net_cash_flow"]),
        }
        for _, row in forecast_df.iterrows()
    ]
    return {"actual": actual, "forecast": forecast}
