import { PageState } from "../../components/PageState";
import { ApiError } from "../../lib/api/client";
import { MyWorkView } from "./MyWorkView";
import { useMyWorkPage } from "./useMyWorkPage";

export function MyWorkPage() {
  const controller = useMyWorkPage();
  if (controller.query.isPending) return <PageState kind="loading" title="Loading your work" />;
  if (controller.query.isError)
    return (
      <WorkspaceError
        error={controller.query.error}
        retry={() => void controller.query.refetch()}
      />
    );
  const first = controller.query.data.pages[0];
  const items = controller.query.data.pages.flatMap((page) => page.items);
  return <MyWorkView controller={controller} first={first} items={items} />;
}

function WorkspaceError({ error, retry }: { error: Error; retry: () => void }) {
  const denied = error instanceof ApiError && error.status === 403;
  const conflict = error instanceof ApiError && error.status === 409;
  return (
    <PageState
      action={
        denied ? undefined : (
          <button className="button" onClick={retry}>
            Refresh
          </button>
        )
      }
      kind="error"
      title={
        denied
          ? "Your access has changed"
          : conflict
            ? "This work view changed"
            : "Your work could not be loaded"
      }
    >
      {denied
        ? "Return to your home page or ask an Administrator to review your access."
        : conflict
          ? "Refresh to use the latest work state."
          : "Check your connection and try again."}
    </PageState>
  );
}
