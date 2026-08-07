import { useQuery } from "@tanstack/react-query";
import { Plus } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link } from "react-router";

import { PageState } from "../../components/PageState";
import { api } from "../../lib/api/client";
import { protectedQueryKeys } from "../../lib/api/queryKeys";
import { useAuth } from "../../lib/auth/AuthProvider";
import { AdminUserRegister } from "./AdminUserRegister";
import { StepUpPanel } from "./StepUpPanel";

export function AdminUsersPage() {
  const { session } = useAuth();
  const [draft, setDraft] = useState("");
  const [query, setQuery] = useState("");
  const userId = session!.user.id;
  const users = useQuery({
    queryKey: protectedQueryKeys.adminUsers(userId, query),
    queryFn: () => api.adminUsers(query),
    enabled: true,
  });
  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    setQuery(draft.trim());
  };
  if (users.isPending) return <PageState kind="loading" title="Loading user accounts" />;
  if (users.isError) return <PageState action={<button className="button" onClick={() => void users.refetch()}>Try again</button>} kind="error" title="User accounts could not be loaded">Check your connection and try again.</PageState>;
  const active = users.data.items.filter((user) => user.isActive).length;
  return (
    <main className="page-stack admin-users-page">
      <header className="page-heading"><div><span>Platform administration</span><h1>User accounts</h1><p>Maintain synthetic account metadata and organisation access. Request content is not available here.</p></div><Link className="button button--primary" to="/admin/users/new"><Plus aria-hidden="true" size={16} />Create user</Link></header>
      <StepUpPanel />
      <dl className="admin-summary" aria-label="Account summary"><div><dt>Active</dt><dd>{active}</dd></div><div><dt>Inactive</dt><dd>{users.data.items.length - active}</dd></div><div><dt>Total shown</dt><dd>{users.data.items.length}</dd></div></dl>
      <section aria-labelledby="account-register-title">
        <div className="admin-register-heading"><div className="section-heading"><span>Identity metadata</span><h2 id="account-register-title">Account register</h2></div><form className="admin-search" onSubmit={submitSearch} role="search"><label className="form-field"><span>Search accounts</span><input onChange={(event) => setDraft(event.target.value)} placeholder="Name, account, role or scope" value={draft} /></label><button className="button" type="submit">Search</button>{query ? <button className="button button--quiet" onClick={() => { setDraft(""); setQuery(""); }} type="button">Clear</button> : null}</form></div>
        {users.data.items.length ? <AdminUserRegister users={users.data.items} /> : <PageState kind="empty" title={query ? "No accounts match this search" : "No user accounts"}>{query ? "Clear the search or try another term." : "Create the first synthetic account."}</PageState>}
      </section>
    </main>
  );
}
