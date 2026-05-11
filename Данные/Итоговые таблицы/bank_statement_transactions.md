# Итоговая таблица `bank_statement_transactions`

Файлы:

- `bank_statement_transactions.csv`
- `bank_statement_transactions.xlsx`
- `bank_statement_transactions.parquet`

Источник: Excel-выписки из папки `Данные/Выписки и данные`.

Гранулярность таблицы: **одна строка = одна банковская операция из табличной части выписки**.

## Как собирается таблица

Исходный Excel имеет один лист `Выписка по счёту`:

1. сверху находится шапка выписки с реквизитами счёта, периодом, остатками и оборотами;
2. строка заголовков начинается с колонок `Дата`, `Номер документа`, `Дебет`, `Кредит`;
3. операции начинаются сразу после второй строки заголовка.

Пайплайн берет только строки операций:

- дата операции берется из колонки `Дата`;
- `debit` и `credit` заполняются нулями, если в исходной ячейке пусто;
- `amount` считается как `credit - debit`: поступления положительные, списания отрицательные;
- `direction` принимает значение `credit` или `debit`;
- шапка выписки не попадает в итоговую таблицу, но обороты из нее используются для сверки.

## Поля таблицы

| Поле | Тип | Описание |
|---|---|---|
| `operation_date` | date | Дата операции. |
| `document_number` | string | Номер документа. |
| `debit` | float | Сумма списания. |
| `credit` | float | Сумма поступления. |
| `amount` | float | Аналитическая сумма: `credit - debit`. |
| `direction` | string | Направление операции: `credit` или `debit`. |
| `counterparty_name` | string | Наименование контрагента. |
| `counterparty_inn` | string | ИНН контрагента. |
| `counterparty_kpp` | string | КПП контрагента. |
| `counterparty_account` | string | Расчетный счет контрагента. |
| `counterparty_bik` | string | БИК банка контрагента. |
| `counterparty_bank_name` | string | Наименование банка контрагента. |
| `payment_purpose` | string | Назначение платежа. |
| `debtor_code` | string | Код дебитора из выписки. |
| `document_type` | string | Тип документа. |
| `source_file` | string | Имя исходного Excel-файла. |
| `source_file_path` | string | Относительный путь к исходному файлу внутри проекта. |
| `source_file_hash` | string | SHA-256 хэш исходного файла. Используется для инкрементальной обработки. |
| `source_sheet` | string | Имя листа-источника. |
| `source_row_number` | integer | Номер строки операции в исходном Excel, начиная с 1. |

## Проверки качества

Для каждого нового или измененного файла пайплайн сверяет:

- сумму `debit` по операциям с полем `Обороты дебет` в шапке;
- сумму `credit` по операциям с полем `Обороты кредит` в шапке.

Если суммы не совпадают, пайплайн останавливается с ошибкой.

Реквизиты, номера документов, ИНН, КПП, счета и БИК сохраняются как строковые поля. При ручном чтении CSV в pandas лучше явно задавать `dtype=str` для этих колонок, если важно сохранить ведущие нули.

## Пример запросов

Денежный поток по дням:

```sql
select operation_date, sum(debit) as debit, sum(credit) as credit, sum(amount) as net_amount
from bank_statement_transactions
group by operation_date
order by operation_date;
```

Поступления по контрагентам:

```sql
select counterparty_name, sum(credit) as credit
from bank_statement_transactions
where direction = 'credit'
group by counterparty_name
order by credit desc;
```

Списания по типам документов:

```sql
select document_type, sum(debit) as debit
from bank_statement_transactions
where direction = 'debit'
group by document_type
order by debit desc;
```
