# Исследование разметки банковских операций

Папка содержит исследовательский ноутбук по классификации банковских операций и построению управленческого Cash Flow для проекта финансового аудита малого производственного бизнеса.

## Главные файлы

- `01_Исследование_классификации_банковских_операций.ipynb` — основной notebook: даты, дубли, категории, rule-based, LM Studio, validation sample, Cash Flow, графики и выводы.
- `00_Обзор_структуры_данных.ipynb` — первичный обзор источников.
- `02_План_и_выводы.md` — краткий план исследования и текущие выводы.
- `outputs/manual_validation_500.xlsx` — файл для ручной проверки 500 операций.

## Что изменено в новой версии

- Старые пересекающиеся категории заменены на 17 строгих укрупнённых категорий.
- Детализация вынесена в `subcategory`, чтобы не смешивать категории и подкатегории.
- Добавлена проверка целостности `CATEGORIES`, `CATEGORY_GROUPS` и допустимости категорий для `credit/debit`.
- Исправлен парсинг дат: после обработки `date = NaT` больше не появляется для реальных операций.
- Усилен rule-based классификатор: отдельно ловятся бухгалтерия, сырьё/ингредиенты, упаковка, комиссии, кредиты, возвраты.
- LM Studio подключается как сравнимый вариант и использует строгий prompt с JSON-ответом.
- Создана ручная валидационная выборка `manual_validation_500.csv/.xlsx`.
- Cash Flow пересобран так, чтобы внутренние переводы не искажали операционный денежный поток.

## Основные outputs

- `outputs/cleaned_bank_operations.csv`
- `outputs/classified_bank_operations.csv`
- `outputs/cash_flow_by_month.csv`
- `outputs/category_summary.csv`
- `outputs/manual_validation_500.csv`
- `outputs/manual_validation_500.xlsx`
- `outputs/rows_with_missing_dates.csv`
- `outputs/classification_disagreements.csv`
- `outputs/operations_for_manual_review.csv`
- `outputs/category_quality_report.csv`

## Как валидировать качество

1. Откройте `outputs/manual_validation_500.xlsx`.
2. Заполните `category_manual`, `subcategory_manual`, при необходимости `comment_manual`.
3. Сохраните копию как `outputs/manual_validation_500_labeled.xlsx`.
4. Перезапустите блок оценки качества в notebook.
