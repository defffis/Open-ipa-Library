import test from "node:test";
import assert from "node:assert/strict";
import { compareVersions, semanticDigest } from "../lib/catalog.js";

test("compareVersions handles numeric segments", () => {
  assert.equal(compareVersions("2.0.0", "1.9.9"), 1);
  assert.equal(compareVersions("1.2", "1.2.0"), 0);
  assert.equal(compareVersions("1.2.0", "1.10.0"), -1);
});

test("semanticDigest ignores catalog and app timestamps", () => {
  const first = {
    sourceUpdateTime: "2026-01-01T00:00:00Z",
    appRepositories: [{ appName: "Demo", appUpdateTime: "2026-01-01T00:00:00Z" }]
  };
  const second = {
    sourceUpdateTime: "2026-07-19T00:00:00Z",
    appRepositories: [{ appName: "Demo", appUpdateTime: "2026-07-19T00:00:00Z" }]
  };
  assert.equal(semanticDigest(first), semanticDigest(second));
});

test("semanticDigest changes when application data changes", () => {
  const first = { appRepositories: [{ appName: "Demo", appVersion: "1.0" }] };
  const second = { appRepositories: [{ appName: "Demo", appVersion: "2.0" }] };
  assert.notEqual(semanticDigest(first), semanticDigest(second));
});
