import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router";

import { PageState } from "../../components/PageState";
import { StatusJourney } from "../../components/StatusJourney";
import { StatusPill } from "../../components/StatusPill";
import { useAuth } from "../../lib/auth/AuthProvider";
import { formatDate } from "../../lib/status";
import { RequestActivity } from "./RequestActivity";
import { RequestCancellation } from "./RequestCancellation";
import { RequestOverview } from "./RequestOverview";
import { RequestConversations } from "./RequestConversations";
import {
  CustomerFeedbackSection,
  CustomerProductSection,
  RequestAttention,
} from "./RequestCustomerSections";
import { useRequestDetail } from "./useRequestDetail";

export function RequestDetailPage() {
  const { requestId = "" } = useParams();
  const { session } = useAuth();
  const controller = useRequestDetail(requestId, session);
  if (controller.request.isPending) {
    return <PageState kind="loading" title="Loading request" />;
  }
  if (controller.request.isError) return <RequestUnavailable />;
  const request = controller.request.data;

  return (
    <main className="page-stack request-workspace">
      <Link className="back-link" to="/requests">
        <ArrowLeft aria-hidden="true" size={16} />
        My requests
      </Link>
      <header className="detail-heading">
        <div>
          <span className="mono-ref">{request.reference}</span>
          <h1>{request.title}</h1>
          <p>
            Submitted by Customer {request.requester.displayName} on {formatDate(request.createdAt)}
            .
          </p>
        </div>
        <StatusPill status={request.status} />
      </header>
      <StatusJourney status={request.status} />
      <RequestAttention request={request} />
      <RequestCancellation request={request} />
      <div className="detail-layout">
        <RequestOverview request={request} />
        <aside aria-label="Activity, released product and feedback" className="detail-aside">
          <RequestConversations
            activityHref="#request-activity"
            key={request.id}
            requestId={request.id}
            status={request.status}
          />
          <RequestActivity
            initialCursor={request.eventsNextCursor}
            initialEvents={request.events}
            key={request.updatedAt}
            requestId={request.id}
          />
          <CustomerProductSection request={request} />
          <CustomerFeedbackSection feedback={controller.feedback} request={request} />
        </aside>
      </div>
    </main>
  );
}

function RequestUnavailable() {
  return (
    <PageState
      action={
        <Link className="button" to="/requests">
          Back to my requests
        </Link>
      }
      kind="error"
      title="Request not available"
    >
      It may no longer exist or you may not have access.
    </PageState>
  );
}
