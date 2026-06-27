export function formatMoney(value: number) {
  return `${Number(value).toLocaleString("ru-RU", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ₽`;
}

export function formatMoneyCompact(value: number) {
  return `${Number(value).toLocaleString("ru-RU", {
    notation: "compact",
    maximumFractionDigits: 1,
  })} ₽`;
}
