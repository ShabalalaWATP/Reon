import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, expect, it } from "vitest";

const config = readFileSync(path.resolve(process.cwd(), "nginx.conf"), "utf8");
const dockerfile = readFileSync(
  path.resolve(process.cwd(), "Dockerfile"),
  "utf8",
);

describe("local web container boundary", () => {
  it("rejects unrecognised hosts and hides the nginx version", () => {
    expect(config).toContain("listen 8080 default_server;");
    expect(config).toContain("server_name localhost 127.0.0.1;");
    expect(config).toContain("return 444;");
    expect(config.match(/server_tokens off;/g)).toHaveLength(2);
    expect(config.match(/access_log off;/g)).toHaveLength(2);
  });

  it.each([
    "Content-Security-Policy",
    "frame-ancestors 'none'",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
    "Cross-Origin-Opener-Policy",
    "Cross-Origin-Embedder-Policy",
    "Cross-Origin-Resource-Policy",
  ])("sets the %s response protection", (protection) => {
    expect(config).toContain(protection);
  });

  it("forwards a trusted proxy host and replaces client forwarding claims", () => {
    expect(config).toContain("proxy_set_header Host $proxy_host;");
    expect(config).toContain("proxy_set_header X-Forwarded-For $remote_addr;");
    expect(config).not.toContain("$proxy_add_x_forwarded_for");
    expect(config).toContain("try_files $uri $uri/ /index.html;");
    expect(config).toContain("location = /index.html");
    expect(config).toContain("expires -1;");
  });

  it("re-resolves the fixed API service after a Compose container replacement", () => {
    expect(config).toContain("resolver 127.0.0.11 valid=10s ipv6=off;");
    expect(config).toContain("set $api_upstream api:8000;");
    expect(config).toContain("proxy_pass http://$api_upstream;");
  });

  it("uses the patched non-root runtime and handles both nginx pid paths", () => {
    expect(dockerfile).toContain("FROM nginx:1.31.3-alpine@sha256:");
    expect(dockerfile).toContain("/var/run/nginx.pid");
    expect(dockerfile).toContain("/run/nginx.pid");
    expect(dockerfile).toContain("grep -qx 'pid /tmp/nginx.pid;'");
    expect(dockerfile).toContain("USER 101:101");
  });

  it("uses the supported digest-pinned Node 24 LTS builder", () => {
    expect(dockerfile).toMatch(/FROM node:24-alpine@sha256:[a-f0-9]{64} AS build/u);
    expect(dockerfile).not.toContain("node:25");
    expect(dockerfile).toMatch(
      /^# syntax=docker\/dockerfile-upstream:master@sha256:[a-f0-9]{64}$/mu,
    );
  });

  it("buffers larger request and proxy bodies on the writable temporary filesystem", () => {
    expect(config).toContain(
      "client_body_temp_path /tmp/nginx-client-temp;",
    );
    expect(config).toContain("proxy_temp_path /tmp/nginx-proxy-temp;");
    expect(dockerfile).toContain("mkdir -p /tmp/nginx-client-temp");
  });
});
