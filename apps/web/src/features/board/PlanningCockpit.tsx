import { useState } from "react";

import type {
  CapacityScenarioSummary,
  PackageChecklist,
  PackageTemplate,
  PlanningCockpit as CockpitData,
  PlanningLane,
} from "../../lib/api/planningEvolutionTypes";
import type { TeamWorkspaceAccess } from "../../lib/api/teamTypes";
import type { Session } from "../../lib/api/types";
import { CapacityScenarioPanel } from "./CapacityScenarioPanel";

type View = "cockpit" | "templates" | "risks" | "scenarios";

const views: Array<{ key: View; label: string }> = [
  { key: "cockpit", label: "Cockpit" },
  { key: "templates", label: "Templates & checklists" },
  { key: "risks", label: "Blockers & dependencies" },
  { key: "scenarios", label: "Capacity scenarios" },
];

export function PlanningCockpit({
  access,
  cockpit,
  scenarios,
  session,
  templates,
}: {
  access: TeamWorkspaceAccess;
  cockpit: CockpitData;
  scenarios: CapacityScenarioSummary[];
  session: Session;
  templates: PackageTemplate[];
}) {
  const [view, setView] = useState<View>("cockpit");
  return (
    <section className="planning-cockpit">
      <header className="planning-cockpit__heading">
        <div>
          <span>Advisory team projection</span>
          <h2>Planning cockpit</h2>
          <p>Backlog, iteration, due risk, WIP and capacity are reconciled without moving a request or assigning a person.</p>
        </div>
        <Freshness data={cockpit} />
      </header>
      <nav aria-label="Planning cockpit views" className="planning-view-tabs">
        {views.map((item) => (
          <button
            aria-pressed={view === item.key}
            key={item.key}
            onClick={() => setView(item.key)}
            type="button"
          >
            {item.label}
          </button>
        ))}
      </nav>
      {view === "cockpit" ? <CockpitView data={cockpit} /> : null}
      {view === "templates" ? (
        <TemplateView checklists={cockpit.checklists} templates={templates} />
      ) : null}
      {view === "risks" ? <RiskView data={cockpit} /> : null}
      {view === "scenarios" ? (
        <CapacityScenarioPanel
          access={access}
          scenarios={scenarios}
          session={session}
          sourceVersion={cockpit.freshness.sourceVersion}
        />
      ) : null}
    </section>
  );
}

function Freshness({ data }: { data: CockpitData }) {
  const date = new Intl.DateTimeFormat("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(data.generatedAt));
  return (
    <div className={`planning-freshness planning-freshness--${data.freshness.health.toLowerCase()}`}>
      <strong>{data.freshness.label}</strong>
      <span>Source v{data.freshness.sourceVersion} · {date}</span>
      <small>Advice only. Human decisions remain explicit.</small>
    </div>
  );
}

function CockpitView({ data }: { data: CockpitData }) {
  const summary = data.summary;
  return (
    <div className="planning-view">
      <section aria-label="Planning summary" className="planning-metrics">
        <PlanningMetric label="Backlog" value={summary.backlogCount} />
        <PlanningMetric label="Active iterations" value={summary.activeIterationCount} />
        <PlanningMetric label="Due risk" value={summary.dueRiskCount} attention={summary.dueRiskCount > 0} />
        <PlanningMetric label="Work in progress" value={summary.wipCount} />
        <PlanningMetric label="Blocked" value={summary.blockedCount} attention={summary.blockedCount > 0} />
        <PlanningMetric label="Available" value={minutes(summary.availableMinutes)} />
        <PlanningMetric label="Reserved" value={minutes(summary.reservedMinutes)} />
      </section>
      <section className="planning-section">
        <header><h3>Work lanes</h3><p>Owner and priority are views of current records, not ranking or automatic assignment.</p></header>
        <div className="planning-lanes">
          {data.lanes.map((lane) => <Lane key={lane.key} lane={lane} />)}
        </div>
      </section>
      <IterationSummary iteration={data.iteration} />
    </div>
  );
}

function PlanningMetric({
  attention = false,
  label,
  value,
}: {
  attention?: boolean;
  label: string;
  value: number | string;
}) {
  return (
    <div className={attention ? "planning-metric planning-metric--attention" : "planning-metric"}>
      <span>{label}</span><strong>{value}</strong>
    </div>
  );
}

function Lane({ lane }: { lane: PlanningLane }) {
  return (
    <section className="planning-lane">
      <header><h4>{lane.label}</h4><span>{lane.items.length}</span></header>
      {lane.items.length === 0 ? <p className="inline-empty">No work in this lane.</p> : (
        <ol>
          {lane.items.map((item) => (
            <li key={`${item.kind}-${item.id}`}>
              <span>{item.reference} · {item.priority}</span>
              <strong>{item.title}</strong>
              <small>{item.ownerDisplayName ?? "Unassigned"} · due {item.dueOn}</small>
              {item.blockerAgeDays !== null || item.dependencyWarningCount > 0 ? (
                <em>{item.blockerAgeDays !== null ? `${item.blockerAgeDays} blocked days` : ""}{item.blockerAgeDays !== null && item.dependencyWarningCount > 0 ? " · " : ""}{item.dependencyWarningCount > 0 ? `${item.dependencyWarningCount} dependency warnings` : ""}</em>
              ) : null}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function IterationSummary({ iteration }: { iteration: CockpitData["iteration"] }) {
  if (!iteration) return <section className="planning-section"><header><h3>Current iteration</h3></header><p className="inline-empty">No active iteration.</p></section>;
  const progress = iteration.committedPoints === 0
    ? 0
    : Math.round((iteration.completedPoints / iteration.committedPoints) * 100);
  return (
    <section className="planning-section iteration-summary">
      <header><div><h3>{iteration.name}</h3><p>{iteration.goal}</p></div><span>{iteration.status}</span></header>
      <div aria-label={`${progress}% of committed points completed`} className="iteration-progress" role="progressbar" aria-valuemax={100} aria-valuemin={0} aria-valuenow={progress}><i style={{ width: `${Math.min(progress, 100)}%` }} /></div>
      <dl>
        <div><dt>Window</dt><dd>{iteration.startsOn} to {iteration.endsOn}</dd></div>
        <div><dt>Points</dt><dd>{iteration.completedPoints} / {iteration.committedPoints}</dd></div>
        <div><dt>Packages</dt><dd>{iteration.completedPackages} / {iteration.committedPackages}</dd></div>
        <div><dt>Factual summary</dt><dd>{iteration.factualSummary ?? "Not completed yet"}</dd></div>
      </dl>
    </section>
  );
}

function TemplateView({
  checklists,
  templates,
}: {
  checklists: PackageChecklist[];
  templates: PackageTemplate[];
}) {
  return (
    <div className="planning-view planning-template-grid">
      <section className="planning-section">
        <header><h3>Team package templates</h3><p>Versioned team guidance. Applying a template never changes request workflow.</p></header>
        {templates.length === 0 ? <p className="inline-empty">No package templates are active.</p> : templates.map((template) => (
          <details key={template.id}>
            <summary>{template.name} <span>v{template.version}</span></summary>
            <p>{template.description}</p>
            <ol>{template.checklist.map((item) => <li key={item.id}>{item.label}{item.required ? " · required" : ""}</li>)}</ol>
          </details>
        ))}
      </section>
      <section className="planning-section">
        <header><h3>Package checklists</h3><p>Completion is factual and does not approve, release or rank work.</p></header>
        {checklists.length === 0 ? <p className="inline-empty">No package checklists are in use.</p> : checklists.map((checklist) => (
          <Checklist key={checklist.packageId} value={checklist} />
        ))}
      </section>
    </div>
  );
}

function Checklist({ value }: { value: PackageChecklist }) {
  return (
    <details>
      <summary>{value.packageTitle} <span>{value.completedCount} / {value.totalCount}</span></summary>
      <p>{value.templateName}</p>
      <ul className="planning-checklist">
        {value.items.map((item) => <li key={item.id}><span aria-hidden="true">{item.completed ? "✓" : "○"}</span>{item.label}{item.required ? " · required" : ""}</li>)}
      </ul>
    </details>
  );
}

function RiskView({ data }: { data: CockpitData }) {
  return (
    <div className="planning-view planning-risk-grid">
      <section className="planning-section">
        <header><h3>Blocker ageing</h3><p>Age highlights waiting work. It does not score an individual.</p></header>
        <Table
          caption="Current package blockers"
          headers={["Package", "Age", "Reason"]}
          rows={data.blockers.map((item) => [item.reference, `${item.ageDays} days`, item.reason])}
        />
      </section>
      <section className="planning-section">
        <header><h3>Dependency warnings</h3><p>Warnings use current package relationships and remain advisory.</p></header>
        <Table
          caption="Current dependency warnings"
          headers={["Package", "Dependency", "Status", "Warning"]}
          rows={data.dependencies.map((item) => [item.reference, item.dependencyReference, item.status, item.warning])}
        />
      </section>
    </div>
  );
}

function Table({ caption, headers, rows }: { caption: string; headers: string[]; rows: string[][] }) {
  if (rows.length === 0) return <p className="inline-empty">No current records.</p>;
  return (
    <div className="team-table-wrap"><table className="team-table"><caption>{caption}</caption><thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead><tbody>{rows.map((row) => <tr key={row.join("-")}>{row.map((value, index) => index === 0 ? <th key={value} scope="row">{value}</th> : <td key={`${index}-${value}`}>{value}</td>)}</tr>)}</tbody></table></div>
  );
}

function minutes(value: number) {
  return `${Math.floor(value / 60)}h ${value % 60}m`;
}
