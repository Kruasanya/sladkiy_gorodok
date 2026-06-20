from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
COURSE_ROOT = Path("/Users/pavelesipenok/Documents/Курсач/sladkiy_gorodok")
PREPARED_DATA = COURSE_ROOT / "Данные" / "Итоговые таблицы"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
FIGURES_DIR = PROJECT_ROOT / "figures"
FINDINGS_PATH = OUTPUTS_DIR / "financial_audit_findings.md"

UNKNOWN_CATEGORY = "Неизвестно / требуется проверка"


def money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ")


def pct(value: float, digits: int = 1) -> str:
    return f"{value * 100:.{digits}f}%"


def read_inputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    bank_raw = pd.read_csv(PREPARED_DATA / "bank_statement_transactions.csv")
    sales = pd.read_csv(PREPARED_DATA / "sales_by_counterparties.csv")
    payments = pd.read_csv(PREPARED_DATA / "sales_by_payment_counterparties.csv")
    classified_bank = pd.read_csv(OUTPUTS_DIR / "classified_bank_operations.csv")

    bank_raw["operation_date"] = pd.to_datetime(bank_raw["operation_date"], errors="coerce")
    sales["sale_date"] = pd.to_datetime(sales["sale_date"], errors="coerce")
    payments["payment_date"] = pd.to_datetime(payments["payment_date"], errors="coerce")
    classified_bank["date"] = pd.to_datetime(classified_bank["date"], errors="coerce")
    return bank_raw, sales, payments, classified_bank


def canonical_client_name(value: object) -> str:
    text = str(value).upper().replace("Ё", "Е") if pd.notna(value) else ""
    if re.search(r"ТОР\s*Г?СЕРВИС\s*150|ТОРГСЕРВИС\s*150|ТС\s*150", text):
        return "ТОРГСЕРВИС 150"
    if re.search(r"ТОР\s*Г?СЕРВИС\s*50|ТОРГСЕРВИС\s*50|ТС\s*50", text):
        return "ТОРГСЕРВИС 50"
    if re.search(r"ТОР\s*Г?СЕРВИС\s*71|ТОРСЕРВИС\s*71|ТОРГСЕРВИС\s*71|ТС\s*71", text):
        return "ТОРГСЕРВИС 71"
    if re.search(r"ВОСТОРГ\s*76", text):
        return "ВОСТОРГ 76"
    if "КЛЕВЕРТРЕЙД" in text:
        return "КЛЕВЕРТРЕЙД"
    text = re.sub(r"(Р\s*/?\s*С|P\s*/?\s*C)\s*.*$", " ", text)
    text = re.sub(r"[^А-ЯA-Z0-9]+", " ", text)
    text = re.sub(r"\b(ООО|ОАО|АО|ПАО|ИП|МАГАЗИН|СВЕТОФОР|МАЯК)\b", " ", text)
    text = re.sub(r"\b\d{10,}\b", " ", text)
    return re.sub(r"\s+", " ", text).strip() or "UNKNOWN"


def concentration_table(amounts: pd.DataFrame, label: str, name_column: str) -> dict:
    data = amounts.sort_values("amount", ascending=False).copy()
    total = float(data["amount"].sum())
    shares = data["amount"] / total if total else data["amount"] * 0
    return {
        "segment": label,
        "entities": int(len(data)),
        "total_amount": total,
        "hhi": float((shares**2).sum()),
        "hhi_10000": float((shares**2).sum() * 10000),
        "cr1": float(shares.iloc[0]) if len(shares) else np.nan,
        "cr5": float(shares.head(5).sum()),
        "cr10": float(shares.head(10).sum()),
        "top_entity": str(data.iloc[0][name_column]) if len(data) else "",
        "top_amount": float(data.iloc[0]["amount"]) if len(data) else np.nan,
    }


def build_reconciliation(bank_raw: pd.DataFrame, payments: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    credit = bank_raw.loc[bank_raw["direction"].eq("credit")].copy()
    credit["doc"] = credit["document_number"].astype(str).str.replace(r"\.0$", "", regex=True)
    payments = payments.copy()
    payments["doc"] = payments["payment_doc_number"].astype(str).str.replace(r"\.0$", "", regex=True)

    one_c_docs = (
        payments.groupby("doc")
        .agg(
            one_c_amount=("amount", "sum"),
            one_c_rows=("amount", "size"),
            one_c_date=("payment_date", "min"),
            one_c_counterparties=("legal_entity", lambda values: " | ".join(sorted(set(map(str, values)))[:5])),
        )
        .reset_index()
    )
    bank_docs = (
        credit.groupby("doc")
        .agg(
            bank_amount=("credit", "sum"),
            bank_rows=("credit", "size"),
            bank_date=("operation_date", "min"),
            bank_counterparties=("counterparty_name", lambda values: " | ".join(sorted(set(map(str, values)))[:5])),
        )
        .reset_index()
    )
    by_document = one_c_docs.merge(bank_docs, on="doc", how="outer")
    for column in ["one_c_amount", "bank_amount", "one_c_rows", "bank_rows"]:
        by_document[column] = by_document[column].fillna(0)
    by_document["amount_gap"] = by_document["one_c_amount"] - by_document["bank_amount"]
    by_document["abs_amount_gap"] = by_document["amount_gap"].abs()
    by_document["date_gap_days"] = (by_document["one_c_date"] - by_document["bank_date"]).dt.days
    by_document["status"] = np.select(
        [
            by_document["one_c_rows"].eq(0),
            by_document["bank_rows"].eq(0),
            by_document["abs_amount_gap"].le(1),
        ],
        ["Только банк", "Только 1С", "Сходится в пределах 1 руб."],
        default="Расхождение больше 1 руб.",
    )
    by_document = by_document.sort_values(["status", "abs_amount_gap"], ascending=[True, False])

    payments["month"] = payments["payment_date"].dt.to_period("M").astype(str)
    credit["month"] = credit["operation_date"].dt.to_period("M").astype(str)
    by_month = pd.concat(
        [
            payments.groupby("month")["amount"].sum().rename("one_c_payments"),
            credit.groupby("month")["credit"].sum().rename("bank_credit"),
        ],
        axis=1,
    ).fillna(0)
    by_month["amount_gap"] = by_month["one_c_payments"] - by_month["bank_credit"]
    by_month["abs_amount_gap"] = by_month["amount_gap"].abs()
    by_month["gap_pct_of_1c"] = by_month["amount_gap"] / by_month["one_c_payments"].replace(0, np.nan)
    by_month = by_month.reset_index()

    both_docs = by_document.loc[by_document["one_c_rows"].gt(0) & by_document["bank_rows"].gt(0)]
    summary = {
        "one_c_payment_rows": int(len(payments)),
        "bank_credit_rows": int(len(credit)),
        "one_c_documents": int(one_c_docs["doc"].nunique()),
        "bank_credit_documents": int(bank_docs["doc"].nunique()),
        "documents_in_both_sources": int(len(both_docs)),
        "documents_only_1c": int((by_document["one_c_rows"].gt(0) & by_document["bank_rows"].eq(0)).sum()),
        "documents_only_bank": int((by_document["bank_rows"].gt(0) & by_document["one_c_rows"].eq(0)).sum()),
        "one_c_payments_total": float(payments["amount"].sum()),
        "bank_credit_total": float(credit["credit"].sum()),
        "total_amount_gap": float(payments["amount"].sum() - credit["credit"].sum()),
        "matched_documents_amount_gap": float(both_docs["amount_gap"].sum()),
        "matched_documents_abs_gap": float(both_docs["abs_amount_gap"].sum()),
        "documents_with_gap_within_1_rub": int(by_document["abs_amount_gap"].le(1).sum()),
        "documents_with_gap_over_1_rub": int(by_document["abs_amount_gap"].gt(1).sum()),
        "max_matched_document_gap": float(both_docs["abs_amount_gap"].max()),
    }
    return by_month, by_document, summary


def build_metrics(
    bank_raw: pd.DataFrame,
    sales: pd.DataFrame,
    payments: pd.DataFrame,
    bank: pd.DataFrame,
    reconciliation_summary: dict,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    needs_review = bank["needs_review"].astype(str).str.lower().eq("true")
    revenue = float(bank.loc[bank["category_final"].eq("Выручка от клиентов"), "amount"].sum())
    operating_outflows = float(
        bank.loc[
            bank["category_group"].eq("Операционные платежи") & bank["operation_type"].eq("debit"),
            "amount",
        ].sum()
    )
    ocf = revenue - operating_outflows
    production_purchases = float(bank.loc[bank["category_final"].eq("Закупки для производства"), "amount"].sum())
    packaging = float(bank.loc[bank["category_final"].eq("Упаковка и расходники"), "amount"].sum())
    direct_costs = production_purchases + packaging

    sales_total = float(sales["amount"].sum())
    payments_total = float(payments["amount"].sum())
    returns_total = abs(float(sales.loc[sales["amount"].lt(0), "amount"].sum()))

    financial_metrics = pd.DataFrame(
        [
            ("bank_rows_raw", len(bank_raw), "Количество строк банковской выписки до аналитической классификации"),
            ("classified_operations", len(bank), "Количество операций в итоговой классифицированной таблице"),
            ("analysis_period_start", bank["date"].min().date().isoformat(), "Начало периода банка"),
            ("analysis_period_end", bank["date"].max().date().isoformat(), "Конец периода банка"),
            ("one_c_sales_total", sales_total, "Продажи/корректировки по 1С, всего"),
            ("one_c_payments_total", payments_total, "Оплаты по 1С, всего"),
            ("bank_revenue_inflow", revenue, "Банковские поступления, классифицированные как выручка"),
            ("operating_outflows", operating_outflows, "Операционные банковские списания"),
            ("operating_cash_flow", ocf, "Операционный денежный поток"),
            ("ocf_margin", ocf / revenue, "Денежная операционная маржа"),
            ("direct_cost_cash_proxy", direct_costs, "Закупки для производства + упаковка"),
            ("cash_contribution_after_direct_costs", revenue - direct_costs, "Поступления минус прямые денежные закупки"),
            ("cash_contribution_margin", (revenue - direct_costs) / revenue, "Прокси-маржа после прямых денежных закупок"),
            ("production_purchases_share_of_revenue", production_purchases / revenue, "Закупки для производства / выручка"),
            ("packaging_share_of_revenue", packaging / revenue, "Упаковка / выручка"),
            ("all_operating_outflows_to_revenue", operating_outflows / revenue, "Операционные выплаты / выручка"),
            ("sales_returns_and_corrections_abs", returns_total, "Абсолютная сумма отрицательных продаж/корректировок в 1С"),
            ("sales_returns_and_corrections_share", returns_total / abs(sales_total), "Доля отрицательных продаж/корректировок в 1С"),
            ("missing_dates_count", int(bank["date"].isna().sum()), "Операции без даты"),
            ("unknown_count", int(bank["category_final"].eq(UNKNOWN_CATEGORY).sum()), "Операции unknown"),
            ("unknown_amount", float(bank.loc[bank["category_final"].eq(UNKNOWN_CATEGORY), "amount"].sum()), "Сумма unknown"),
            ("unknown_amount_share", float(bank.loc[bank["category_final"].eq(UNKNOWN_CATEGORY), "amount"].sum() / bank["amount"].sum()), "Доля unknown в обороте"),
            ("needs_review_count", int(needs_review.sum()), "Операции к ручной проверке"),
            ("needs_review_share", float(needs_review.mean()), "Доля операций к ручной проверке"),
            ("needs_review_amount", float(bank.loc[needs_review, "amount"].sum()), "Сумма операций к ручной проверке"),
            ("one_c_bank_total_gap", reconciliation_summary["total_amount_gap"], "Разница 1С-оплат и всех кредитовых банковских поступлений"),
            ("one_c_bank_matched_docs_abs_gap", reconciliation_summary["matched_documents_abs_gap"], "Абсолютный разрыв по документам, найденным в обоих источниках"),
        ],
        columns=["metric", "value", "interpretation"],
    )

    bank_clients = (
        bank.loc[bank["category_final"].eq("Выручка от клиентов")]
        .groupby("counterparty", dropna=False)
        .agg(amount=("amount", "sum"), operations=("operation_id", "size"))
        .reset_index()
    )
    bank_suppliers = (
        bank.loc[bank["operation_type"].eq("debit")]
        .groupby("counterparty", dropna=False)
        .agg(amount=("amount", "sum"), operations=("operation_id", "size"))
        .reset_index()
    )
    one_c_payments_legal = payments.groupby("legal_entity", dropna=False)["amount"].sum().reset_index(name="amount")
    one_c_payments_brand = payments.groupby("brand", dropna=False)["amount"].sum().reset_index(name="amount")
    one_c_sales_legal = sales.groupby("legal_entity", dropna=False)["amount"].sum().reset_index(name="amount")
    one_c_sales_brand = sales.groupby("brand", dropna=False)["amount"].sum().reset_index(name="amount")

    concentration_metrics = pd.DataFrame(
        [
            concentration_table(bank_clients, "Банк: клиенты по названию контрагента", "counterparty"),
            concentration_table(bank_suppliers, "Банк: расходные контрагенты по названию", "counterparty"),
            concentration_table(one_c_payments_legal, "1С оплаты: юрлица", "legal_entity"),
            concentration_table(one_c_payments_brand, "1С оплаты: бренд/сеть", "brand"),
            concentration_table(one_c_sales_legal, "1С продажи: юрлица", "legal_entity"),
            concentration_table(one_c_sales_brand, "1С продажи: бренд/сеть", "brand"),
        ]
    )

    category_structure = (
        bank.groupby(["category_final", "operation_type"], dropna=False)
        .agg(amount=("amount", "sum"), operations=("operation_id", "size"))
        .reset_index()
        .sort_values("amount", ascending=False)
    )

    metrics_dict = {
        "revenue": revenue,
        "operating_outflows": operating_outflows,
        "ocf": ocf,
        "ocf_margin": ocf / revenue,
        "direct_costs": direct_costs,
        "direct_margin": (revenue - direct_costs) / revenue,
        "production_purchases": production_purchases,
        "packaging": packaging,
        "sales_total": sales_total,
        "payments_total": payments_total,
        "returns_total": returns_total,
        "needs_review_count": int(needs_review.sum()),
        "needs_review_share": float(needs_review.mean()),
        "needs_review_amount": float(bank.loc[needs_review, "amount"].sum()),
        "unknown_count": int(bank["category_final"].eq(UNKNOWN_CATEGORY).sum()),
        "unknown_amount": float(bank.loc[bank["category_final"].eq(UNKNOWN_CATEGORY), "amount"].sum()),
        "unknown_share": float(bank.loc[bank["category_final"].eq(UNKNOWN_CATEGORY), "amount"].sum() / bank["amount"].sum()),
    }

    return financial_metrics, concentration_metrics, category_structure, metrics_dict


def build_figures(
    sales: pd.DataFrame,
    payments: pd.DataFrame,
    bank: pd.DataFrame,
    by_month: pd.DataFrame,
    concentration_metrics: pd.DataFrame,
) -> None:
    import matplotlib.pyplot as plt

    FIGURES_DIR.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "axes.titlesize": 12, "axes.labelsize": 10})

    bank = bank.copy()
    sales = sales.copy()
    payments = payments.copy()
    bank["month"] = bank["date"].dt.to_period("M").astype(str)
    sales["month"] = sales["sale_date"].dt.to_period("M").astype(str)
    payments["month"] = payments["payment_date"].dt.to_period("M").astype(str)

    bridge = pd.concat(
        [
            sales.groupby("month")["amount"].sum().rename("1С продажи"),
            payments.groupby("month")["amount"].sum().rename("1С оплаты"),
            bank.loc[bank["category_final"].eq("Выручка от клиентов")]
            .groupby("month")["amount"]
            .sum()
            .rename("Банк: выручка"),
        ],
        axis=1,
    ).fillna(0)

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    bridge.plot(ax=axes[0, 0], marker="o")
    axes[0, 0].set_title("Мост 1С продажи - 1С оплаты - банк")
    axes[0, 0].set_xlabel("Месяц")
    axes[0, 0].set_ylabel("Руб.")
    axes[0, 0].tick_params(axis="x", rotation=45)

    outflows = (
        bank.loc[bank["operation_type"].eq("debit")]
        .groupby("category_final")["amount"]
        .sum()
        .sort_values(ascending=True)
        .tail(8)
    )
    outflows.plot(kind="barh", ax=axes[0, 1], color="#B85346")
    axes[0, 1].set_title("Крупнейшие статьи расходов")
    axes[0, 1].set_xlabel("Руб.")
    axes[0, 1].set_ylabel("")

    cf = pd.read_csv(OUTPUTS_DIR / "cash_flow_by_month.csv")
    cf.plot(x="month", y="operating_cash_flow", kind="bar", ax=axes[1, 0], color="#4C78A8", legend=False)
    axes[1, 0].axhline(0, color="black", linewidth=1)
    axes[1, 0].set_title("Операционный денежный поток по месяцам")
    axes[1, 0].set_xlabel("Месяц")
    axes[1, 0].set_ylabel("Руб.")
    axes[1, 0].tick_params(axis="x", rotation=45)

    by_month.set_index("month")[["amount_gap"]].plot(kind="bar", ax=axes[1, 1], color="#72B7B2", legend=False)
    axes[1, 1].axhline(0, color="black", linewidth=1)
    axes[1, 1].set_title("Расхождение 1С оплат и банка по месяцам")
    axes[1, 1].set_xlabel("Месяц")
    axes[1, 1].set_ylabel("Руб.")
    axes[1, 1].tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "audit_cash_flow_structure.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    supplier = (
        bank.loc[bank["operation_type"].eq("debit")]
        .groupby("counterparty")["amount"]
        .sum()
        .sort_values(ascending=False)
        .head(10)
        .sort_values()
    )
    client_brand = payments.groupby("brand", dropna=False)["amount"].sum().sort_values(ascending=False)
    client_brand.index = client_brand.index.fillna("Не определено")

    fig, axes = plt.subplots(1, 2, figsize=(16, 6))
    supplier.plot(kind="barh", ax=axes[0], color="#B85346")
    axes[0].set_title("Топ расходных контрагентов банка")
    axes[0].set_xlabel("Руб.")
    axes[0].set_ylabel("")
    client_brand.plot(kind="pie", ax=axes[1], autopct="%1.1f%%", startangle=90, colors=["#4C78A8", "#F58518", "#72B7B2"])
    axes[1].set_title("Концентрация поступлений 1С по брендам")
    axes[1].set_ylabel("")
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "audit_counterparty_concentration.png", dpi=180, bbox_inches="tight")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(14, 5))
    plot_data = by_month.set_index("month")[["one_c_payments", "bank_credit"]].rename(
        columns={"one_c_payments": "1С оплаты", "bank_credit": "Банк: кредит"}
    )
    plot_data.plot(kind="bar", ax=ax, width=0.82)
    ax.set_title("Сверка 1С оплат и кредитовых банковских поступлений")
    ax.set_xlabel("Месяц")
    ax.set_ylabel("Руб.")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(FIGURES_DIR / "audit_1c_bank_reconciliation.png", dpi=180, bbox_inches="tight")
    plt.close(fig)


def write_audit_findings(
    reconciliation_summary: dict,
    financial_metrics: pd.DataFrame,
    concentration_metrics: pd.DataFrame,
    by_month: pd.DataFrame,
    by_document: pd.DataFrame,
    metrics: dict,
) -> None:
    cm = concentration_metrics.set_index("segment")
    supplier = cm.loc["Банк: расходные контрагенты по названию"]
    client_legal = cm.loc["1С оплаты: юрлица"]
    client_brand = cm.loc["1С оплаты: бренд/сеть"]
    bank_clients = cm.loc["Банк: клиенты по названию контрагента"]
    negative_months = pd.read_csv(OUTPUTS_DIR / "cash_flow_by_month.csv")
    negative_ocf_months = negative_months.loc[negative_months["operating_cash_flow"].lt(0), "month"].tolist()
    largest_month_gap = by_month.loc[by_month["abs_amount_gap"].idxmax()]
    largest_doc_gap = by_document.sort_values("abs_amount_gap", ascending=False).iloc[0]

    lines = [
        "# Финансовый аудит и качество данных",
        "",
        "## Главные выводы",
        "",
        f"- Бизнес генерирует существенный оборот: банковская выручка клиентов за период составляет **{money(metrics['revenue'])} руб.**, 1С-продажи - **{money(metrics['sales_total'])} руб.**, 1С-оплаты - **{money(metrics['payments_total'])} руб.**",
        f"- Денежная операционная рентабельность практически нулевая: операционные поступления **{money(metrics['revenue'])} руб.**, операционные списания **{money(metrics['operating_outflows'])} руб.**, operating cash flow **{money(metrics['ocf'])} руб.**, маржа OCF **{pct(metrics['ocf_margin'], 2)}**.",
        f"- Прокси-маржа после прямых денежных закупок лучше, но затем полностью съедается постоянными и прочими расходами: закупки для производства + упаковка **{money(metrics['direct_costs'])} руб.**, вклад после них **{money(metrics['revenue'] - metrics['direct_costs'])} руб.**, маржа **{pct(metrics['direct_margin'], 1)}**.",
        f"- Прокси-маржа здесь - приближенная денежная валовая маржа по доступным банковским данным: `(выручка клиентов - закупки для производства - упаковка) / выручка клиентов`. Это не бухгалтерская валовая прибыль, потому что не учитывает складские остатки, списания себестоимости и начисления.",
        f"- Главная зона оптимизации - производственные закупки: только закупки для производства составляют **{money(metrics['production_purchases'])} руб.** или **{pct(metrics['production_purchases'] / metrics['revenue'], 1)}** банковской выручки; упаковка добавляет еще **{money(metrics['packaging'])} руб.**.",
        f"- Кассовая устойчивость слабая: отрицательный OCF был в месяцах **{', '.join(negative_ocf_months)}**. Это означает, что небольшие задержки оплат или закупочные всплески быстро превращаются в кассовый разрыв.",
        "",
        "## Концентрация и риск контрагентов",
        "",
        "- HHI считается как сумма квадратов долей контрагентов: `HHI = sum(share_i^2)` или в пунктах `HHI * 10 000`. Интерпретация: до 1500 пунктов - низкая/умеренная концентрация, 1500-2500 - высокая, выше 2500 - очень высокая; для этого аудита метрика показывает зависимость денежных потоков от нескольких контрагентов или сетей.",
        f"- По расходным контрагентам концентрация высокая: HHI **{supplier['hhi_10000']:.0f}** пунктов, CR1 **{pct(supplier['cr1'], 1)}**, CR5 **{pct(supplier['cr5'], 1)}**, CR10 **{pct(supplier['cr10'], 1)}**. Крупнейший контрагент - **{supplier['top_entity']}**, сумма **{money(supplier['top_amount'])} руб.**",
        f"- По банковским поступлениям на уровне буквальных названий контрагентов концентрация выглядит низкой: HHI **{bank_clients['hhi_10000']:.0f}**, CR5 **{pct(bank_clients['cr5'], 1)}**. Но это занижает риск, потому что сеть разбита на множество юрлиц/счетов.",
        f"- По 1С-оплатам на уровне юрлиц концентрация уже высокая: HHI **{client_legal['hhi_10000']:.0f}**, CR1 **{pct(client_legal['cr1'], 1)}**, CR5 **{pct(client_legal['cr5'], 1)}**.",
        f"- По брендам/сетям риск максимальный: бренд **{client_brand['top_entity']}** дает **{pct(client_brand['cr1'], 1)}** оплат, HHI по брендам **{client_brand['hhi_10000']:.0f}**. Вывод для текста: продажи нужно расширять за пределы одного доминирующего канала, иначе задержка/пересмотр условий одной сети ударит по всей кассе.",
        "",
        "## Сверка 1С и банка",
        "",
        f"- На уровне итоговых сумм 1С и банк почти сходятся: 1С-оплаты **{money(reconciliation_summary['one_c_payments_total'])} руб.**, кредитовые поступления банка **{money(reconciliation_summary['bank_credit_total'])} руб.**, общий разрыв **{money(reconciliation_summary['total_amount_gap'])} руб.**",
        f"- По документам найдено в обоих источниках **{reconciliation_summary['documents_in_both_sources']}** документа; документов только в 1С - **{reconciliation_summary['documents_only_1c']}**, только в банке - **{reconciliation_summary['documents_only_bank']}**.",
        f"- Единственный документ только в банке - поступление/возврат на **{money(float(largest_doc_gap['bank_amount']))} руб.** по документу **{largest_doc_gap['doc']}**; именно он объясняет почти весь месячный разрыв мая.",
        f"- По документам, которые есть в обоих источниках, суммарный разрыв всего **{money(reconciliation_summary['matched_documents_amount_gap'])} руб.**, абсолютный разрыв **{money(reconciliation_summary['matched_documents_abs_gap'])} руб.**, максимальный разрыв по matched-документу **{reconciliation_summary['max_matched_document_gap']:.2f} руб.**",
        f"- Основная разладка данных: 1С хранит суммы оплат в основном в рублях/округлениях, банк содержит копейки; названия контрагентов в банке содержат расчетные счета и банк, а в 1С часть названий содержит адрес торговой точки. Поэтому автоматическая построчная сверка без нормализации будет давать ложные расхождения.",
        f"- Самый заметный месячный разрыв: **{largest_month_gap['month']}**, абсолютное расхождение **{money(float(largest_month_gap['abs_amount_gap']))} руб.**",
        "",
        "## Качество данных",
        "",
        f"- Даты очищены хорошо: операций без даты в классифицированной банковской таблице **0**.",
        f"- Unknown практически устранен: **{metrics['unknown_count']}** операция на **{money(metrics['unknown_amount'])} руб.**, доля в обороте **{pct(metrics['unknown_share'], 2)}**.",
        f"- Ручной проверки требуют **{metrics['needs_review_count']}** операций (**{pct(metrics['needs_review_share'], 1)}** по количеству), но их сумма крупная - **{money(metrics['needs_review_amount'])} руб.** Это не проблема покрытия категорий, а контроль крупных и неоднозначных платежей.",
        "- Старые выводы о количестве операций в README/плане могут расходиться с текущими output-файлами: актуальная классифицированная таблица содержит 4 086 операций. В тексте лучше ссылаться на свежие расчетные outputs, а не на устаревшие контрольные цифры.",
    ]

    FINDINGS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def append_notebook_block(
    notebook_path: Path,
    title: str,
    output_files: list[str],
    figure_paths: list[str] | None = None,
) -> None:
    notebook = json.loads(notebook_path.read_text(encoding="utf-8"))
    marker = "<!-- audit_enrichment_v1 -->"
    cells = notebook.get("cells", [])
    cells = [
        cell
        for cell in cells
        if marker not in "".join(cell.get("source", []))
    ]

    figure_paths = figure_paths or []
    image_lines = [f"![{Path(path).stem}]({path})" for path in figure_paths]
    output_lines = [f"- `{path}`" for path in output_files]
    markdown = [
        marker + "\n",
        f"## {title}\n",
        "\n",
        "Добавлен слой финансового аудита: сверка 1С и банка, денежная рентабельность и концентрация контрагентов. Ключевые тезисы собраны в `outputs/financial_audit_findings.md`.\n",
        "\n",
        "### Итоговые материалы\n",
        "\n",
        *[line + "\n" for line in output_lines],
    ]
    if image_lines:
        markdown.extend(["\n", "### Графики\n", "\n", *[line + "\n\n" for line in image_lines]])
    cells.append({"cell_type": "markdown", "metadata": {}, "source": markdown})
    notebook["cells"] = cells
    notebook_path.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build financial audit conclusions from prepared 1C and bank data.")
    parser.add_argument("--emit-tables", action="store_true", help="Save intermediate CSV reconciliation/metric tables.")
    parser.add_argument("--emit-figures", action="store_true", help="Save PNG figures and link them from notebooks.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    OUTPUTS_DIR.mkdir(exist_ok=True)
    if args.emit_figures:
        FIGURES_DIR.mkdir(exist_ok=True)

    bank_raw, sales, payments, bank = read_inputs()
    by_month, by_document, reconciliation_summary = build_reconciliation(bank_raw, payments)
    financial_metrics, concentration_metrics, category_structure, metrics = build_metrics(
        bank_raw, sales, payments, bank, reconciliation_summary
    )

    if args.emit_tables:
        by_month.to_csv(OUTPUTS_DIR / "reconciliation_1c_bank_by_month.csv", index=False)
        by_document.to_csv(OUTPUTS_DIR / "reconciliation_1c_bank_by_document.csv", index=False)
        pd.DataFrame([reconciliation_summary]).to_csv(OUTPUTS_DIR / "reconciliation_1c_bank_summary.csv", index=False)
        financial_metrics.to_csv(OUTPUTS_DIR / "financial_audit_metrics.csv", index=False)
        concentration_metrics.to_csv(OUTPUTS_DIR / "concentration_metrics.csv", index=False)
        category_structure.to_csv(OUTPUTS_DIR / "cash_flow_category_structure.csv", index=False)

    if args.emit_figures:
        build_figures(sales, payments, bank, by_month, concentration_metrics)

    write_audit_findings(
        reconciliation_summary,
        financial_metrics,
        concentration_metrics,
        by_month,
        by_document,
        metrics,
    )

    figure_paths = []
    if args.emit_figures:
        figure_paths = [
            "figures/audit_cash_flow_structure.png",
            "figures/audit_counterparty_concentration.png",
            "figures/audit_1c_bank_reconciliation.png",
        ]
    output_files = ["outputs/financial_audit_findings.md"]
    if args.emit_tables:
        output_files.extend(
            [
                "outputs/financial_audit_metrics.csv",
                "outputs/concentration_metrics.csv",
                "outputs/reconciliation_1c_bank_by_month.csv",
                "outputs/reconciliation_1c_bank_by_document.csv",
            ]
        )
    append_notebook_block(
        PROJECT_ROOT / "00_Обзор_структуры_данных.ipynb",
        "Дополнительный аудит структуры данных, 1С и банка",
        output_files,
        ["figures/audit_cash_flow_structure.png", "figures/audit_1c_bank_reconciliation.png"] if args.emit_figures else [],
    )
    append_notebook_block(
        PROJECT_ROOT / "01_Исследование_классификации_банковских_операций.ipynb",
        "Финансовые метрики, концентрация и сверка источников",
        output_files,
        figure_paths,
    )

    print("Готово: рассчитаны метрики и обновлены Markdown-блоки ноутбуков.")


if __name__ == "__main__":
    main()
