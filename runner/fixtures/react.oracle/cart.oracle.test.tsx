// Oracle tests for the change-react-component task. They live OUTSIDE the
// fixture so the model cannot grep them; verify.sh copies them in, runs the
// suite and removes them.
import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Cart } from "./Cart";

const items = [
  { name: "Café", cents: 1000 },
  { name: "Medialuna", cents: 2000 },
];

describe("Cart with discount (oracle)", () => {
  it("without the prop, renders no discount line and the full total", () => {
    const html = renderToStaticMarkup(<Cart items={items} />);
    expect(html).not.toContain("Descuento");
    expect(html).toContain("30,00");
  });

  it("with discount=10, shows the discount amount and the net total", () => {
    const html = renderToStaticMarkup(<Cart items={items} discount={10} />);
    expect(html).toContain("Descuento");
    expect(html).toContain("3,00");
    expect(html).toContain("27,00");
    expect(html).not.toContain("30,00");
  });

  it("with discount=0, renders exactly the same markup as without the prop", () => {
    // `{discount && ...}` with 0 renders a stray "0" in React: the two
    // markups must be byte-identical, not merely "no Descuento line".
    const withZero = renderToStaticMarkup(<Cart items={items} discount={0} />);
    const without = renderToStaticMarkup(<Cart items={items} />);
    expect(withZero).toBe(without);
    expect(without).not.toContain("Descuento");
    expect(without).toContain("30,00");
  });

  it("keeps one line per item unchanged", () => {
    const html = renderToStaticMarkup(<Cart items={items} discount={10} />);
    expect(html).toContain("Café");
    expect(html).toContain("10,00");
    expect(html).toContain("20,00");
  });
});
