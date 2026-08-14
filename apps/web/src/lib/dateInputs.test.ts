import { describe, expect, it } from "vitest";

import { addLocalDays, localDateInputValue, localDateTimeInputValue } from "./dateInputs";

describe("local date input values", () => {
  it("uses local calendar and clock components", () => {
    const value = new Date(2026, 7, 5, 14, 3);

    expect(localDateInputValue(value)).toBe("2026-08-05");
    expect(localDateTimeInputValue(value)).toBe("2026-08-05T14:03");
  });

  it("moves across month boundaries as calendar days", () => {
    const value = new Date(2026, 0, 31, 9, 30);

    expect(localDateInputValue(addLocalDays(value, 1))).toBe("2026-02-01");
  });
});
