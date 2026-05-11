from __future__ import annotations

import argparse
import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


DATASET_BASENAME = "bank_statement_transactions"
STRING_COLUMNS = [
    "source_file",
    "source_file_path",
    "source_file_hash",
    "source_sheet",
    "document_number",
    "direction",
    "counterparty_name",
    "counterparty_inn",
    "counterparty_kpp",
    "counterparty_account",
    "counterparty_bik",
    "counterparty_bank_name",
    "payment_purpose",
    "debtor_code",
    "document_type",
]


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

    def discover_xlsx_files(self, source_dir: Path) -> list[Path]:
        if not source_dir.exists():
            raise FileNotFoundError(f"Папка с исходными файлами не найдена: {source_dir}")

        return sorted(
            path
            for path in source_dir.glob("*.xlsx")
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
    @staticmethod
    def clean(value) -> str | None:
        if pd.isna(value):
            return None
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        text = str(value).strip()
        return re.sub(r"\s+", " ", text) or None

    @staticmethod
    def parse_ru_date(value) -> pd.Timestamp:
        text = TextParser.clean(value)
        if not text:
            return pd.NaT
        return pd.to_datetime(text, format="%d.%m.%Y", errors="coerce")

    @staticmethod
    def parse_amount(value) -> float:
        if pd.isna(value):
            return 0.0
        return float(value)


class BankStatementParser:
    SHEET_NAME = "Выписка по счёту"

    COLUMNS = {
        0: "operation_date",
        1: "document_number",
        2: "debit",
        3: "credit",
        4: "counterparty_name",
        5: "counterparty_inn",
        6: "counterparty_kpp",
        7: "counterparty_account",
        8: "counterparty_bik",
        9: "counterparty_bank_name",
        10: "payment_purpose",
        11: "debtor_code",
        12: "document_type",
    }

    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root

    def parse_file(self, path: Path, source_file_hash: str) -> tuple[pd.DataFrame, dict]:
        raw = pd.read_excel(path, sheet_name=0, header=None, engine="openpyxl")
        source_file_path = path.resolve().relative_to(self.project_root.resolve()).as_posix()
        source_sheet = self._sheet_name(path)
        operation_start_idx = self._find_operation_start(raw)
        header_info = self._parse_header_info(raw)

        rows = []
        for row_idx in range(operation_start_idx, len(raw)):
            row = raw.iloc[row_idx]
            operation_date = TextParser.parse_ru_date(row.iat[0])
            if pd.isna(operation_date):
                continue

            debit = TextParser.parse_amount(row.iat[2])
            credit = TextParser.parse_amount(row.iat[3])
            if debit == 0 and credit == 0:
                continue

            amount = credit - debit
            direction = "credit" if credit > 0 else "debit"

            record = {
                "source_file": path.name,
                "source_file_path": source_file_path,
                "source_file_hash": source_file_hash,
                "source_sheet": source_sheet,
                "source_row_number": row_idx + 1,
                "operation_date": operation_date,
                "document_number": TextParser.clean(row.iat[1]),
                "debit": debit,
                "credit": credit,
                "amount": amount,
                "direction": direction,
            }
            for column_idx, column_name in self.COLUMNS.items():
                if column_name in record or column_name == "operation_date":
                    continue
                record[column_name] = TextParser.clean(row.iat[column_idx])
            rows.append(record)

        df = self._finalize(pd.DataFrame(rows))
        validation = self._validate_against_header(df, header_info, source_file_path)
        return df, validation

    @staticmethod
    def _sheet_name(path: Path) -> str:
        excel_file = pd.ExcelFile(path, engine="openpyxl")
        return excel_file.sheet_names[0]

    @staticmethod
    def _find_operation_start(raw: pd.DataFrame) -> int:
        for row_idx in range(len(raw)):
            if pd.notna(TextParser.parse_ru_date(raw.iat[row_idx, 0])):
                return row_idx
        raise ValueError("Не найдена первая строка операций с датой в первой колонке.")

    @staticmethod
    def _parse_header_info(raw: pd.DataFrame) -> dict:
        return {
            "header_debit_turnover": TextParser.parse_amount(raw.iat[6, 4]),
            "header_credit_turnover": TextParser.parse_amount(raw.iat[7, 4]),
        }

    @staticmethod
    def _validate_against_header(df: pd.DataFrame, header_info: dict, source_file_path: str) -> dict:
        debit_total = round(float(df["debit"].sum()), 2) if not df.empty else 0.0
        credit_total = round(float(df["credit"].sum()), 2) if not df.empty else 0.0
        header_debit = round(float(header_info["header_debit_turnover"]), 2)
        header_credit = round(float(header_info["header_credit_turnover"]), 2)

        if debit_total != header_debit or credit_total != header_credit:
            raise ValueError(
                "Суммы операций не совпали с оборотами в шапке файла "
                f"{source_file_path}: debit {debit_total} != {header_debit}, "
                f"credit {credit_total} != {header_credit}"
            )

        return {
            "source_file_path": source_file_path,
            "rows": len(df),
            "debit_total": debit_total,
            "credit_total": credit_total,
            "header_debit_turnover": header_debit,
            "header_credit_turnover": header_credit,
        }

    @staticmethod
    def _finalize(df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df

        columns = [
            "operation_date",
            "document_number",
            "debit",
            "credit",
            "amount",
            "direction",
            "counterparty_name",
            "counterparty_inn",
            "counterparty_kpp",
            "counterparty_account",
            "counterparty_bik",
            "counterparty_bank_name",
            "payment_purpose",
            "debtor_code",
            "document_type",
            "source_file",
            "source_file_path",
            "source_file_hash",
            "source_sheet",
            "source_row_number",
        ]
        df = df[columns].copy()
        for column in STRING_COLUMNS:
            df[column] = df[column].astype("string")
        return df


class DatasetStore:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config

    def load_existing(self) -> pd.DataFrame:
        if not self.config.csv_path.exists():
            return pd.DataFrame()

        return pd.read_csv(
            self.config.csv_path,
            parse_dates=["operation_date"],
            dtype={column: "string" for column in STRING_COLUMNS},
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
            ["operation_date", "source_file_path", "source_row_number"],
            ascending=[True, True, True],
            kind="stable",
        ).reset_index(drop=True)


class BankStatementPipeline:
    def __init__(self, config: PipelineConfig) -> None:
        self.config = config
        self.registry = FileRegistry(config.project_root)
        self.parser = BankStatementParser(config.project_root)
        self.store = DatasetStore(config)

    def run(self) -> dict:
        existing = pd.DataFrame() if self.config.rebuild else self.store.load_existing()
        files = self.registry.discover_xlsx_files(self.config.source_dir)

        existing_hashes = set(existing["source_file_hash"].dropna()) if not existing.empty else set()
        existing_paths = set(existing["source_file_path"].dropna()) if not existing.empty else set()

        parsed_frames = []
        processed_files = []
        skipped_files = []
        validations = []

        working_existing = existing.copy()
        for path in files:
            source_hash = self.registry.file_hash(path)
            source_rel_path = self.registry.relative_path(path)

            if source_hash in existing_hashes:
                skipped_files.append(source_rel_path)
                continue

            if source_rel_path in existing_paths and not working_existing.empty:
                working_existing = working_existing[working_existing["source_file_path"] != source_rel_path]

            parsed_frame, validation = self.parser.parse_file(path, source_hash)
            parsed_frames.append(parsed_frame)
            processed_files.append(source_rel_path)
            validations.append(validation)

        frames = [frame for frame in [working_existing, *parsed_frames] if not frame.empty]
        result = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

        self.store.save(result)

        return {
            "source_files_found": len(files),
            "processed_files_count": len(processed_files),
            "skipped_files_count": len(skipped_files),
            "processed_files": processed_files,
            "skipped_files": skipped_files,
            "validations": validations,
            "rows_total": len(result),
            "debit_total": float(result["debit"].sum()) if not result.empty else 0.0,
            "credit_total": float(result["credit"].sum()) if not result.empty else 0.0,
            "amount_total": float(result["amount"].sum()) if not result.empty else 0.0,
            "csv_path": str(self.config.csv_path),
            "xlsx_path": str(self.config.xlsx_path),
            "parquet_path": str(self.config.parquet_path),
        }


def default_project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_source_dir(project_root: Path) -> Path:
    return project_root / "Данные" / "Выписки и данные"


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    project_root = default_project_root()
    parser = argparse.ArgumentParser(
        description="Парсит банковские выписки Альфа-Банка в единую таблицу операций."
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

    summary = BankStatementPipeline(config).run()

    print("Готово.")
    print(f"Найдено исходных файлов: {summary['source_files_found']}")
    print(f"Обработано новых/измененных файлов: {summary['processed_files_count']}")
    print(f"Пропущено уже обработанных файлов: {summary['skipped_files_count']}")
    print(f"Строк в итоговой таблице: {summary['rows_total']}")
    print(f"Сумма debit: {summary['debit_total']:,.2f}")
    print(f"Сумма credit: {summary['credit_total']:,.2f}")
    print(f"Сумма amount: {summary['amount_total']:,.2f}")
    print(f"CSV: {summary['csv_path']}")
    print(f"Excel: {summary['xlsx_path']}")
    print(f"Parquet: {summary['parquet_path']}")

    if summary["validations"]:
        print("\nСверки по обработанным файлам:")
        for validation in summary["validations"]:
            print(
                f"- {validation['source_file_path']}: "
                f"rows={validation['rows']}, "
                f"debit={validation['debit_total']:,.2f}, "
                f"credit={validation['credit_total']:,.2f}"
            )

    if summary["processed_files"]:
        print("\nОбработанные файлы:")
        for file in summary["processed_files"]:
            print(f"- {file}")


if __name__ == "__main__":
    main()
