import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { PersonalProfile } from "../../lib/api/types";
import { PersonalProfileDetails } from "./PersonalProfileDetails";

const profile: PersonalProfile = {
  userId: "00000000-0000-0000-0000-000000000101",
  name: "Synthetic User",
  username: "synthetic.user",
  email: "synthetic.user@example.test",
  role: "DELIVERY_SPECIALIST",
  profileTeam: null,
  rankOrGrade: "Synthetic grade",
  serviceNumber: "SYN-123",
  skills: [],
  additionalInformation: null,
  version: 1,
};

describe("PersonalProfileDetails", () => {
  it("renders both populated and empty values, including skill labels", () => {
    const { rerender } = render(<PersonalProfileDetails profile={profile} />);
    expect(screen.getByText("Synthetic grade")).toBeInTheDocument();
    expect(screen.getAllByText("Not provided")).toHaveLength(3);

    rerender(<PersonalProfileDetails profile={{ ...profile, skills: ["Research", "Briefing"] }} />);
    expect(screen.getByText("Research")).toBeInTheDocument();
    expect(screen.getByText("Briefing")).toBeInTheDocument();
  });
});
