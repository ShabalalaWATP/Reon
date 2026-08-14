type LoadMoreButtonProps = {
  hasMore: boolean;
  loading: boolean;
  onLoad: () => void;
};

export function LoadMoreButton({ hasMore, loading, onLoad }: LoadMoreButtonProps) {
  if (!hasMore) return null;
  return (
    <button
      className="button button--quiet load-more"
      disabled={loading}
      onClick={onLoad}
      type="button"
    >
      {loading ? "Loading more…" : "Load more"}
    </button>
  );
}
