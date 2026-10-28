import * as fmt from "./format";

const formatters: Record<string, (n: number) => string> = {
  price: (n) => fmt["formatPrice"](n),
};

export function line(kind: string, n: number) {
  return formatters[kind]?.(n) ?? String(n);
}
