"""
Адаптер существующего пайплайна `sales_by_payment_counterparties_pipeline.py`
для программного вызова из Django (см. tech_spec.md, раздел 6.3).
"""

from __future__ import annotations

import importlib.util
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_PIPELINE_PATH = (
    Path(__file__).resolve().parents[3]
    / "Данные"
    / "Пайплайны обработки данных"
    / "sales_by_payment_counterparties_pipeline.py"
)


def _load_original_module():
    spec = importlib.util.spec_from_file_location(
        "sales_by_payment_counterparties_pipeline", _PIPELINE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_original = _load_original_module()
FileRegistry = _original.FileRegistry
SalesByPaymentReportParser = _original.SalesByPaymentReportParser


@dataclass
class ProcessResult:
    parquet_path: str
    row_count: int
    amount_total: float
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    period_start: "pd.Timestamp | None" = None
    period_end: "pd.Timestamp | None" = None
    source_filename: str = ""
    source_sha256: str = ""


def process_file(source_path: Path, output_dir: Path) -> ProcessResult:
    source_path = Path(source_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    project_root = source_path.parent
    sha256 = FileRegistry.file_hash(source_path)
    parser = SalesByPaymentReportParser(project_root=project_root)

    warnings: list[str] = []
    errors: list[str] = []

    try:
        df = parser.parse_file(source_path, source_file_hash=sha256)
    except Exception as exc:
        errors.append(f"Не удалось разобрать файл: {exc}")
        df = pd.DataFrame()

    if df.empty and not errors:
        errors.append("В файле не найдено ни одной строки оплат известного формата.")

    if not df.empty:
        df["source_file_path"] = source_path.name

        future_mask = df["payment_date"] > pd.Timestamp.now().normalize()
        future_count = int(future_mask.sum())
        if future_count:
            warnings.append(
                f"{future_count} строк с датой оплаты в будущем относительно момента загрузки."
            )

        if df["amount"].isna().any() or not df["amount"].abs().lt(float("inf")).all():
            errors.append("В сумме оплат обнаружены некорректные значения (NaN/Inf).")

    parquet_path = output_dir / f"{source_path.stem}.parquet"
    if not df.empty:
        df.to_parquet(parquet_path, index=False)

    period_start = df["payment_date"].min() if not df.empty else None
    period_end = df["payment_date"].max() if not df.empty else None

    return ProcessResult(
        parquet_path=str(parquet_path) if not df.empty else "",
        row_count=int(len(df)),
        amount_total=float(df["amount"].sum()) if not df.empty else 0.0,
        warnings=warnings,
        errors=errors,
        period_start=period_start,
        period_end=period_end,
        source_filename=source_path.name,
        source_sha256=sha256,
    )


def dataframe_from_result(result: ProcessResult) -> pd.DataFrame:
    if not result.parquet_path:
        return pd.DataFrame()
    return pd.read_parquet(result.parquet_path)
