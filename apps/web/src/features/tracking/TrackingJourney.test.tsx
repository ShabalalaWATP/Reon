import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { trackedRequest } from "../../test/fixtures";
import { TrackingJourney } from "./TrackingJourney";

describe("tracking journey viewer context", () => {
  it("keeps the route readable when viewer context is unavailable", () => {
    render(<TrackingJourney request={trackedRequest} />);

    expect(screen.queryByText(/^Viewing as /)).not.toBeInTheDocument();
    expect(screen.queryByText("Your unit")).not.toBeInTheDocument();
    expect(screen.getByText("Customer", { selector: "strong" })).toBeInTheDocument();
  });
});
