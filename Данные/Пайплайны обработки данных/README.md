# Пайплайны обработки данных

В этой папке лежат скрипты, которые превращают исходные Excel-отчеты из папки `Данные` в аналитические таблицы.

## Установка зависимостей

```bash
python3 -m pip install -r "Данные/Пайплайны обработки данных/requirements.txt"
```

## Пайплайны

| Пайплайн | Что обрабатывает | Код | Итоговые данные | Описание таблицы |
|---|---|---|---|---|
| `sales_by_counterparties` | Продажи по контрагентам | [sales_by_counterparties_pipeline.py](sales_by_counterparties_pipeline.py) | [Parquet](../Итоговые%20таблицы/sales_by_counterparties.parquet), [CSV](../Итоговые%20таблицы/sales_by_counterparties.csv), [XLSX](../Итоговые%20таблицы/sales_by_counterparties.xlsx) | [sales_by_counterparties.md](../Итоговые%20таблицы/sales_by_counterparties.md) |
| `sales_by_payment_counterparties` | Продажи по контрагентам по оплате | [sales_by_payment_counterparties_pipeline.py](sales_by_payment_counterparties_pipeline.py) | [Parquet](../Итоговые%20таблицы/sales_by_payment_counterparties.parquet), [CSV](../Итоговые%20таблицы/sales_by_payment_counterparties.csv), [XLSX](../Итоговые%20таблицы/sales_by_payment_counterparties.xlsx) | [sales_by_payment_counterparties.md](../Итоговые%20таблицы/sales_by_payment_counterparties.md) |
| `bank_statement_transactions` | Банковские выписки | [bank_statement_transactions_pipeline.py](bank_statement_transactions_pipeline.py) | [Parquet](../Итоговые%20таблицы/bank_statement_transactions.parquet), [CSV](../Итоговые%20таблицы/bank_statement_transactions.csv), [XLSX](../Итоговые%20таблицы/bank_statement_transactions.xlsx) | [bank_statement_transactions.md](../Итоговые%20таблицы/bank_statement_transactions.md) |

## Запуск

Обычный запуск обновляет итоговую таблицу только новыми или измененными файлами:

```bash
python3 "Данные/Пайплайны обработки данных/sales_by_counterparties_pipeline.py"
python3 "Данные/Пайплайны обработки данных/sales_by_payment_counterparties_pipeline.py"
python3 "Данные/Пайплайны обработки данных/bank_statement_transactions_pipeline.py"
```

Полная пересборка:

```bash
python3 "Данные/Пайплайны обработки данных/sales_by_counterparties_pipeline.py" --rebuild
python3 "Данные/Пайплайны обработки данных/sales_by_payment_counterparties_pipeline.py" --rebuild
python3 "Данные/Пайплайны обработки данных/bank_statement_transactions_pipeline.py" --rebuild
```

Подробное описание алгоритмов всех пайплайнов: [PIPELINES.md](PIPELINES.md).

## Описание итоговых таблиц

- [sales_by_counterparties.md](../Итоговые%20таблицы/sales_by_counterparties.md) - описание таблицы продаж по контрагентам.
- [sales_by_payment_counterparties.md](../Итоговые%20таблицы/sales_by_payment_counterparties.md) - описание таблицы оплат по контрагентам.
- [bank_statement_transactions.md](../Итоговые%20таблицы/bank_statement_transactions.md) - описание таблицы банковских операций.
