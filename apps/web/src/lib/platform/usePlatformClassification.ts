import { useQuery } from "@tanstack/react-query";

import { platformSecurityApi } from "../api/platformSecurityClient";

export const platformClassificationKey = ["platform", "classification"] as const;

export function usePlatformClassification() {
  return useQuery({
    queryKey: platformClassificationKey,
    queryFn: platformSecurityApi.classification,
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
    staleTime: 15_000,
  });
}
