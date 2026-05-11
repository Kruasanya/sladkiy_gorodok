# Итоговые таблицы

Эта папка хранит готовые аналитические таблицы, которые создаются пайплайнами из папки `Данные/Пайплайны обработки данных`.

## Форматы

Для каждой таблицы пайплайн сохраняет три формата:

- `.parquet` - основной формат для анализа в pandas. Он быстрее CSV, компактнее и лучше сохраняет типы данных.
- `.csv` - текстовый формат для совместимости и быстрой проверки.
- `.xlsx` - Excel-версия для просмотра руками.

Для работы в pandas лучше использовать Parquet:

```python
import pandas as pd

df = pd.read_parquet("Данные/Итоговые таблицы/bank_statement_transactions.parquet")
```

## Таблицы

| Таблица | Что внутри | Основной файл | Описание |
|---|---|---|---|
| `sales_by_counterparties` | Продажи по контрагентам и номенклатуре | `sales_by_counterparties.parquet` | [sales_by_counterparties.md](sales_by_counterparties.md) |
| `sales_by_payment_counterparties` | Оплаты по контрагентам | `sales_by_payment_counterparties.parquet` | [sales_by_payment_counterparties.md](sales_by_payment_counterparties.md) |
| `bank_statement_transactions` | Операции банковской выписки | `bank_statement_transactions.parquet` | [bank_statement_transactions.md](bank_statement_transactions.md) |

## Служебные поля

Во всех таблицах поля `source_*` находятся в конце. Они нужны, чтобы понимать происхождение строки и поддерживать инкрементальную обработку:

- `source_file`
- `source_file_path`
- `source_file_hash`
- `source_sheet`
- `source_row_number`

В некоторых таблицах есть дополнительные `source_*` поля, например колонка исходного отчета.
