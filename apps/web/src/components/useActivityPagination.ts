import { useMutation } from "@tanstack/react-query";
import { useState } from "react";

type ActivityEvent = {
  createdAt: string;
  id: string;
};

type ActivityPage<Event extends ActivityEvent> = {
  events: Event[];
  eventsNextCursor?: string | null;
};

export function useActivityPagination<Event extends ActivityEvent>(
  initialEvents: Event[],
  initialCursor: string | null | undefined,
  loadPage: (cursor?: string) => Promise<ActivityPage<Event>>,
) {
  const [events, setEvents] = useState(initialEvents);
  const [cursor, setCursor] = useState(initialCursor ?? null);
  const older = useMutation({
    mutationFn: () => loadPage(cursor ?? undefined),
    onSuccess: (page) => {
      setEvents((current) => {
        const byId = new Map(current.map((event) => [event.id, event]));
        page.events.forEach((event) => byId.set(event.id, event));
        return [...byId.values()].sort((left, right) =>
          left.createdAt.localeCompare(right.createdAt),
        );
      });
      setCursor(page.eventsNextCursor ?? null);
    },
  });

  return { cursor, events, older };
}
