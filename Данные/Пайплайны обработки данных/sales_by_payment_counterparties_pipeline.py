from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


DATASET_BASENAME = "sales_by_payment_counterparties"


@dataclass(frozen=True)
class PipelineConfig:
    project_root: Path
    source_dir: Path
    output_dir: Path
    dataset_basename: str = DATASET_BASENAME
    rebuild: bool = False

    @property
    def csv_path(self) -> Path:
        return self.output_dir / f"{self.dataset_basename}.csv"

    @property
    def xlsx_path(self) -> Path:
        return self.output_dir / f"{self.dataset_basename}.xlsx"

    @property
    def parquet_path(self) -> Path:
        return self.output_dir / f"{self.dataset_basename}.parquet"


class DependencyChecker:
    REQUIRED_IMPORTS = {
        "pandas": "pandas",
        "xlrd": "xlrd",
        "openpyxl": "openpyxl",
        "pyarrow": "pyarrow",
    }

    @classmethod
    def ensure_available(cls) -> None:
        missing = []
        for package_name, import_name in cls.REQUIRED_IMPORTS.items():
            try:
                __import__(import_name)
            except ImportError:
                missing.append(package_name)

        if missing:
            packages = " ".join(missing)
            raise SystemExit(
                "Не хватает Python-пакетов: "
                f"{packages}\nУстанови их командой:\n"
                f"{sys.executable} -m pip install {packages}"
            )


class FileRegistry:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def discover_xls_files(self, source_dir: Path) -> list[Path]:
        if not source_dir.exists():
            raise FileNotFoundError(f"Папка с исходными файлами не найдена: {source_dir}")

        return sorted(
            path
            for path in source_dir.glob("*.xls")
            if path.is_file() and not path.name.startswith("~$")
        )

    def relative_path(self, path: Path) -> str:
        return path.resolve().relative_to(self.project_root.resolve()).as_posix()

    @staticmethod
    def file_hash(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()


class TextParser:
    DATE_PATTERN = r"\d{2}\.\d{2}\.\d{4}"

    @staticmethod
    def clean(value) -> str | None:
        if pd.isna(value):
            return None
        text = str(value).strip()
        return re.sub(r"\s+", " ", text) or None

    @staticmethod
    def parse_column_date(value) -> pd.Timestamp | None:
        text = TextParser.clean(value)
        if not text:
            return None
        return pd.to_datetime(text, format="%d.%m.%y", errors="coerce")

    @staticmethod
    def parse_ru_date(value: str | None) -> pd.Timestamp:
        if not value:
            return pd.NaT
        return pd.to_datetime(value, format="%d.%m.%Y", errors="coerce")

    @staticmethod
    def is_payment_doc(value: str | None) -> bool:
        text = TextParser.clean(value)
        return bool(text and text.startswith("Поступление на расчетный счет"))

    @staticmethod
    def is_contract(value: str | None) -> bool:
        text = TextParser.clean(value)
        return bool(text and re.search(rf"\s+от\s+({TextParser.DATE_PATTERN})$", text))

    @staticmethod
    def parse_contract(contract_raw: str | None) -> dict:
        contract_raw = TextParser.clean(contract_raw)
        if not contract_raw:
            return {"contract_number": None, "contract_date": pd.NaT}

        match = re.search(rf"\s+от\s+({TextParser.DATE_PATTERN})$", contract_raw)
        if not match:
            return {"contract_number": contract_raw, "contract_date": pd.NaT}

        return {
            "contract_number": contract_raw[: match.start()].strip(),
            "contract_date": TextParser.parse_ru_date(match.group(1)),
        }

    @staticmethod
    def parse_payment_doc(payment_doc_raw: str | None) -> dict:
        payment_doc_raw = TextParser.clean(payment_doc_raw)
        if not payment_doc_raw:
            return {"payment_doc_number": None, "payment_doc_date": pd.NaT}

        match = re.search(rf"№\s*([^\s]+)\s+от\s+({TextParser.DATE_PATTERN})", payment_doc_raw)
        if not match:
            return {"payment_doc_number": None, "payment_doc_date": pd.NaT}

        return {
            "payment_doc_number": match.group(1),
            "payment_doc_date": TextParser.parse_ru_date(match.group(2)),
        }

    @staticmethod
    def parse_counterparty(counterparty_raw: str | None) -> dict:
        counterparty_raw = TextParser.clean(counterparty_raw)
        result = {
            "legal_entity": None,
            "brand": None,
            "store_location_raw": None,
            "city_or_area": None,
        }
        if not counterparty_raw:
            return result

        if "Магазин Светофор" in counterparty_raw:
            left, location = counterparty_raw.split("Магазин Светофор", 1)
            result["legal_entity"] = left.strip()
            result["brand"] = "Светофор"
            result["store_location_raw"] = location.strip(" ,") or None
        elif "Магазин Маяк" in counterparty_raw:
            left, location = counterparty_raw.split("Магазин Маяк", 1)
            result["legal_entity"] = left.strip().strip(",")
            result["brand"] = "Маяк"
            result["store_location_raw"] = location.strip(" ,") or None
        else:
            result["legal_entity"] = counterparty_raw

        location = result["store_location_raw"] or ""
        city_match = re.search(r"((?:г\.|рп\.|пгт|с\.)\s*[^,]+)", location)
        if city_match:
            result["city_or_area"] = city_match.group(1).strip()

        return result


class PeriodParser:
    MONTHS = {
        "Январь": 1,
        "Февраль": 2,
        "Март": 3,
        "Апрель": 4,
        "Май": 5,
        "Июнь": 6,
        "Июль": 7,
        "Август": 8,
        "Сентябрь": 9,
        "Октябрь": 10,
        "Ноябрь": 11,
        "Декабрь": 12,
    }

    QUARTERS = {
        "1 квартал": (1, 3),
        "2 квартал": (4, 6),
        "3 квартал": (7, 9),
        "4 квартал": (10, 12),
    }

    @classmethod
    def parse_from_filename(cls, filename: str) -> dict:
        year_match = re.search(r"(20\d{2})", filename)
        year = int(year_match.group(1)) if year_match else None
        period_label = filename.replace(".xls", "")

        quarter = next((value for key, value in cls.QUARTERS.items() if key in filename), None)
        if year and quarter:
            start_month, end_month = quarter
            return {
                "period_label": period_label,
                "period_start": pd.Timestamp(year=year, month=start_month, day=1),
                "period_end": pd.Timestamp(year=year, month=end_month, day=1) + pd.offsets.MonthEnd(0),
            }

        months = [month for month_name, month in cls.MONTHS.items() if month_name in filename]
        if year and months:
            start_month = min(months)
            end_month = max(months)
            return {
                "period_label": period_label,
                "period_start": pd.Timestamp(year=year, month=start_month, day=1),
                "period_end": pd.Timestamp(year=year, month=end_month, day=1) + pd.offsets.MonthEnd(0),
            }

        return {"period_label": period_label, "period_start": pd.NaT, "period_end": pd.NaT}


class SalesByPaymentReportParser:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def parse_file(self, path: Path, source_file_hash: str) -> pd.DataFrame:
        raw = pd.read_excel(path, sheet_name=0, header=None, engine="xlrd")
        headers = raw.iloc[0].tolist()
        date_columns = {
            col_idx: parsed_date
            for col_idx in range(2, len(headers))
            if (parsed_date := TextParser.parse_column_date(headers[col_idx])) is not None
            and pd.notna(parsed_date)
        }

        period_info = PeriodParser.parse_from_filename(path.name)
        source_file_path = path.resolve().relative_to(self.project_root.resolve()).as_posix()

        rows = []
        i = 3
        while i < len(raw):
            first_cell = TextParser.clean(raw.iat[i, 0])
            if not first_cell or first_cell == "Итого" or first_cell.startswith("*"):
                break

            counterparty_raw = first_cell
            counterparty = TextParser.parse_counterparty(counterparty_raw)

            j = i + 1
            while j < len(raw):
                contract_raw = TextParser.clean(raw.iat[j, 0])
                if (
                    not contract_raw
                    or contract_raw == "Итого"
                    or contract_raw.startswith("*")
                    or not TextParser.is_contract(contract_raw)
                ):
                    break

                contract = TextParser.parse_contract(contract_raw)
                j += 1

                while j < len(raw):
                    payment_doc_raw = TextParser.clean(raw.iat[j, 0])
                    if not TextParser.is_payment_doc(payment_doc_raw):
                        break

                    payment_doc = TextParser.parse_payment_doc(payment_doc_raw)
                    doc_date = payment_doc["payment_doc_date"]

                    for col_idx, column_date in date_columns.items():
                        amount = raw.iat[j, col_idx]
                        if pd.isna(amount) or float(amount) == 0:
                            continue

                        payment_date = column_date
                        if pd.notna(doc_date) and doc_date != column_date:
                            payment_date = doc_date

                        rows.append(
                            {
                                **period_info,
                                "counterparty_raw": counterparty_raw,
                                **counterparty,
                                "contract_raw": contract_raw,
                                **contract,
                                "payment_doc_raw": payment_doc_raw,
                                "payment_doc_number": payment_doc["payment_doc_number"],
                                "payment_date": payment_date,
                                "amount": float(amount),
                                "source_file": path.name,
                                "source_file_path": source_file_path,
                                "source_file_hash": source_file_hash,
                                "source_sheet": "Лист_1",
                                "source_row_number": j + 1,
                                "source_column": headers[col_idx],
                            }
                        )

                    j += 1

            i = j

        return self._finalize(pd.DataFrame(rows))

    @staticmethod
    def _finalize(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        columns = [
            "period_label",
            "period_start",
            "period_end",
            "counterparty_raw",
            "legal_entity",
            "brand",
            "store_location_raw",
            "city_or_area",
            "contract_raw",
            "contract_number",
            "contract_date",
            "payment_doc_raw",
            "payment_doc_number",
            "payment_date",
            "amount",
            "source_file",
            "source_file_path",
            "source_file_hash",
            "source_sheet",
            "source_row_number",
            "source_column",
        ]
        return df[columns]


class DatasetStore:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def load_existing(self) -> pd.DataFrame:
        if not self.config.csv_path.exists():
            return pd.DataFrame()

        return pd.read_csv(
            self.config.csv_path,
            parse_dates=["period_start", "period_end", "contract_date", "payment_date"],
        )

    def save(self, df: pd.DataFrame) -> None:
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

        df = self._sort(df)
        df.to_csv(self.config.csv_path, index=False, encoding="utf-8-sig")
        df.to_excel(self.config.xlsx_path, index=False)
        df.to_parquet(self.config.parquet_path, index=False)

    @staticmethod
    def _sort(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        return df.sort_values(
            [
                "payment_date",
                "source_file_path",
                "counterparty_raw",
                "payment_doc_number",
                "source_row_number",
            ],
            kind="stable",
        ).reset_index(drop=True)


class SalesByPaymentPipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.registry = FileRegistry(config.project_root)
        self.parser = SalesByPaymentReportParser(config.project_root)
        self.store = DatasetStore(config)

    def run(self) -> dict:
        existing = pd.DataFrame() if self.config.rebuild else self.store.load_existing()
        files = self.registry.discover_xls_files(self.config.source_dir)

        existing_hashes = set(existing["source_file_hash"].dropna()) if not existing.empty else set()
        existing_paths = set(existing["source_file_path"].dropna()) if not existing.empty else set()

        parsed_frames = []
        processed_files = []
        skipped_files = []

        working_existing = existing.copy()
        for path in files:
            source_hash = self.registry.file_hash(path)
            source_rel_path = self.registry.relative_path(path)

            if source_hash in existing_hashes:
                skipped_files.append(source_rel_path)
                continue

            if source_rel_path in existing_paths and not working_existing.empty:
                working_existing = working_existing[working_existing["source_file_path"] != source_rel_path]

            parsed_frames.append(self.parser.parse_file(path, source_hash))
            processed_files.append(source_rel_path)

        frames = [frame for frame in [working_existing, *parsed_frames] if not frame.empty]
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        self.store.save(result)

        return {
            "source_files_found": len(files),
            "processed_files_count": len(processed_files),
            "skipped_files_count": len(skipped_files),
            "processed_files": processed_files,
            "skipped_files": skipped_files,
            "rows_total": len(result),
            "amount_total": float(result["amount"].sum()) if not result.empty else 0.0,
            "csv_path": str(self.config.csv_path),
            "xlsx_path": str(self.config.xlsx_path),
            "parquet_path": str(self.config.parquet_path),
        }


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_source_dir(project_root: Path) -> Path:
    preferred = project_root / "Данные" / "Продажи по контрагентам (по оплате)"
    if preferred.exists():
        return preferred
    return project_root / "Продажи по контрагентам (по оплате)"


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    project_root = default_project_root()
    parser = argparse.ArgumentParser(
        description="Парсит Excel-отчеты 'Продажи по контрагентам (по оплате)' в единую таблицу."
    )
    parser.add_argument("--source-dir", type=Path, default=default_source_dir(project_root))
    parser.add_argument("--output-dir", type=Path, default=project_root / "Данные" / "Итоговые таблицы")
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Полностью пересобрать итоговую таблицу из всех исходных файлов.",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> None:
    DependencyChecker.ensure_available()

    args = parse_args(argv)
    project_root = default_project_root()
    config = PipelineConfig(
        project_root=project_root,
        source_dir=args.source_dir.resolve(),
        output_dir=args.output_dir.resolve(),
        rebuild=args.rebuild,
    )

    summary = SalesByPaymentPipeline(config).run()

    print("Готово.")
    print(f"Найдено исходных файлов: {summary['source_files_found']}")
    print(f"Обработано новых/измененных файлов: {summary['processed_files_count']}")
    print(f"Пропущено уже обработанных файлов: {summary['skipped_files_count']}")
    print(f"Строк в итоговой таблице: {summary['rows_total']}")
    print(f"Сумма amount: {summary['amount_total']:,.2f}")
    print(f"CSV: {summary['csv_path']}")
    print(f"Excel: {summary['xlsx_path']}")
    print(f"Parquet: {summary['parquet_path']}")

    if summary["processed_files"]:
        print("\nОбработанные файлы:")
        for file in summary["processed_files"]:
            print(f"- {file}")


if __name__ == "__main__":
    main()
