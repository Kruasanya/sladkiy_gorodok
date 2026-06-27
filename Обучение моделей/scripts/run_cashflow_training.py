#!/usr/bin/env python3
"""Запускает обучение моделей дневного Cash Flow и сохраняет артефакты в artifacts/returns_cashflow.

Загружает train_returns_cashflow_models.py под фиксированным именем модуля
"train_returns_cashflow_models", чтобы классы (HurdleExpectedValueModel и т.п.)
сохранялись в joblib с этим же module-путём — это нужно, чтобы backend
(kloduchet/backend/apps/banking/cashflow_adapter.py) мог десериализовать модели,
загрузив скрипт под тем же именем модуля.
"""

import importlib.util
import sys
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parent / "train_returns_cashflow_models.py"
MODULE_NAME = "train_returns_cashflow_models"


def load_module():
    spec = importlib.util.spec_from_file_location(MODULE_NAME, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


if __name__ == "__main__":
    module = load_module()
    module.ensure_dirs()
    module.train_cashflow_models()
    print("Cash Flow models trained and saved to artifacts/returns_cashflow/.")
