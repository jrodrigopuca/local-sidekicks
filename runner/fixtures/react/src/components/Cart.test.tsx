import { describe, it, expect } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import { Cart } from "./Cart";

const items = [
  { name: "Café", cents: 1000 },
  { name: "Medialuna", cents: 2000 },
];

describe("Cart", () => {
  it("renders one line per item", () => {
    const html = renderToStaticMarkup(<Cart items={items} />);
    expect(html).toContain("Café");
    expect(html).toContain("Medialuna");
  });

  it("renders the total of all items", () => {
    const html = renderToStaticMarkup(<Cart items={items} />);
    expect(html).toContain("Total:");
    expect(html).toContain("30,00");
  });
});
