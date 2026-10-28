import { formatPrice, formatDate } from "../lib/format";

export function Receipt({ cents, date }: { cents: number; date: Date }) {
  return <p>{formatDate(date)}: {formatPrice(cents, "USD")}</p>;
}
