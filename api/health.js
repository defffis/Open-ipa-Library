import { rawGithubUrl, runtimeConfig } from "../lib/catalog.js";

export default async function handler(_request, response) {
  const config = runtimeConfig();
  const missing = [];
  if (!process.env.CRON_SECRET) missing.push("CRON_SECRET");
  if (!process.env.GITHUB_TOKEN) missing.push("GITHUB_TOKEN");

  let catalogReachable = false;
  let catalogStatus = null;
  try {
    const upstream = await fetch(rawGithubUrl(config), { method: "HEAD", cache: "no-store" });
    catalogStatus = upstream.status;
    catalogReachable = upstream.ok;
  } catch {
    catalogStatus = null;
  }

  response.setHeader("Cache-Control", "no-store");
  return response.status(missing.length === 0 && catalogReachable ? 200 : 503).json({
    status: missing.length === 0 && catalogReachable ? "ok" : "configuration_required",
    repository: `${config.owner}/${config.repo}`,
    branch: config.branch,
    outputPath: config.outputPath,
    catalogUrl: "/gbox/catalog.json",
    catalogReachable,
    catalogStatus,
    missingEnvironmentVariables: missing
  });
}
