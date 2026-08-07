import { readFileSync } from "node:fs";
import path from "node:path";
import process from "node:process";
import { describe, expect, it } from "vitest";

const config = readFileSync(path.resolve(process.cwd(), "nginx.conf"), "utf8");

describe("local web container boundary", () => {
  it("rejects unrecognised hosts and hides the nginx version", () => {
    expect(config).toContain("listen 80 default_server;");
    expect(config).toContain("server_name localhost 127.0.0.1;");
    expect(config).toContain("return 444;");
    expect(config.match(/server_tokens off;/g)).toHaveLength(2);
  });

  it.each([
    "Content-Security-Policy",
    "frame-ancestors 'none'",
    "X-Frame-Options",
    "X-Content-Type-Options",
    "Referrer-Policy",
    "Permissions-Policy",
  ])("sets the %s response protection", (protection) => {
    expect(config).toContain(protection);
  });

  it("forwards a trusted proxy host and replaces client forwarding claims", () => {
    expect(config).toContain("proxy_set_header Host $proxy_host;");
    expect(config).toContain("proxy_set_header X-Forwarded-For $remote_addr;");
    expect(config).not.toContain("$proxy_add_x_forwarded_for");
    expect(config).toContain("try_files $uri $uri/ /index.html;");
  });
});
