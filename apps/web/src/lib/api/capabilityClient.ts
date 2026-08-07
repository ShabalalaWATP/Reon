import { apiRequest } from "./client";

export type ServerCapabilities = {
  myWork: boolean;
  notifications: boolean;
  configuration: boolean;
  products: boolean;
  managedFileUploads: boolean;
  planning: boolean;
  statistics: boolean;
};

export const disabledCapabilities: ServerCapabilities = Object.freeze({
  myWork: false,
  notifications: false,
  configuration: false,
  products: false,
  managedFileUploads: false,
  planning: false,
  statistics: false,
});

export const capabilityApi = {
  capabilities: () => apiRequest<ServerCapabilities>("/me/capabilities"),
};
