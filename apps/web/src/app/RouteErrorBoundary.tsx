import { Component, type ErrorInfo, type ReactNode } from "react";

interface RouteErrorBoundaryProps {
  actionLabel?: string;
  children: ReactNode;
  description?: string;
  onReload: () => void;
  resetKey?: string;
}

interface RouteErrorBoundaryState {
  failed: boolean;
}

export class RouteErrorBoundary extends Component<
  RouteErrorBoundaryProps,
  RouteErrorBoundaryState
> {
  state: RouteErrorBoundaryState = { failed: false };

  static getDerivedStateFromError(): RouteErrorBoundaryState {
    return { failed: true };
  }

  componentDidCatch(error: Error, information: ErrorInfo) {
    console.error("The active Mist view could not be rendered.", error, information);
  }

  componentDidUpdate(previous: RouteErrorBoundaryProps) {
    if (this.state.failed && previous.resetKey !== this.props.resetKey) {
      this.setState({ failed: false });
    }
  }

  render() {
    if (!this.state.failed) return this.props.children;

    return (
      <main className="page-stack page-stack--narrow">
        <header className="page-heading">
          <div>
            <span>View unavailable</span>
            <h1>This page could not be displayed</h1>
            <p>
              {this.props.description ??
                "Your session is still active. Reload the workspace to try the request again."}
            </p>
          </div>
        </header>
        <button className="button button--primary" onClick={this.props.onReload} type="button">
          {this.props.actionLabel ?? "Reload workspace"}
        </button>
      </main>
    );
  }
}
