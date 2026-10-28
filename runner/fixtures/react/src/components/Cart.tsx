import { formatPrice } from "../lib/format";

type Item = { name: string; cents: number };

export function Cart({ items }: { items: Item[] }) {
  const total = items.reduce((acc, i) => acc + i.cents, 0);
  return (
    <ul>
      {items.map((i) => (
        <li key={i.name}>
          {i.name} — {formatPrice(i.cents)}
        </li>
      ))}
      <li>Total: {formatPrice(total)}</li>
    </ul>
  );
}
