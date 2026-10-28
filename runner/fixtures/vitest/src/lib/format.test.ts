import { describe, it, expect } from "vitest";
import { formatPrice } from "./format";

describe("formatPrice", () => {
  it("formats cents as ARS", () => {
    expect(formatPrice(123456)).toContain("1.234,56");
  });
});
