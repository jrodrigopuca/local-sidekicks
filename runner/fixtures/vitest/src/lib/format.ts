export function formatPrice(cents: number, currency = "ARS"): string {
  return new Intl.NumberFormat("es-AR", { style: "currency", currency }).format(cents / 100);
}

export function formatDate(d: Date): string {
  return d.toLocaleDateString("es-AR");
}

export function formatPercent(ratio: number): string {
  return (ratio * 100).toFixed(1).replace(".", ",") + " %";
}
