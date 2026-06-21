#!/usr/bin/env python3
"""Train return-volume, daily cash-flow and inflow-anomaly models.

The script is intentionally self-contained: it reads the final 1C/bank tables,
builds leakage-safe time-series features, compares statistical baselines with
CatBoost/LightGBM, saves forecasts, figures and a retraining/drift status file.
"""

from __future__ import annotations

import json
import math
import warnings
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from catboost import CatBoostRegressor
from sklearn.ensemble import ExtraTreesRegressor, IsolationForest, RandomForestRegressor
from sklearn.metrics import mean_absolute_error

warnings.filterwarnings("ignore", category=FutureWarning)

try:
    from lightgbm import LGBMRegressor
except (ImportError, OSError):
    LGBMRegressor = None


REPO_ROOT = Path(__file__).resolve().parents[2]
ML_ROOT = REPO_ROOT / "Обучение моделей"
DATA_ROOT = REPO_ROOT / "Данные" / "Итоговые таблицы"
CLASSIFIED_BANK_PATH = (
    REPO_ROOT
    / "Исследование разметки транзакций"
    / "outputs"
    / "classified_bank_operations.csv"
)

OUTPUT_ROOT = ML_ROOT / "outputs" / "returns_cashflow"
FIGURE_ROOT = ML_ROOT / "figures" / "returns_cashflow"
ARTIFACT_ROOT = ML_ROOT / "artifacts" / "returns_cashflow"

RANDOM_STATE = 42


def ensure_dirs() -> None:
    for path in (OUTPUT_ROOT, FIGURE_ROOT, ARTIFACT_ROOT):
        path.mkdir(parents=True, exist_ok=True)


def wape(y_true: np.ndarray | pd.Series, y_pred: np.ndarray | pd.Series) -> float:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    denom = np.abs(y_true).sum()
    if denom <= 1e-9:
        return float("nan")
    return float(np.abs(y_true - y_pred).sum() / denom)


def clamp_non_negative(values: np.ndarray | pd.Series) -> np.ndarray:
    return np.clip(np.asarray(values, dtype=float), 0.0, None)


def week_start(series: pd.Series) -> pd.Series:
    dates = pd.to_datetime(series)
    return (dates - pd.to_timedelta(dates.dt.weekday, unit="D")).dt.normalize()


def add_calendar_features(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    out = df.copy()
    dt = pd.to_datetime(out[date_col])
    iso = dt.dt.isocalendar()
    out["year"] = dt.dt.year
    out["month"] = dt.dt.month
    out["week_of_year"] = iso.week.astype(int)
    out["day"] = dt.dt.day
    out["day_of_week"] = dt.dt.dayofweek
    out["is_weekend"] = out["day_of_week"].isin([5, 6]).astype(int)
    out["is_month_start"] = dt.dt.is_month_start.astype(int)
    out["is_month_end"] = dt.dt.is_month_end.astype(int)
    out["is_quarter_end"] = dt.dt.is_quarter_end.astype(int)
    out["is_payday_window"] = out["day"].isin([5, 10, 15, 20, 25, 30]).astype(int)
    out["is_summer"] = out["month"].isin([6, 7, 8]).astype(int)
    return out


def read_product_dictionary() -> pd.DataFrame:
    path = ML_ROOT / "Справочники" / "справочник_товаров_шаблон.csv"
    dictionary = pd.read_csv(path)
    dictionary = dictionary.rename(columns={"nomenclature_raw": "nomenclature"})
    dictionary["is_active_product"] = (
        dictionary["актуальность"].fillna("").str.lower().eq("да").astype(int)
    )
    for col in ["срок_годности_дней", "себестоимость_за_единицу"]:
        dictionary[col] = pd.to_numeric(dictionary[col], errors="coerce")
    return dictionary


def read_sales() -> pd.DataFrame:
    sales = pd.read_csv(DATA_ROOT / "sales_by_counterparties.csv", parse_dates=["sale_date"])
    dictionary = read_product_dictionary()
    sales = sales.merge(
        dictionary[
            [
                "nomenclature",
                "общее_название",
                "актуальность",
                "is_active_product",
                "срок_годности_дней",
                "себестоимость_за_единицу",
            ]
        ],
        on="nomenclature",
        how="left",
    )
    sales["product_name"] = sales["общее_название"].fillna(sales["nomenclature"])
    sales["is_active_product"] = sales["is_active_product"].fillna(0).astype(int)
    sales["shelf_life_days"] = sales["срок_годности_дней"].fillna(
        sales["срок_годности_дней"].median()
    )
    sales["unit_cost"] = sales["себестоимость_за_единицу"].fillna(
        sales["себестоимость_за_единицу"].median()
    )
    sales["brand"] = sales["brand"].fillna("unknown")
    sales["legal_entity"] = sales["legal_entity"].fillna("unknown")
    return sales


def build_weekly_returns_panel(sales: pd.DataFrame) -> pd.DataFrame:
    data = sales.copy()
    data["week"] = week_start(data["sale_date"])
    data["gross_sales_qty"] = np.where(
        data["sales_doc_type"].eq("Реализация"), data["quantity"].clip(lower=0), 0.0
    )
    data["gross_sales_amount"] = np.where(
        data["sales_doc_type"].eq("Реализация"), data["amount"].clip(lower=0), 0.0
    )
    data["return_qty"] = np.where(
        data["sales_doc_type"].eq("Корректировка реализации"),
        (-data["quantity"]).clip(lower=0),
        0.0,
    )
    data["return_amount"] = np.where(
        data["sales_doc_type"].eq("Корректировка реализации"),
        (-data["amount"]).clip(lower=0),
        0.0,
    )
    data["return_document_count"] = data["sales_doc_type"].eq("Корректировка реализации").astype(int)

    group_cols = [
        "product_name",
        "brand",
        "is_active_product",
        "shelf_life_days",
        "unit_cost",
    ]
    weekly = (
        data.groupby(group_cols + ["week"], dropna=False)
        .agg(
            gross_sales_qty=("gross_sales_qty", "sum"),
            gross_sales_amount=("gross_sales_amount", "sum"),
            return_qty=("return_qty", "sum"),
            return_amount=("return_amount", "sum"),
            return_document_count=("return_document_count", "sum"),
        )
        .reset_index()
    )

    panels: list[pd.DataFrame] = []
    for keys, part in weekly.groupby(group_cols, dropna=False):
        start = part["week"].min()
        end = weekly["week"].max()
        idx = pd.date_range(start, end, freq="W-MON")
        base = pd.DataFrame({"week": idx})
        if not isinstance(keys, tuple):
            keys = (keys,)
        for col, value in zip(group_cols, keys):
            base[col] = value
        merged = base.merge(part, on=group_cols + ["week"], how="left")
        value_cols = [
            "gross_sales_qty",
            "gross_sales_amount",
            "return_qty",
            "return_amount",
            "return_document_count",
        ]
        merged[value_cols] = merged[value_cols].fillna(0.0)
        panels.append(merged)

    panel = pd.concat(panels, ignore_index=True)
    panel["return_rate_qty"] = panel["return_qty"] / panel["gross_sales_qty"].replace(0, np.nan)
    panel["return_rate_qty"] = panel["return_rate_qty"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
    panel = add_calendar_features(panel, "week")
    return panel.sort_values(["product_name", "brand", "week"]).reset_index(drop=True)


def add_group_lag_features(
    df: pd.DataFrame,
    group_cols: list[str],
    value_cols: list[str],
    windows: tuple[int, ...] = (4, 8),
    lags: tuple[int, ...] = (1, 2, 4),
) -> pd.DataFrame:
    out = df.sort_values(group_cols + ["week"]).copy()
    grouped = out.groupby(group_cols, dropna=False)
    for col in value_cols:
        shifted = grouped[col].shift(1)
        for lag in lags:
            out[f"{col}_lag_{lag}"] = grouped[col].shift(lag)
        for window in windows:
            out[f"{col}_roll_mean_{window}"] = shifted.groupby(
                [out[g] for g in group_cols], dropna=False
            ).rolling(window, min_periods=1).mean().reset_index(level=list(range(len(group_cols))), drop=True)
            out[f"{col}_roll_std_{window}"] = shifted.groupby(
                [out[g] for g in group_cols], dropna=False
            ).rolling(window, min_periods=2).std().reset_index(level=list(range(len(group_cols))), drop=True)
    feature_cols = [c for c in out.columns if "_lag_" in c or "_roll_" in c]
    out[feature_cols] = out[feature_cols].fillna(0.0)
    return out


@dataclass
class ModelResult:
    name: str
    estimator: object | None
    metric_rows: list[dict]
    predict_fn: Callable[[pd.DataFrame], np.ndarray]
    lower_is_better: float


class BaselineRegressor:
    def __init__(self, feature: str):
        self.feature = feature

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "BaselineRegressor":
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return clamp_non_negative(X[self.feature].fillna(0.0))


class LogTargetModel:
    def __init__(self, model: object):
        self.model = model

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "LogTargetModel":
        self.model.fit(X, np.log1p(np.clip(y.astype(float), 0.0, None)))
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return clamp_non_negative(np.expm1(self.model.predict(X)))


class NumericOnlyModel:
    def __init__(self, model: object):
        self.model = model
        self.columns_: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series) -> "NumericOnlyModel":
        numeric = X.select_dtypes(include=[np.number])
        self.columns_ = list(numeric.columns)
        self.model.fit(numeric, y)
        return self

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return clamp_non_negative(self.model.predict(X[self.columns_]))


def make_return_candidates(cat_features: list[str]) -> dict[str, object]:
    candidates = {
        "baseline_zero": BaselineRegressor("baseline_zero"),
        "last_week": BaselineRegressor("return_qty_lag_1"),
        "moving_average_4": BaselineRegressor("return_qty_roll_mean_4"),
        "catboost_mae": CatBoostRegressor(
            loss_function="MAE",
            iterations=350,
            depth=3,
            learning_rate=0.04,
            l2_leaf_reg=12,
            random_seed=RANDOM_STATE,
            verbose=False,
            allow_writing_files=False,
            cat_features=cat_features,
        ),
        "random_forest_numeric": NumericOnlyModel(
            RandomForestRegressor(
                n_estimators=300,
                min_samples_leaf=10,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
        ),
    }
    if LGBMRegressor is not None:
        candidates["lightgbm_mae"] = LGBMRegressor(
            objective="mae",
            n_estimators=250,
            learning_rate=0.035,
            num_leaves=7,
            min_child_samples=28,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_alpha=0.25,
            reg_lambda=2.0,
            random_state=RANDOM_STATE,
            verbosity=-1,
        )
    return candidates


def make_cashflow_candidates() -> dict[str, object]:
    candidates = {
        "seasonal_naive_7": BaselineRegressor("target_lag_7"),
        "moving_average_7": BaselineRegressor("target_roll_mean_7"),
        "moving_average_30": BaselineRegressor("target_roll_mean_30"),
        "catboost_log_mae": LogTargetModel(
            CatBoostRegressor(
                loss_function="MAE",
                iterations=450,
                depth=4,
                learning_rate=0.035,
                l2_leaf_reg=20,
                random_seed=RANDOM_STATE,
                verbose=False,
                allow_writing_files=False,
            )
        ),
        "extra_trees_log": LogTargetModel(
            ExtraTreesRegressor(
                n_estimators=400,
                min_samples_leaf=8,
                random_state=RANDOM_STATE,
                n_jobs=-1,
            )
        ),
    }
    if LGBMRegressor is not None:
        candidates["lightgbm_log_mae"] = LogTargetModel(
            LGBMRegressor(
                objective="mae",
                n_estimators=350,
                learning_rate=0.03,
                num_leaves=15,
                min_child_samples=25,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_alpha=0.3,
                reg_lambda=3.0,
                random_state=RANDOM_STATE,
                verbosity=-1,
            )
        )
    return candidates


def evaluate_time_splits(
    df: pd.DataFrame,
    date_col: str,
    target_col: str,
    feature_cols: list[str],
    candidates: dict[str, object],
    test_windows: list[pd.Timestamp],
    test_window_size_days: int,
) -> tuple[pd.DataFrame, str]:
    metric_rows: list[dict] = []
    for fold, test_start in enumerate(test_windows, start=1):
        test_end = test_start + pd.Timedelta(days=test_window_size_days - 1)
        train_mask = df[date_col] < test_start
        test_mask = (df[date_col] >= test_start) & (df[date_col] <= test_end)
        train = df.loc[train_mask].copy()
        test = df.loc[test_mask].copy()
        if train.empty or test.empty or test[target_col].abs().sum() <= 1e-9:
            continue
        X_train = train[feature_cols]
        y_train = train[target_col].astype(float)
        X_test = test[feature_cols]
        y_test = test[target_col].astype(float)
        for name, estimator in candidates.items():
            model = deepcopy(estimator)
            model.fit(X_train, y_train)
            pred = clamp_non_negative(model.predict(X_test))
            metric_rows.append(
                {
                    "fold": fold,
                    "model": name,
                    "target": target_col,
                    "test_start": test_start.date().isoformat(),
                    "test_end": test_end.date().isoformat(),
                    "rows_train": len(train),
                    "rows_test": len(test),
                    "wape": wape(y_test, pred),
                    "mae": mean_absolute_error(y_test, pred),
                    "actual_sum": float(y_test.sum()),
                    "predicted_sum": float(pred.sum()),
                }
            )

    metrics = pd.DataFrame(metric_rows)
    if metrics.empty:
        raise RuntimeError(f"No valid validation folds for {target_col}")
    ranking = (
        metrics.groupby("model", as_index=False)
        .agg(mean_wape=("wape", "mean"), std_wape=("wape", "std"), mean_mae=("mae", "mean"))
        .sort_values(["mean_wape", "mean_mae"], ascending=[True, True])
    )
    best_model = str(ranking.iloc[0]["model"])
    return metrics, best_model


def fit_named_candidate(
    candidates: dict[str, object],
    best_model: str,
    X: pd.DataFrame,
    y: pd.Series,
) -> object:
    estimator = deepcopy(candidates[best_model])
    estimator.fit(X, y.astype(float))
    return estimator


def train_returns_model() -> dict:
    sales = read_sales()
    panel = build_weekly_returns_panel(sales)
    group_cols = ["product_name", "brand"]
    panel = add_group_lag_features(
        panel,
        group_cols=group_cols,
        value_cols=["return_qty", "return_amount", "gross_sales_qty", "return_rate_qty"],
    )
    panel["baseline_zero"] = 0.0
    panel["weeks_since_first_observation"] = panel.groupby(group_cols).cumcount()

    feature_cols = [
        "product_name",
        "brand",
        "is_active_product",
        "shelf_life_days",
        "unit_cost",
        "month",
        "week_of_year",
        "is_summer",
        "weeks_since_first_observation",
        "return_qty_lag_1",
        "return_qty_lag_2",
        "return_qty_lag_4",
        "return_qty_roll_mean_4",
        "return_qty_roll_mean_8",
        "return_qty_roll_std_4",
        "return_amount_lag_1",
        "gross_sales_qty_lag_1",
        "gross_sales_qty_lag_2",
        "gross_sales_qty_lag_4",
        "gross_sales_qty_roll_mean_4",
        "gross_sales_qty_roll_mean_8",
        "return_rate_qty_lag_1",
        "return_rate_qty_roll_mean_4",
        "return_rate_qty_roll_mean_8",
        "baseline_zero",
    ]
    model_df = panel.loc[panel["weeks_since_first_observation"] >= 4].copy()
    model_df[["product_name", "brand"]] = model_df[["product_name", "brand"]].astype(str)

    last_week = model_df["week"].max()
    test_starts = [
        last_week - pd.Timedelta(weeks=6 * i + 5) for i in reversed(range(4))
    ]
    candidates = make_return_candidates(cat_features=["product_name", "brand"])
    metrics, best_model = evaluate_time_splits(
        model_df,
        date_col="week",
        target_col="return_qty",
        feature_cols=feature_cols,
        candidates=candidates,
        test_windows=test_starts,
        test_window_size_days=42,
    )
    ranking = (
        metrics.groupby("model", as_index=False)
        .agg(mean_wape=("wape", "mean"), std_wape=("wape", "std"), mean_mae=("mae", "mean"))
        .sort_values(["mean_wape", "mean_mae"])
    )
    model = fit_named_candidate(
        candidates,
        best_model,
        model_df[feature_cols],
        model_df["return_qty"],
    )
    joblib.dump(model, ARTIFACT_ROOT / "returns_volume_model.joblib")
    metrics.to_csv(OUTPUT_ROOT / "returns_validation_metrics.csv", index=False)
    ranking.to_csv(OUTPUT_ROOT / "returns_model_ranking.csv", index=False)

    forecast = forecast_returns(panel, model, best_model, feature_cols, horizon_weeks=4)
    forecast.to_csv(OUTPUT_ROOT / "returns_forecast_next_4_weeks.csv", index=False)
    plot_returns(panel, forecast)

    latest_start = last_week - pd.Timedelta(weeks=3)
    recent = model_df.loc[model_df["week"] >= latest_start].copy()
    recent_pred = clamp_non_negative(model.predict(recent[feature_cols]))
    recent_wape = wape(recent["return_qty"], recent_pred)
    cv_wape = float(ranking.iloc[0]["mean_wape"])
    drift_flag = bool(not math.isnan(recent_wape) and recent_wape > cv_wape * 1.35)
    top_forecast = forecast.sort_values("predicted_return_qty", ascending=False).head(8).copy()
    top_forecast["week"] = pd.to_datetime(top_forecast["week"]).dt.date.astype(str)

    return {
        "best_model": best_model,
        "cv_mean_wape": cv_wape,
        "cv_mean_mae": float(ranking.iloc[0]["mean_mae"]),
        "recent_4w_wape": recent_wape,
        "drift_flag": drift_flag,
        "last_fact_week": last_week.date().isoformat(),
        "forecast_total_qty_4w": float(forecast["predicted_return_qty"].sum()),
        "top_forecast_rows": top_forecast.to_dict("records"),
    }


def compute_return_feature_row(history: pd.DataFrame, row: dict) -> dict:
    result = dict(row)
    for col in ["return_qty", "return_amount", "gross_sales_qty", "return_rate_qty"]:
        values = history[col].astype(float).tolist()
        for lag in (1, 2, 4):
            result[f"{col}_lag_{lag}"] = values[-lag] if len(values) >= lag else 0.0
        for window in (4, 8):
            past = values[-window:]
            result[f"{col}_roll_mean_{window}"] = float(np.mean(past)) if past else 0.0
            result[f"{col}_roll_std_{window}"] = float(np.std(past, ddof=1)) if len(past) >= 2 else 0.0
    result["baseline_zero"] = 0.0
    return result


def forecast_returns(
    panel: pd.DataFrame,
    model: object,
    best_model: str,
    feature_cols: list[str],
    horizon_weeks: int,
) -> pd.DataFrame:
    del best_model
    group_cols = ["product_name", "brand"]
    forecasts: list[dict] = []
    work = panel.sort_values(group_cols + ["week"]).copy()
    max_week = work["week"].max()
    for step in range(1, horizon_weeks + 1):
        forecast_week = max_week + pd.Timedelta(weeks=step)
        rows: list[dict] = []
        for (product_name, brand), hist in work.groupby(group_cols, dropna=False):
            hist = hist.sort_values("week")
            last = hist.iloc[-1]
            gross_sales_qty = float(hist["gross_sales_qty"].tail(4).mean())
            gross_sales_amount = float(hist["gross_sales_amount"].tail(4).mean())
            base = {
                "week": forecast_week,
                "product_name": product_name,
                "brand": brand,
                "is_active_product": int(last["is_active_product"]),
                "shelf_life_days": float(last["shelf_life_days"]),
                "unit_cost": float(last["unit_cost"]),
                "gross_sales_qty": gross_sales_qty,
                "gross_sales_amount": gross_sales_amount,
                "return_qty": 0.0,
                "return_amount": 0.0,
                "return_document_count": 0.0,
                "return_rate_qty": 0.0,
                "weeks_since_first_observation": int(last["weeks_since_first_observation"]) + step,
            }
            base = add_calendar_features(pd.DataFrame([base]), "week").iloc[0].to_dict()
            rows.append(compute_return_feature_row(hist, base))
        future = pd.DataFrame(rows)
        future[["product_name", "brand"]] = future[["product_name", "brand"]].astype(str)
        pred = clamp_non_negative(model.predict(future[feature_cols]))
        future["return_qty"] = pred
        future["return_rate_qty"] = future["return_qty"] / future["gross_sales_qty"].replace(0, np.nan)
        future["return_rate_qty"] = future["return_rate_qty"].replace([np.inf, -np.inf], np.nan).fillna(0.0)
        future["return_amount"] = future["return_qty"] * future["unit_cost"]
        work = pd.concat([work, future[work.columns]], ignore_index=True)
        forecasts.append(
            future[
                [
                    "week",
                    "product_name",
                    "brand",
                    "is_active_product",
                    "gross_sales_qty",
                    "return_qty",
                    "return_rate_qty",
                ]
            ].rename(
                columns={
                    "gross_sales_qty": "baseline_expected_sales_qty",
                    "return_qty": "predicted_return_qty",
                    "return_rate_qty": "predicted_return_rate_qty",
                }
            )
        )
    out = pd.concat(forecasts, ignore_index=True)
    return out.loc[out["is_active_product"].eq(1)].sort_values(
        ["week", "predicted_return_qty"], ascending=[True, False]
    )


def plot_returns(panel: pd.DataFrame, forecast: pd.DataFrame) -> None:
    weekly_actual = panel.groupby("week", as_index=False)["return_qty"].sum()
    weekly_forecast = forecast.groupby("week", as_index=False)["predicted_return_qty"].sum()

    plt.figure(figsize=(11, 5))
    plt.plot(weekly_actual["week"], weekly_actual["return_qty"], label="Факт возвратов", linewidth=2)
    plt.plot(
        weekly_forecast["week"],
        weekly_forecast["predicted_return_qty"],
        label="Прогноз возвратов",
        linewidth=2,
        marker="o",
    )
    plt.title("Прогноз объёма возвратов на 4 недели")
    plt.ylabel("Штуки")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_ROOT / "returns_forecast_4w.png", dpi=180)
    plt.close()

    top = (
        forecast.groupby(["product_name", "brand"], as_index=False)["predicted_return_qty"]
        .sum()
        .sort_values("predicted_return_qty", ascending=False)
        .head(10)
    )
    labels = top["product_name"] + " / " + top["brand"]
    plt.figure(figsize=(10, 5))
    plt.barh(labels[::-1], top["predicted_return_qty"][::-1])
    plt.title("Топ товар-сеть по ожидаемому возврату")
    plt.xlabel("Штуки за 4 недели")
    plt.tight_layout()
    plt.savefig(FIGURE_ROOT / "returns_top_risk.png", dpi=180)
    plt.close()


def read_bank_daily() -> pd.DataFrame:
    bank = pd.read_csv(DATA_ROOT / "bank_statement_transactions.csv", parse_dates=["operation_date"])
    daily = (
        bank.groupby("operation_date", as_index=False)
        .agg(
            inflow=("credit", "sum"),
            outflow=("debit", "sum"),
            transaction_count=("amount", "size"),
            credit_transaction_count=("credit", lambda x: (x > 0).sum()),
            debit_transaction_count=("debit", lambda x: (x > 0).sum()),
        )
        .rename(columns={"operation_date": "date"})
    )
    date_range = pd.date_range(daily["date"].min(), daily["date"].max(), freq="D")
    daily = pd.DataFrame({"date": date_range}).merge(daily, on="date", how="left").fillna(0.0)
    daily["net_cash_flow"] = daily["inflow"] - daily["outflow"]

    if CLASSIFIED_BANK_PATH.exists():
        classified = pd.read_csv(CLASSIFIED_BANK_PATH, parse_dates=["date"])
        pivot = (
            classified.pivot_table(
                index="date",
                columns="cash_flow_section",
                values="amount",
                aggfunc="sum",
                fill_value=0.0,
            )
            .reset_index()
            .rename_axis(None, axis=1)
        )
        for col in [
            "operating_inflow",
            "operating_outflow",
            "financing",
            "owner_withdrawal",
            "operating_adjustment",
        ]:
            if col not in pivot:
                pivot[col] = 0.0
        pivot["has_classification"] = 1
        daily = daily.merge(pivot, on="date", how="left")
    else:
        daily["has_classification"] = 0

    category_cols = [
        "operating_inflow",
        "operating_outflow",
        "financing",
        "owner_withdrawal",
        "operating_adjustment",
        "has_classification",
    ]
    for col in category_cols:
        if col not in daily:
            daily[col] = 0.0
    daily[category_cols] = daily[category_cols].fillna(0.0)
    daily = add_calendar_features(daily, "date")
    return daily.sort_values("date").reset_index(drop=True)


def add_cashflow_features(daily: pd.DataFrame, target_col: str) -> pd.DataFrame:
    out = daily.copy()
    target = out[target_col].astype(float)
    shifted = target.shift(1)
    for lag in (1, 2, 3, 7, 14, 28):
        out[f"target_lag_{lag}"] = target.shift(lag)
    for window in (7, 14, 30):
        out[f"target_roll_mean_{window}"] = shifted.rolling(window, min_periods=1).mean()
        out[f"target_roll_std_{window}"] = shifted.rolling(window, min_periods=2).std()
        out[f"target_nonzero_days_{window}"] = (
            (target.shift(1) > 0).rolling(window, min_periods=1).sum()
        )
    for col in [
        "transaction_count",
        "credit_transaction_count",
        "debit_transaction_count",
        "inflow",
        "outflow",
        "net_cash_flow",
        "operating_inflow",
        "operating_outflow",
        "financing",
        "owner_withdrawal",
        "operating_adjustment",
    ]:
        if col == target_col:
            continue
        out[f"{col}_lag_1"] = out[col].shift(1)
        out[f"{col}_roll_mean_7"] = out[col].shift(1).rolling(7, min_periods=1).mean()
    feature_cols = [c for c in out.columns if c not in ["date", "inflow", "outflow", "net_cash_flow"]]
    out[feature_cols] = out[feature_cols].fillna(0.0)
    return out


def train_cashflow_target(daily: pd.DataFrame, target_col: str) -> dict:
    featured = add_cashflow_features(daily, target_col)
    feature_cols = [
        c
        for c in featured.columns
        if c
        not in [
            "date",
            "inflow",
            "outflow",
            "net_cash_flow",
        ]
    ]
    featured = featured.loc[featured["date"] >= featured["date"].min() + pd.Timedelta(days=30)].copy()
    max_date = featured["date"].max()
    test_starts = [
        max_date - pd.Timedelta(days=28 * i + 27) for i in reversed(range(4))
    ]
    candidates = make_cashflow_candidates()
    metrics, best_model = evaluate_time_splits(
        featured,
        date_col="date",
        target_col=target_col,
        feature_cols=feature_cols,
        candidates=candidates,
        test_windows=test_starts,
        test_window_size_days=28,
    )
    ranking = (
        metrics.groupby("model", as_index=False)
        .agg(mean_wape=("wape", "mean"), std_wape=("wape", "std"), mean_mae=("mae", "mean"))
        .sort_values(["mean_wape", "mean_mae"])
    )
    model = fit_named_candidate(
        candidates,
        best_model,
        featured[feature_cols],
        featured[target_col],
    )
    joblib.dump(model, ARTIFACT_ROOT / f"cashflow_{target_col}_model.joblib")

    latest_start = max_date - pd.Timedelta(days=13)
    recent = featured.loc[featured["date"] >= latest_start].copy()
    recent_pred = clamp_non_negative(model.predict(recent[feature_cols]))
    recent_wape = wape(recent[target_col], recent_pred)
    cv_wape = float(ranking.iloc[0]["mean_wape"])
    drift_flag = bool(not math.isnan(recent_wape) and recent_wape > cv_wape * 1.35)

    return {
        "target": target_col,
        "model": model,
        "best_model": best_model,
        "feature_cols": feature_cols,
        "metrics": metrics,
        "ranking": ranking,
        "cv_mean_wape": cv_wape,
        "cv_mean_mae": float(ranking.iloc[0]["mean_mae"]),
        "recent_14d_wape": recent_wape,
        "drift_flag": drift_flag,
    }


def forecast_cashflow(daily: pd.DataFrame, target_models: dict[str, dict], horizon_days: int = 14) -> pd.DataFrame:
    work = daily.copy().sort_values("date").reset_index(drop=True)
    max_date = work["date"].max()
    forecasts: list[dict] = []
    for step in range(1, horizon_days + 1):
        date = max_date + pd.Timedelta(days=step)
        base = {
            "date": date,
            "inflow": 0.0,
            "outflow": 0.0,
            "transaction_count": float(work["transaction_count"].tail(7).mean()),
            "credit_transaction_count": float(work["credit_transaction_count"].tail(7).mean()),
            "debit_transaction_count": float(work["debit_transaction_count"].tail(7).mean()),
            "net_cash_flow": 0.0,
            "operating_inflow": 0.0,
            "operating_outflow": 0.0,
            "financing": 0.0,
            "owner_withdrawal": 0.0,
            "operating_adjustment": 0.0,
            "has_classification": 0.0,
        }
        future_row = add_calendar_features(pd.DataFrame([base]), "date")
        candidate = pd.concat([work, future_row], ignore_index=True)

        predictions = {}
        for target_col, payload in target_models.items():
            featured = add_cashflow_features(candidate, target_col).tail(1)
            pred = clamp_non_negative(payload["model"].predict(featured[payload["feature_cols"]]))[0]
            predictions[target_col] = float(pred)

        future_row["inflow"] = predictions["inflow"]
        future_row["outflow"] = predictions["outflow"]
        future_row["net_cash_flow"] = future_row["inflow"] - future_row["outflow"]
        for col in work.columns:
            if col not in future_row.columns:
                future_row[col] = 0.0
        work = pd.concat([work, future_row[work.columns]], ignore_index=True)
        forecasts.append(
            {
                "date": date.date().isoformat(),
                "predicted_inflow": predictions["inflow"],
                "predicted_outflow": predictions["outflow"],
                "predicted_net_cash_flow": predictions["inflow"] - predictions["outflow"],
            }
        )
    out = pd.DataFrame(forecasts)
    out["projected_balance_delta_from_last_fact"] = out["predicted_net_cash_flow"].cumsum()
    return out


def detect_inflow_anomalies(daily: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    bank = pd.read_csv(DATA_ROOT / "bank_statement_transactions.csv", parse_dates=["operation_date"])
    credit = bank.loc[bank["direction"].eq("credit") & (bank["credit"] > 0)].copy()
    credit = credit.sort_values(["counterparty_name", "operation_date"])
    credit["counterparty_tx_count"] = credit.groupby("counterparty_name")["credit"].transform("count")
    credit["counterparty_median"] = credit.groupby("counterparty_name")["credit"].transform("median")
    credit["counterparty_mad"] = credit.groupby("counterparty_name")["credit"].transform(
        lambda x: np.median(np.abs(x - np.median(x)))
    )
    global_median = float(credit["credit"].median())
    global_mad = float(np.median(np.abs(credit["credit"] - global_median))) or 1.0
    credit["amount_robust_z"] = (
        0.6745
        * (credit["credit"] - credit["counterparty_median"].fillna(global_median))
        / credit["counterparty_mad"].replace(0, np.nan).fillna(global_mad)
    )
    credit["previous_payment_date"] = credit.groupby("counterparty_name")["operation_date"].shift(1)
    credit["days_since_previous_payment"] = (
        credit["operation_date"] - credit["previous_payment_date"]
    ).dt.days.fillna(999)
    credit["rare_counterparty_flag"] = credit["counterparty_tx_count"].le(2).astype(int)

    iso_features = credit[
        ["credit", "amount_robust_z", "days_since_previous_payment", "counterparty_tx_count"]
    ].fillna(0.0)
    iso_features["log_credit"] = np.log1p(iso_features["credit"])
    isolation = IsolationForest(
        n_estimators=300,
        contamination=min(0.03, max(0.005, 20 / max(len(credit), 1))),
        random_state=RANDOM_STATE,
    )
    credit["isolation_score"] = -isolation.fit_predict(iso_features.drop(columns=["credit"]))
    credit["inflow_anomaly_score"] = (
        credit["amount_robust_z"].abs().clip(upper=10)
        + credit["rare_counterparty_flag"] * 2
        + (credit["days_since_previous_payment"] > 45).astype(int)
        + (credit["isolation_score"] > 0).astype(int) * 2
    )
    credit["is_anomaly"] = credit["inflow_anomaly_score"].ge(5)
    credit["reason"] = np.select(
        [
            credit["rare_counterparty_flag"].eq(1),
            credit["amount_robust_z"].abs().ge(4),
            credit["days_since_previous_payment"].gt(45),
            credit["isolation_score"].gt(0),
        ],
        [
            "редкий контрагент",
            "сумма сильно отличается от истории контрагента",
            "нетипичный интервал между поступлениями",
            "IsolationForest пометил операцию",
        ],
        default="комбинация умеренных отклонений",
    )

    anomaly_cols = [
        "operation_date",
        "counterparty_name",
        "credit",
        "amount_robust_z",
        "days_since_previous_payment",
        "counterparty_tx_count",
        "inflow_anomaly_score",
        "reason",
        "payment_purpose",
    ]
    tx_anomalies = (
        credit.loc[credit["is_anomaly"], anomaly_cols]
        .sort_values(["operation_date", "inflow_anomaly_score"], ascending=[False, False])
        .head(60)
    )
    tx_anomalies.to_csv(OUTPUT_ROOT / "inflow_transaction_anomalies.csv", index=False)

    daily_anom = daily[["date", "inflow"]].copy()
    rolling_median = daily_anom["inflow"].shift(1).rolling(30, min_periods=10).median()
    rolling_mad = daily_anom["inflow"].shift(1).rolling(30, min_periods=10).apply(
        lambda x: np.median(np.abs(x - np.median(x))), raw=False
    )
    daily_anom["inflow_robust_z_30d"] = (
        0.6745 * (daily_anom["inflow"] - rolling_median) / rolling_mad.replace(0, np.nan)
    ).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    daily_anom["is_daily_inflow_anomaly"] = daily_anom["inflow_robust_z_30d"].abs().ge(3.5)
    daily_anom.to_csv(OUTPUT_ROOT / "daily_inflow_anomaly_scores.csv", index=False)
    return tx_anomalies, daily_anom


def markdown_table(df: pd.DataFrame, float_digits: int = 2) -> str:
    if df.empty:
        return "_Нет данных._"
    rows = []
    columns = list(df.columns)
    rows.append("| " + " | ".join(columns) + " |")
    rows.append("| " + " | ".join(["---"] * len(columns)) + " |")
    for _, row in df.iterrows():
        values = []
        for col in columns:
            value = row[col]
            if isinstance(value, (float, np.floating)):
                values.append(f"{value:.{float_digits}f}")
            else:
                values.append(str(value))
        rows.append("| " + " | ".join(values) + " |")
    return "\n".join(rows)


def train_cashflow_models() -> dict:
    daily = read_bank_daily()
    target_models = {
        "inflow": train_cashflow_target(daily, "inflow"),
        "outflow": train_cashflow_target(daily, "outflow"),
    }
    metrics = pd.concat([payload["metrics"] for payload in target_models.values()], ignore_index=True)
    rankings = pd.concat(
        [
            payload["ranking"].assign(target=target)
            for target, payload in target_models.items()
        ],
        ignore_index=True,
    )
    metrics.to_csv(OUTPUT_ROOT / "cashflow_validation_metrics.csv", index=False)
    rankings.to_csv(OUTPUT_ROOT / "cashflow_model_ranking.csv", index=False)

    forecast = forecast_cashflow(daily, target_models, horizon_days=14)
    forecast.to_csv(OUTPUT_ROOT / "cashflow_forecast_next_14_days.csv", index=False)
    tx_anomalies, daily_anom = detect_inflow_anomalies(daily)
    plot_cashflow(daily, forecast, daily_anom)

    return {
        "last_fact_date": daily["date"].max().date().isoformat(),
        "forecast_net_14d": float(forecast["predicted_net_cash_flow"].sum()),
        "forecast_inflow_14d": float(forecast["predicted_inflow"].sum()),
        "forecast_outflow_14d": float(forecast["predicted_outflow"].sum()),
        "models": {
            target: {
                "best_model": payload["best_model"],
                "cv_mean_wape": payload["cv_mean_wape"],
                "cv_mean_mae": payload["cv_mean_mae"],
                "recent_14d_wape": payload["recent_14d_wape"],
                "drift_flag": payload["drift_flag"],
            }
            for target, payload in target_models.items()
        },
        "inflow_anomaly_count": int(len(tx_anomalies)),
        "recent_daily_inflow_anomalies_30d": int(
            daily_anom.loc[
                daily_anom["date"] >= daily["date"].max() - pd.Timedelta(days=29),
                "is_daily_inflow_anomaly",
            ].sum()
        ),
    }


def plot_cashflow(daily: pd.DataFrame, forecast: pd.DataFrame, daily_anom: pd.DataFrame) -> None:
    recent = daily.tail(120)
    forecast_dates = pd.to_datetime(forecast["date"])
    plt.figure(figsize=(12, 5))
    plt.plot(recent["date"], recent["inflow"], label="Поступления факт", alpha=0.75)
    plt.plot(recent["date"], recent["outflow"], label="Списания факт", alpha=0.75)
    plt.plot(forecast_dates, forecast["predicted_inflow"], label="Поступления прогноз", linewidth=2)
    plt.plot(forecast_dates, forecast["predicted_outflow"], label="Списания прогноз", linewidth=2)
    plt.title("Прогноз дневного Cash Flow на 14 дней")
    plt.ylabel("Рубли")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_ROOT / "cashflow_forecast_14d.png", dpi=180)
    plt.close()

    recent_anom = daily_anom.tail(120)
    plt.figure(figsize=(12, 5))
    plt.plot(recent_anom["date"], recent_anom["inflow"], label="Поступления", linewidth=1.5)
    marked = recent_anom.loc[recent_anom["is_daily_inflow_anomaly"]]
    plt.scatter(marked["date"], marked["inflow"], color="crimson", label="Аномальные дни", zorder=3)
    plt.title("Детектор аномалий дневных поступлений")
    plt.ylabel("Рубли")
    plt.grid(alpha=0.25)
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIGURE_ROOT / "daily_inflow_anomalies.png", dpi=180)
    plt.close()

    plt.figure(figsize=(12, 5))
    plt.bar(forecast_dates, forecast["projected_balance_delta_from_last_fact"])
    plt.axhline(0, color="black", linewidth=1)
    plt.title("Прогноз изменения остатка от последнего факта")
    plt.ylabel("Рубли")
    plt.grid(axis="y", alpha=0.25)
    plt.tight_layout()
    plt.savefig(FIGURE_ROOT / "cashflow_balance_delta_14d.png", dpi=180)
    plt.close()


def write_markdown_report(returns_summary: dict, cashflow_summary: dict) -> None:
    retrain_needed = bool(
        returns_summary["drift_flag"]
        or any(model["drift_flag"] for model in cashflow_summary["models"].values())
        or cashflow_summary["recent_daily_inflow_anomalies_30d"] >= 3
    )
    status = {
        "generated_at": pd.Timestamp.now().isoformat(timespec="seconds"),
        "retrain_recommended": retrain_needed,
        "returns": returns_summary,
        "cashflow": cashflow_summary,
    }
    (OUTPUT_ROOT / "retraining_status.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    top_returns = pd.DataFrame(returns_summary["top_forecast_rows"])
    top_returns_md = markdown_table(
        top_returns[
            ["week", "product_name", "brand", "predicted_return_qty", "predicted_return_rate_qty"]
        ],
        float_digits=2,
    )
    cash_models_md = markdown_table(pd.DataFrame(
        [
            {"target": target, **payload}
            for target, payload in cashflow_summary["models"].items()
        ]
    ), float_digits=3)

    report = f"""# Прогнозные модели: возвраты, Cash Flow и аномалии

Дата последнего факта по продажам: `{returns_summary["last_fact_week"]}`.  
Дата последнего факта по банку: `{cashflow_summary["last_fact_date"]}`.

## 1. Прогноз возвратов

Рабочая модель выбрана по rolling-origin validation, без перемешивания будущего и прошлого.
Победитель: **{returns_summary["best_model"]}**.

- CV WAPE: **{returns_summary["cv_mean_wape"]:.3f}**
- CV MAE: **{returns_summary["cv_mean_mae"]:.1f} шт.**
- WAPE на последних 4 неделях: **{returns_summary["recent_4w_wape"]:.3f}**
- Прогноз возвратов на 4 недели: **{returns_summary["forecast_total_qty_4w"]:.0f} шт.**
- Флаг разладки: **{"да" if returns_summary["drift_flag"] else "нет"}**

Топ прогнозируемых возвратов:

{top_returns_md}

## 2. Прогноз дневного Cash Flow

Поступления и списания прогнозируются отдельными временными рядами, затем собираются в
`net_cash_flow = inflow - outflow`. Абсолютный остаток на счёте требует фактический остаток
из банка; текущий прогноз считает изменение остатка от последнего факта.

{cash_models_md}

На горизонте 14 дней:

- прогноз поступлений: **{cashflow_summary["forecast_inflow_14d"]:,.0f} руб.**
- прогноз списаний: **{cashflow_summary["forecast_outflow_14d"]:,.0f} руб.**
- прогноз net cash flow: **{cashflow_summary["forecast_net_14d"]:,.0f} руб.**

## 3. Детектор аномалий поступлений

Детектор работает на уровне входящих транзакций и дневных сумм: robust z-score по истории
контрагента, редкость контрагента, нетипичный интервал между платежами и IsolationForest.

- найдено транзакций на проверку: **{cashflow_summary["inflow_anomaly_count"]}**
- аномальных дней поступлений за последние 30 дней: **{cashflow_summary["recent_daily_inflow_anomalies_30d"]}**

## 4. Самостоятельное переобучение и разладка

Скрипт каждый запуск переобучает модели на всех доступных данных и пишет
`outputs/returns_cashflow/retraining_status.json`. В продуктовой эксплуатации его можно запускать
по расписанию: возвраты раз в неделю, cash flow и аномалии ежедневно после загрузки выписки.

Триггер переобучения/проверки включается, если свежий WAPE превышает CV WAPE более чем на 35%
или если за последний месяц появляется несколько аномальных дней поступлений.

Итоговый статус: **{"нужно проверить/переобучить" if retrain_needed else "разладки не видно"}**.

## 5. Артефакты

- `outputs/returns_cashflow/returns_forecast_next_4_weeks.csv`
- `outputs/returns_cashflow/cashflow_forecast_next_14_days.csv`
- `outputs/returns_cashflow/inflow_transaction_anomalies.csv`
- `figures/returns_cashflow/returns_forecast_4w.png`
- `figures/returns_cashflow/returns_top_risk.png`
- `figures/returns_cashflow/cashflow_forecast_14d.png`
- `figures/returns_cashflow/daily_inflow_anomalies.png`
- `figures/returns_cashflow/cashflow_balance_delta_14d.png`
"""
    (OUTPUT_ROOT / "modeling_report.md").write_text(report, encoding="utf-8")


def main() -> None:
    ensure_dirs()
    returns_summary = train_returns_model()
    cashflow_summary = train_cashflow_models()
    write_markdown_report(returns_summary, cashflow_summary)
    print("Done.")
    print(f"Report: {OUTPUT_ROOT / 'modeling_report.md'}")
    print(f"Retraining status: {OUTPUT_ROOT / 'retraining_status.json'}")


if __name__ == "__main__":
    main()
