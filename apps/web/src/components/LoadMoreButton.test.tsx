import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { LoadMoreButton } from "./LoadMoreButton";

describe("LoadMoreButton", () => {
  it("hides at the end and exposes idle and loading states", async () => {
    const onLoad = vi.fn();
    const { rerender } = render(
      <LoadMoreButton hasMore={false} loading={false} onLoad={onLoad} />,
    );
    expect(screen.queryByRole("button")).not.toBeInTheDocument();

    rerender(<LoadMoreButton hasMore loading={false} onLoad={onLoad} />);
    await userEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect(onLoad).toHaveBeenCalledOnce();

    rerender(<LoadMoreButton hasMore loading onLoad={onLoad} />);
    expect(screen.getByRole("button", { name: "Loading more…" })).toBeDisabled();
  });
});
