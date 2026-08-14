import { useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import type { TeamWorkspaceAccess, WorkspaceRecordList } from "../../lib/api/teamTypes";
import { useAuth } from "../../lib/auth/AuthProvider";
import { TeamNoticeboardLinkForm, TeamNoticeForm } from "./TeamNoticeboardForms";
import { WorkspaceRecordItem } from "./WorkspaceRecordItem";

export function TeamNoticeboard({ access }: { access: TeamWorkspaceAccess; userId: string }) {
  const { session } = useAuth();
  const queryKeys = protectedQueryKeys(session);
  const client = useQueryClient();
  const queryKey = queryKeys.teamRecords(access.teamId);
  const records = useQuery({ queryKey, queryFn: () => api.workspaceRecords(access.teamId) });
  const canManage = Boolean(access.grantId && access.permissions.includes("ROSTER"));
  const csrfToken = session!.csrfToken;
  const saveList = (list: WorkspaceRecordList) => client.setQueryData(queryKey, list);
  const open = (records.data?.items ?? [])
    .filter((item) => item.status === "OPEN")
    .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt));
  const notices = open.filter((item) => item.kind !== "LINK");
  const links = open.filter((item) => item.kind === "LINK");
  return (
    <section
      aria-labelledby="team-noticeboard-title"
      className="workspace-records team-noticeboard"
    >
      <header>
        <span>Shared team space</span>
        <h2 id="team-noticeboard-title">Noticeboard and pinned links</h2>
        <p>
          {canManage
            ? "Standing notices and useful links for everyone in this workspace. Posting and archiving are recorded with your name."
            : "Standing notices and useful links kept current by this workspace's Managers."}
        </p>
      </header>
      {records.isPending ? <p className="inline-empty">Loading the noticeboard…</p> : null}
      {records.isError ? <p className="inline-unavailable">Noticeboard unavailable</p> : null}
      {records.data ? (
        <div className="workspace-collaboration">
          <div className="team-noticeboard__column">
            <h3 id="team-notices-title">Notices</h3>
            {notices.length ? (
              <ol aria-labelledby="team-notices-title">
                {notices.map((record) => (
                  <WorkspaceRecordItem
                    access={access}
                    canManage={canManage}
                    csrfToken={csrfToken}
                    key={record.id}
                    onSaved={saveList}
                    record={record}
                  />
                ))}
              </ol>
            ) : (
              <p className="inline-empty">No standing notices.</p>
            )}
            {canManage ? (
              <TeamNoticeForm access={access} csrfToken={csrfToken} onSaved={saveList} />
            ) : null}
          </div>
          <aside className="team-noticeboard__column">
            <h3 id="team-links-title">Pinned links</h3>
            {links.length ? (
              <ul aria-labelledby="team-links-title">
                {links.map((record) => (
                  <WorkspaceRecordItem
                    access={access}
                    canManage={canManage}
                    csrfToken={csrfToken}
                    key={record.id}
                    onSaved={saveList}
                    record={record}
                  />
                ))}
              </ul>
            ) : (
              <p className="inline-empty">No pinned links.</p>
            )}
            {canManage ? (
              <TeamNoticeboardLinkForm access={access} csrfToken={csrfToken} onSaved={saveList} />
            ) : null}
          </aside>
        </div>
      ) : null}
    </section>
  );
}
