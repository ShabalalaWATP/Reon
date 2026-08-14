import { ModalDrawer } from "../../components/ModalDrawer";
import { PageState } from "../../components/PageState";
import { ApiError } from "../../lib/api/client";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { useAuth } from "../../lib/auth/AuthProvider";
import { BoardSettings } from "./BoardSettings";
import { BoardToolbar } from "./BoardToolbar";
import { TeamBoardWorkstreams } from "./TeamBoardWorkstreams";
import { WorkItemInspector } from "./WorkItemInspector";
import { WorkPackageForm } from "./WorkPackageForm";
import { type TeamBoardController, useTeamBoardController } from "./useTeamBoardController";

export function TeamBoardPage({ access }: { access: TeamWorkspaceAccess }) {
  const { session } = useAuth();
  if (!session) return <PageState kind="error" title="Sign in is required" />;
  return <AuthenticatedTeamBoard access={access} session={session} />;
}

function AuthenticatedTeamBoard({
  access,
  session,
}: {
  access: TeamWorkspaceAccess;
  session: Session;
}) {
  const board = useTeamBoardController(access, session);
  if (board.isPending) return <PageState kind="loading" title="Loading team delivery" />;
  if (board.isError) return <BoardLoadError onRetry={board.retryRequiredData} />;
  return <TeamBoardWorkspace board={board} />;
}

function TeamBoardWorkspace({ board }: { board: TeamBoardController }) {
  const mutationError = board.save.error ?? board.remove.error ?? board.move.error;
  return (
    <div className="board-page page-stack">
      {board.deepLinkedRequest.isError ? <DeepLinkError /> : null}
      <BoardToolbar
        canManage={board.canManage}
        filters={board.filters}
        mode={board.mode}
        onChange={board.changeFilters}
        onDeleteView={(view) => board.remove.mutate(view)}
        onModeChange={board.changeMode}
        onOpenSettings={() => board.setSettings(true)}
        onSaveView={() => board.save.mutate()}
        onViewNameChange={board.setViewName}
        people={board.people.data!.items}
        savedViews={board.requestBoard.data!.savedViews}
        saving={board.save.isPending}
        userId={board.session.user.id}
        viewName={board.viewName}
      />
      {mutationError ? (
        <p className="form-banner form-banner--error" role="alert">
          {errorMessage(mutationError)}
        </p>
      ) : null}
      <TeamBoardWorkstreams board={board} />
      <BoardDrawers board={board} />
      <WorkItemInspector
        access={board.access}
        item={board.selected}
        moving={board.move.isPending}
        onClose={() => board.setSelected(null)}
        onMove={(item, target, reason) => board.move.mutate({ item, target, reason })}
        packages={board.packages.data!.items}
        session={board.session}
        userId={board.session.user.id}
      />
    </div>
  );
}

function BoardDrawers({ board }: { board: TeamBoardController }) {
  return (
    <>
      <ModalDrawer
        label="Create internal card"
        onClose={() => board.setCreating(false)}
        open={board.creating}
      >
        <WorkPackageForm
          access={board.access}
          iterations={board.iterations.data!.items}
          members={board.people.data!.items}
          onCreated={() => {
            board.setCreating(false);
            void board.refresh();
          }}
          session={board.session}
        />
      </ModalDrawer>
      <ModalDrawer
        label="Board settings"
        onClose={() => board.setSettings(false)}
        open={board.settings}
      >
        <BoardSettings
          current={board.requestBoard.data!.wipLimits}
          error={board.configure.error}
          onSave={(limits) => board.configure.mutate(limits)}
          pending={board.configure.isPending}
        />
      </ModalDrawer>
    </>
  );
}

function BoardLoadError({ onRetry }: { onRetry: () => Promise<unknown> }) {
  return (
    <PageState
      action={
        <button className="button" onClick={() => void onRetry()}>
          Try again
        </button>
      }
      kind="error"
      title="Team delivery could not be loaded"
    >
      Board, roster, package and iteration data must be available before planning changes can be
      made.
    </PageState>
  );
}

function DeepLinkError() {
  return (
    <p className="form-banner form-banner--error" role="alert">
      The linked request could not be opened. It may no longer be available to this team.
    </p>
  );
}

function errorMessage(error: Error | null) {
  return error instanceof ApiError
    ? error.message
    : (error?.message ?? "The board change could not be saved.");
}
