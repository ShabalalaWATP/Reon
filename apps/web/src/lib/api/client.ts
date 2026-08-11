import { adminApi } from "./adminClient";
import { authApi } from "./authClient";
import { calendarApi } from "./calendarClient";
import { requestApi } from "./requestClient";
import { platformSecurityApi } from "./platformSecurityClient";
import { statisticsApi } from "./statisticsClient";
import { teamApi } from "./teamClient";
import { workApi } from "./workClient";

export {
  ApiError,
  apiRequest,
  productDownloadUrl,
  SESSION_EXPIRED_EVENT,
} from "./transport";

export const api = {
  ...adminApi,
  ...authApi,
  ...calendarApi,
  ...platformSecurityApi,
  ...requestApi,
  ...statisticsApi,
  ...teamApi,
  ...workApi,
};
