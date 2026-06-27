"""Общие построчные проверки для адаптеров импорта (продажи, оплаты, банк)."""

from __future__ import annotations

import pandas as pd


def validate_rows(df: pd.DataFrame, *, required_fields=(), amount_fields=(), date_fields=()) -> list[str]:
    """Проверяет обязательные поля, суммы и даты построчно.

    Возвращает список ошибок с номером строки источника и причиной.
    """
    errors: list[str] = []
    if df.empty:
        return errors

    row_numbers = df["source_row_number"] if "source_row_number" in df.columns else df.index + 1

    for idx, row_no in zip(df.index, row_numbers):
        row = df.loc[idx]

        for field in required_fields:
            value = row.get(field)
            if value is None or pd.isna(value) or (isinstance(value, str) and not value.strip()):
                errors.append(f"Строка {row_no}: не заполнено обязательное поле «{field}».")

        for field in amount_fields:
            value = row.get(field)
            if value is None or pd.isna(value) or (isinstance(value, float) and not abs(value) < float("inf")):
                errors.append(f"Строка {row_no}: некорректное значение суммы в поле «{field}».")

        for field in date_fields:
            value = row.get(field)
            if value is None or pd.isna(value):
                errors.append(f"Строка {row_no}: не заполнена или некорректна дата в поле «{field}».")

    return errors
