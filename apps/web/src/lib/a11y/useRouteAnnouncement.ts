import { useEffect, useRef } from "react";
import { useLocation } from "react-router";

import { documentTitleForRoute } from "../routes";

const MAIN_CONTENT_ID = "main-content";

/**
 * Names each page and moves focus to the main region after a navigation, so
 * keyboard and screen-reader users land on the new content. The first render is
 * deliberately left alone: taking focus on initial load is disruptive. The
 * region is addressed by id because the shell renders it several route levels
 * below this hook, and the skip link already targets the same id.
 */
export function useRouteAnnouncement() {
  const { pathname } = useLocation();
  const announced = useRef(pathname);

  useEffect(() => {
    document.title = documentTitleForRoute(pathname);
    if (announced.current === pathname) return;
    announced.current = pathname;
    document.getElementById(MAIN_CONTENT_ID)?.focus();
  }, [pathname]);
}
