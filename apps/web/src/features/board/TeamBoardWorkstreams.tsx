import type { Dispatch, SetStateAction } from "react";

import { PageState } from "../../components/PageState";
import type { WorkPackage } from "../../lib/api/boardTypes";
import { formatDate } from "../../lib/status";
import { BoardSurface } from "./BoardSurface";
import {
  archiveBoardColumns,
  serviceRequestBoardColumns,
  serviceRequestColumnMeanings,
  serviceRequestExceptionColumns,
  workPackageBoardColumns,
} from "./boardPresentation";
import type { TeamBoardController } from "./useTeamBoardController";

export function TeamBoardWorkstreams({ board }: { board: TeamBoardController }) {
  return (
    <>
      {board.showRequests ? <ServiceRequestWorkstream board={board} /> : null}
      {board.showPackages ? <WorkPackageWorkstream board={board} /> : null}
    </>
  );
}

function ServiceRequestWorkstream({ board }: { board: TeamBoardController }) {
  const data = board.requestBoard.data!;
  return (
    <section aria-labelledby="service-request-board-title" className="board-workstream">
      <header className="board-workstream__header">
        <span>Customer workflow</span>
        <h2 id="service-request-board-title">Service request board</h2>
        <p>
          Requests move through these stages when Analysts, Managers and QC complete their named
          workflow actions.
        </p>
      </header>
      <BoardSurface
        activeColumns={serviceRequestBoardColumns}
        ariaLabel="Service request workflow board"
        archiveColumns={archiveBoardColumns}
        columnCounts={data.columnCounts}
        columnDescriptions={serviceRequestColumnMeanings}
        columnFilterActive={board.filters.columns.length > 0}
        context={{}}
        exceptionColumns={serviceRequestExceptionColumns}
        filteredColumns={board.filters.columns.filter((column) =>
          [
            ...serviceRequestBoardColumns,
            ...serviceRequestExceptionColumns,
            ...archiveBoardColumns,
          ].includes(column),
        )}
        items={data.items.filter((item) => item.itemType === "SERVICE_REQUEST")}
        mode={board.mode}
        onInspect={board.setSelected}
        onShowArchive={board.toggleRequestArchive}
        onShowExceptions={board.toggleExceptions}
        resultNote="Service requests cannot be dragged. Their stage changes through assignment, Analyst submission, Manager review, QC and dissemination."
        showArchive={board.showRequestArchive}
        showExceptions={board.showExceptions}
        totalCount={data.totalCount}
        wipLimits={data.wipLimits}
      />
      <BoardPagination
        ariaLabel="Service request pages"
        cursors={board.requestCursors}
        nextCursor={data.nextCursor}
        onChange={board.setRequestCursors}
      />
      {data.totalCount === 0 ? (
        <PageState kind="empty" title="No service requests match this view">
          Clear or change the current filters.
        </PageState>
      ) : null}
    </section>
  );
}

function WorkPackageWorkstream({ board }: { board: TeamBoardController }) {
  return (
    <details
      className="board-workstream board-workstream--packages"
      onToggle={(event) => board.setPackagesOpen(event.currentTarget.open)}
      open={board.packagesOpen}
    >
      <summary>
        <span className="board-workstream__chevron" aria-hidden="true">
          ›
        </span>
        <span className="board-workstream__summary-copy">
          <small>Analyst team planning</small>
          <strong>Work package Kanban</strong>
          <span>Expand to create and move internal team cards.</span>
        </span>
        <span className="board-workstream__summary-action">
          {board.packagesOpen ? "Collapse" : "Expand"}
        </span>
      </summary>
      <div className="board-workstream__body">
        <header className="board-workstream__actions">
          <div>
            <strong>Internal team cards</strong>
            <span>
              Create scratch tasks, assign contributors and move the work without changing the
              Customer request.
            </span>
          </div>
          {board.canReadPeople ? (
            <button
              className="button button--primary"
              onClick={() => board.setCreating(true)}
              type="button"
            >
              Create internal card
            </button>
          ) : null}
        </header>
        <WorkPackageBoardState board={board} />
      </div>
    </details>
  );
}

function WorkPackageBoardState({ board }: { board: TeamBoardController }) {
  if (board.packageBoard.isPending)
    return <PageState kind="loading" title="Loading work package Kanban" />;
  if (board.packageBoard.isError)
    return (
      <PageState
        action={
          <button className="button" onClick={() => void board.packageBoard.refetch()}>
            Try again
          </button>
        }
        kind="error"
        title="Work package Kanban could not be loaded"
      />
    );
  if (!board.packageBoard.data) return null;
  const data = board.packageBoard.data;
  return (
    <>
      <BoardSurface
        activeColumns={workPackageBoardColumns}
        ariaLabel="Work package Kanban"
        archiveColumns={archiveBoardColumns}
        columnCounts={data.columnCounts}
        columnFilterActive={board.filters.columns.length > 0}
        context={{ packages: board.packages.data!.items, iterations: board.iterations.data!.items }}
        exceptionColumns={[]}
        filteredColumns={board.filters.columns.filter((column) =>
          [...workPackageBoardColumns, ...archiveBoardColumns].includes(column),
        )}
        items={data.items.filter((item) => item.itemType === "WORK_PACKAGE")}
        mode={board.mode}
        moving={board.move.isPending}
        onInspect={board.setSelected}
        onMove={(item, target, reason) =>
          board.move.mutateAsync({ item, target, reason }).then(() => undefined)
        }
        onShowArchive={board.togglePackageArchive}
        onShowExceptions={() => undefined}
        resultNote="Drag a work-package card to move it. Each manual move requires a reason and is recorded in its activity history."
        showArchive={board.showPackageArchive}
        showExceptions={false}
        totalCount={data.totalCount}
        wipLimits={data.wipLimits}
      />
      <BoardPagination
        ariaLabel="Work package pages"
        cursors={board.packageCursors}
        nextCursor={data.nextCursor}
        onChange={board.setPackageCursors}
      />
      {data.totalCount === 0 ? (
        <PageState kind="empty" title="No work packages match this view">
          Clear or change the current filters.
        </PageState>
      ) : null}
      <PackageActivityFeed packages={board.packages.data!.items} />
    </>
  );
}

function PackageActivityFeed({ packages }: { packages: WorkPackage[] }) {
  const recent = packages
    .flatMap((item) =>
      item.activities.map((activity) => ({ ...activity, packageTitle: item.title })),
    )
    .sort((left, right) => right.createdAt.localeCompare(left.createdAt))
    .slice(0, 5);
  if (recent.length === 0) return null;
  return (
    <section aria-labelledby="package-activity-title" className="board-activity">
      <h3 id="package-activity-title">Recent internal card activity</h3>
      <ol>
        {recent.map((activity) => (
          <li key={activity.id}>
            <time dateTime={activity.createdAt}>{formatDate(activity.createdAt, true)}</time>
            <div>
              <strong>{activity.packageTitle}</strong>
              <span>
                {activity.summary} · {activity.actorDisplayName}
              </span>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

function BoardPagination({
  ariaLabel,
  cursors,
  nextCursor,
  onChange,
}: {
  ariaLabel: string;
  cursors: Array<string | null>;
  nextCursor: string | null;
  onChange: Dispatch<SetStateAction<Array<string | null>>>;
}) {
  if (cursors.length === 1 && !nextCursor) return null;
  return (
    <nav aria-label={ariaLabel} className="board-pages">
      <button
        className="button button--quiet"
        disabled={cursors.length === 1}
        onClick={() => onChange((value) => value.slice(0, -1))}
        type="button"
      >
        Previous page
      </button>
      <span>Page {cursors.length}</span>
      <button
        className="button button--quiet"
        disabled={!nextCursor}
        onClick={() => nextCursor && onChange((value) => [...value, nextCursor])}
        type="button"
      >
        Next page
      </button>
    </nav>
  );
}
