import { apiRequest } from "./client";

export type ServerCapabilities = {
  conversationReads: boolean;
  conversationWrites: boolean;
  contextSwitching: boolean;
  myWork: boolean;
  notifications: boolean;
  configuration: boolean;
  products: boolean;
  managedFileUploads: boolean;
  planning: boolean;
  statistics: boolean;
};

export const disabledCapabilities: ServerCapabilities = Object.freeze({
  conversationReads: false,
  conversationWrites: false,
  contextSwitching: false,
  myWork: false,
  notifications: false,
  configuration: false,
  products: false,
  managedFileUploads: false,
  planning: false,
  statistics: false,
});

export const capabilityApi = {
  capabilities: async () => normaliseCapabilities(await apiRequest<unknown>("/me/capabilities")),
};

function normaliseCapabilities(value: unknown): ServerCapabilities {
  const source = isRecord(value) ? value : {};
  return {
    conversationReads: source.conversationReads === true,
    conversationWrites: source.conversationWrites === true,
    contextSwitching: source.contextSwitching === true,
    myWork: source.myWork === true,
    notifications: source.notifications === true,
    configuration: source.configuration === true,
    products: source.products === true,
    managedFileUploads: source.managedFileUploads === true,
    planning: source.planning === true,
    statistics: source.statistics === true,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
