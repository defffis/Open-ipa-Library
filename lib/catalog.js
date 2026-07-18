import { createHash } from "node:crypto";

const DEFAULT_OWNER = "defffis";
const DEFAULT_REPO = "Open-ipa-Library";
const DEFAULT_BRANCH = "main";
const DEFAULT_OUTPUT_PATH = "output/catalog.json";
const DEFAULT_SOURCES_PATH = "config/sources.json";
const DEFAULT_DEFAULTS_PATH = "config/defaults.json";

function env(name, fallback = "") {
  const value = process.env[name];
  return typeof value === "string" && value.trim() ? value.trim() : fallback;
}

function intEnv(name, fallback, minimum = 0, maximum = Number.MAX_SAFE_INTEGER) {
  const parsed = Number.parseInt(env(name), 10);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.min(maximum, Math.max(minimum, parsed));
}

export function runtimeConfig() {
  return {
    owner: env("GITHUB_OWNER", DEFAULT_OWNER),
    repo: env("GITHUB_REPO", DEFAULT_REPO),
    branch: env("GITHUB_BRANCH", DEFAULT_BRANCH),
    outputPath: env("GITHUB_OUTPUT_PATH", DEFAULT_OUTPUT_PATH),
    sourcesPath: env("GITHUB_SOURCES_PATH", DEFAULT_SOURCES_PATH),
    defaultsPath: env("GITHUB_DEFAULTS_PATH", DEFAULT_DEFAULTS_PATH),
    githubToken: env("GITHUB_TOKEN"),
    timeoutMs: intEnv("SOURCE_TIMEOUT_MS", 20_000, 1_000, 55_000),
    concurrency: intEnv("SOURCE_CONCURRENCY", 4, 1, 10),
    minimumApplications: intEnv("MIN_APPLICATIONS", 1, 1, 1_000_000),
    maximumRemovalPercent: intEnv("MAX_REMOVAL_PERCENT", 70, 0, 100)
  };
}

function githubHeaders(token, mediaType = "application/vnd.github+json") {
  const headers = {
    Accept: mediaType,
    "X-GitHub-Api-Version": "2022-11-28",
    "User-Agent": "Open-ipa-Library-Vercel"
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

function contentsUrl(config, path) {
  const encodedPath = path.split("/").map(encodeURIComponent).join("/");
  return `https://api.github.com/repos/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/contents/${encodedPath}?ref=${encodeURIComponent(config.branch)}`;
}

export function rawGithubUrl(config, path = config.outputPath) {
  return `https://raw.githubusercontent.com/${encodeURIComponent(config.owner)}/${encodeURIComponent(config.repo)}/${encodeURIComponent(config.branch)}/${path.split("/").map(encodeURIComponent).join("/")}`;
}

async function fetchWithTimeout(url, options = {}, timeoutMs = 20_000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function readGithubFile(config, path, { optional = false } = {}) {
  const response = await fetchWithTimeout(
    contentsUrl(config, path),
    { headers: githubHeaders(config.githubToken), cache: "no-store" },
    Math.min(config.timeoutMs, 20_000)
  );

  if (response.status === 404 && optional) return null;
  if (!response.ok) {
    throw new Error(`GitHub read failed for ${path}: HTTP ${response.status}`);
  }

  const payload = await response.json();
  if (!payload || payload.type !== "file" || typeof payload.content !== "string") {
    throw new Error(`GitHub returned an unsupported object for ${path}`);
  }

  return {
    sha: payload.sha,
    text: Buffer.from(payload.content.replace(/\n/g, ""), "base64").toString("utf8")
  };
}

function asNonEmptyString(value) {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function safeHttpsUrl(value) {
  const raw = asNonEmptyString(value);
  if (!raw) return null;
  try {
    const parsed = new URL(raw);
    return parsed.protocol === "https:" ? parsed.toString() : null;
  } catch {
    return null;
  }
}

function directImageUrl(value) {
  const url = safeHttpsUrl(value);
  if (!url) return null;
  const parsed = new URL(url);
  if (/\.(?:png|jpe?g|webp|gif|avif)(?:$|[?#])/i.test(parsed.href)) return url;
  if (/(?:^|\.)mzstatic\.com$/i.test(parsed.hostname)) return url;
  return null;
}

async function resolveImage(value, fallback, timeoutMs) {
  const direct = directImageUrl(value);
  if (direct) return direct;

  const lookupUrl = safeHttpsUrl(value);
  if (!lookupUrl || !/itunes\.apple\.com\/lookup/i.test(lookupUrl)) return fallback;

  try {
    const response = await fetchWithTimeout(
      lookupUrl,
      { headers: { Accept: "application/json", "User-Agent": "Open-ipa-Library-Vercel" } },
      Math.min(timeoutMs, 10_000)
    );
    if (!response.ok) return fallback;
    const data = await response.json();
    const result = Array.isArray(data?.results) ? data.results[0] : null;
    return (
      directImageUrl(result?.artworkUrl512) ||
      directImageUrl(result?.artworkUrl100) ||
      directImageUrl(result?.artworkUrl60) ||
      fallback
    );
  } catch {
    return fallback;
  }
}

function parseVersionParts(version) {
  return String(version ?? "0")
    .toLowerCase()
    .split(/[._+\-]/)
    .map((part) => (/^\d+$/.test(part) ? Number(part) : part));
}

export function compareVersions(left, right) {
  const a = parseVersionParts(left);
  const b = parseVersionParts(right);
  const length = Math.max(a.length, b.length);

  for (let i = 0; i < length; i += 1) {
    const av = a[i] ?? 0;
    const bv = b[i] ?? 0;
    if (av === bv) continue;
    if (typeof av === "number" && typeof bv === "number") return av > bv ? 1 : -1;
    if (typeof av === "number") return 1;
    if (typeof bv === "number") return -1;
    return String(av).localeCompare(String(bv), "en", { numeric: true, sensitivity: "base" });
  }
  return 0;
}

function normalizeDownloadUrl(value) {
  const url = safeHttpsUrl(value);
  if (!url) return null;
  const parsed = new URL(url);
  parsed.hash = "";
  for (const key of [...parsed.searchParams.keys()]) {
    if (/^(?:utm_|fbclid$|gclid$|ref$|source$)/i.test(key)) parsed.searchParams.delete(key);
  }
  return parsed.toString();
}

function appIdentity(app) {
  if (app.bundleId) return `bundle:${app.bundleId.toLowerCase()}`;
  if (app.packageUrl) return `url:${app.packageUrl}`;
  return `name:${app.name.toLowerCase()}@${String(app.version).toLowerCase()}`;
}

function normalizePlayCoverRoot(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.apps)) return payload.apps;
  if (Array.isArray(payload?.applications)) return payload.applications;
  if (Array.isArray(payload?.data)) return payload.data;
  throw new Error("PlayCover source root must be an array");
}

async function mapPlayCoverApp(raw, source, defaults, categoryIndex, timeoutMs) {
  if (!raw || typeof raw !== "object") return null;

  const name = asNonEmptyString(raw.name ?? raw.appName ?? raw.title);
  const packageUrl = normalizeDownloadUrl(raw.link ?? raw.downloadURL ?? raw.downloadUrl ?? raw.appPackage);
  if (!name || !packageUrl) return null;

  const version = asNonEmptyString(raw.version ?? raw.appVersion) ?? "0.0.0";
  const bundleId = asNonEmptyString(raw.bundleID ?? raw.bundleId ?? raw.bundle_id);
  const image = await resolveImage(
    raw.itunesLookup ?? raw.image ?? raw.icon ?? raw.appImage,
    defaults.fallbackAppImage,
    timeoutMs
  );

  return {
    sourceId: source.id,
    sourceName: source.name,
    priority: Number.isFinite(Number(source.priority)) ? Number(source.priority) : 100,
    bundleId,
    name,
    version,
    packageUrl,
    image,
    categoryIndex
  };
}

async function fetchPlayCoverSource(source, defaults, categoryIndex, config) {
  const url = safeHttpsUrl(source.catalogUrl ?? source.url);
  if (!url) throw new Error("catalogUrl must be a valid HTTPS URL");

  const retries = Math.max(0, Math.min(3, Number.parseInt(source.retries ?? "1", 10) || 0));
  const timeoutMs = Math.max(1_000, Math.min(config.timeoutMs, Number(source.timeoutSec) > 0 ? Number(source.timeoutSec) * 1_000 : config.timeoutMs));
  let lastError;

  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await fetchWithTimeout(
        url,
        { headers: { Accept: "application/json", "User-Agent": "Open-ipa-Library-Vercel" }, cache: "no-store" },
        timeoutMs
      );
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const payload = await response.json();
      const rows = normalizePlayCoverRoot(payload);
      const mapped = await Promise.all(rows.map((row) => mapPlayCoverApp(row, source, defaults, categoryIndex, timeoutMs)));
      return mapped.filter(Boolean);
    } catch (error) {
      lastError = error;
      if (attempt < retries) await new Promise((resolve) => setTimeout(resolve, 400 * 2 ** attempt));
    }
  }

  throw new Error(lastError instanceof Error ? lastError.message : String(lastError));
}

async function mapWithConcurrency(items, concurrency, worker) {
  const results = new Array(items.length);
  let cursor = 0;

  async function run() {
    while (true) {
      const index = cursor;
      cursor += 1;
      if (index >= items.length) return;
      results[index] = await worker(items[index], index);
    }
  }

  await Promise.all(Array.from({ length: Math.min(concurrency, items.length) }, run));
  return results;
}

function sourceCategory(source) {
  return asNonEmptyString(source.category ?? source.options?.category) ?? "Apps";
}

function selectWinner(current, candidate) {
  if (!current) return candidate;
  if (candidate.priority !== current.priority) return candidate.priority < current.priority ? candidate : current;
  const versionResult = compareVersions(candidate.version, current.version);
  if (versionResult !== 0) return versionResult > 0 ? candidate : current;
  const currentScore = Number(Boolean(current.bundleId)) + Number(Boolean(current.image));
  const candidateScore = Number(Boolean(candidate.bundleId)) + Number(Boolean(candidate.image));
  return candidateScore > currentScore ? candidate : current;
}

function gboxDate(date = new Date()) {
  return date.toISOString().replace(/\.\d{3}Z$/, "Z");
}

function toGBoxApp(app, updateTime, appType) {
  const details = [`Источник: ${app.sourceName}`];
  if (app.bundleId) details.push(`Bundle ID: ${app.bundleId}`);

  return {
    appType,
    appCateIndex: app.categoryIndex,
    appUpdateTime: updateTime,
    appName: app.name,
    appVersion: app.version,
    appImage: app.image,
    appPackage: app.packageUrl,
    appDescription: details.join("\n")
  };
}

function normalizedDefaults(raw, config) {
  const repositoryUrl = `https://github.com/${config.owner}/${config.repo}`;
  const rawBase = `https://raw.githubusercontent.com/${config.owner}/${config.repo}/${config.branch}`;
  const categories = Array.isArray(raw?.appCategories) && raw.appCategories.length
    ? raw.appCategories.map(asNonEmptyString).filter(Boolean)
    : ["Apps"];

  return {
    version: asNonEmptyString(raw?.version) ?? "1.0",
    sourceName: asNonEmptyString(process.env.GBOX_SOURCE_NAME) ?? asNonEmptyString(raw?.sourceName) ?? "PlayCover to GBox",
    sourceAuthor: asNonEmptyString(process.env.GBOX_SOURCE_AUTHOR) ?? asNonEmptyString(raw?.sourceAuthor) ?? config.owner,
    sourceLinkTitle: asNonEmptyString(raw?.sourceLinkTitle) ?? "GitHub Repository",
    sourceLinkUrl: (asNonEmptyString(raw?.sourceLinkUrl) ?? repositoryUrl).replace("https://github.com/<owner>/<repo>", repositoryUrl),
    sourceImage: (asNonEmptyString(raw?.sourceImage) ?? `${rawBase}/docs/source.png`).replace("https://raw.githubusercontent.com/<owner>/<repo>/main", rawBase),
    sourceDescription: asNonEmptyString(process.env.GBOX_SOURCE_DESCRIPTION) ?? asNonEmptyString(raw?.sourceDescription) ?? "Daily generated GBox catalog from PlayCover sources.",
    defaultAppType: asNonEmptyString(process.env.GBOX_DEFAULT_APP_TYPE) ?? asNonEmptyString(raw?.defaultAppType) ?? "SELF_SIGN",
    fallbackAppImage: (asNonEmptyString(process.env.GBOX_FALLBACK_ICON) ?? asNonEmptyString(raw?.fallbackAppImage) ?? `${rawBase}/docs/fallback-icon.png`).replace("https://raw.githubusercontent.com/<owner>/<repo>/main", rawBase),
    appCategories: categories
  };
}

export async function buildCatalog({ config = runtimeConfig(), now = new Date() } = {}) {
  const [sourcesFile, defaultsFile] = await Promise.all([
    readGithubFile(config, config.sourcesPath),
    readGithubFile(config, config.defaultsPath)
  ]);

  const allSources = JSON.parse(sourcesFile.text);
  if (!Array.isArray(allSources)) throw new Error("config/sources.json must contain an array");
  const defaults = normalizedDefaults(JSON.parse(defaultsFile.text), config);

  const sources = allSources
    .filter((source) => source?.enabled !== false)
    .filter((source) => source?.adapter === "playcover_json" || source?.type === "playcover_json")
    .filter((source) => safeHttpsUrl(source.catalogUrl ?? source.url));

  if (sources.length === 0) throw new Error("No enabled PlayCover JSON sources with a valid HTTPS URL");

  const sourceCategories = [...new Set(sources.map(sourceCategory))];
  const categories = [...defaults.appCategories];
  for (const category of sourceCategories) if (!categories.includes(category)) categories.push(category);

  const status = await mapWithConcurrency(sources, config.concurrency, async (source) => {
    const categoryIndex = categories.indexOf(sourceCategory(source));
    try {
      const apps = await fetchPlayCoverSource(source, defaults, categoryIndex, config);
      return { id: source.id, name: source.name, ok: true, apps, error: null };
    } catch (error) {
      return {
        id: source.id,
        name: source.name,
        ok: false,
        apps: [],
        error: error instanceof Error ? error.message : String(error)
      };
    }
  });

  const successfulSources = status.filter((entry) => entry.ok);
  if (successfulSources.length === 0) {
    throw new Error(`All PlayCover sources failed: ${status.map((entry) => `${entry.id}: ${entry.error}`).join("; ")}`);
  }

  const winners = new Map();
  let received = 0;
  for (const entry of successfulSources) {
    received += entry.apps.length;
    for (const app of entry.apps) {
      const key = appIdentity(app);
      winners.set(key, selectWinner(winners.get(key), app));
    }
  }

  const updateTime = gboxDate(now);
  const apps = [...winners.values()]
    .sort((a, b) => a.categoryIndex - b.categoryIndex || a.name.localeCompare(b.name, "ru", { sensitivity: "base" }) || compareVersions(b.version, a.version))
    .map((app) => toGBoxApp(app, updateTime, defaults.defaultAppType));

  const catalog = {
    version: defaults.version,
    sourceName: defaults.sourceName,
    sourceAuthor: defaults.sourceAuthor,
    sourceLinkTitle: defaults.sourceLinkTitle,
    sourceLinkUrl: defaults.sourceLinkUrl,
    sourceImage: defaults.sourceImage,
    sourceUpdateTime: updateTime,
    sourceDescription: defaults.sourceDescription,
    appCategories: categories,
    appRepositories: apps
  };

  return {
    catalog,
    status,
    metrics: {
      configuredSources: sources.length,
      successfulSources: successfulSources.length,
      failedSources: status.length - successfulSources.length,
      receivedApplications: received,
      publishedApplications: apps.length,
      duplicatesRemoved: received - apps.length
    }
  };
}

function semanticCatalog(catalog) {
  return {
    ...catalog,
    sourceUpdateTime: null,
    appRepositories: Array.isArray(catalog?.appRepositories)
      ? catalog.appRepositories.map((app) => ({ ...app, appUpdateTime: null }))
      : []
  };
}

export function semanticDigest(catalog) {
  return createHash("sha256").update(JSON.stringify(semanticCatalog(catalog))).digest("hex");
}

function applicationCount(catalog) {
  return Array.isArray(catalog?.appRepositories) ? catalog.appRepositories.length : 0;
}

function applyExistingTimestamp(nextCatalog, previousCatalog) {
  const timestamp = asNonEmptyString(previousCatalog?.sourceUpdateTime) ?? nextCatalog.sourceUpdateTime;
  return {
    ...nextCatalog,
    sourceUpdateTime: timestamp,
    appRepositories: nextCatalog.appRepositories.map((app) => ({ ...app, appUpdateTime: timestamp }))
  };
}

function enforceSafety(nextCatalog, previousCatalog, config) {
  const nextCount = applicationCount(nextCatalog);
  const previousCount = applicationCount(previousCatalog);

  if (nextCount < config.minimumApplications) {
    throw new Error(`Safety check failed: ${nextCount} apps is below MIN_APPLICATIONS=${config.minimumApplications}`);
  }

  if (previousCount > 1 && nextCount < previousCount) {
    const removalPercent = ((previousCount - nextCount) / previousCount) * 100;
    if (removalPercent > config.maximumRemovalPercent) {
      throw new Error(`Safety check failed: catalog would remove ${removalPercent.toFixed(1)}% of apps`);
    }
  }
}

async function updateGithubFile(config, file, text) {
  if (!config.githubToken) throw new Error("GITHUB_TOKEN is required to commit catalog updates");

  const response = await fetchWithTimeout(
    contentsUrl(config, config.outputPath).replace(/\?ref=.*$/, ""),
    {
      method: "PUT",
      headers: { ...githubHeaders(config.githubToken), "Content-Type": "application/json" },
      body: JSON.stringify({
        message: "chore: update GBox catalog via Vercel Cron",
        content: Buffer.from(text, "utf8").toString("base64"),
        sha: file?.sha,
        branch: config.branch
      })
    },
    Math.min(config.timeoutMs, 30_000)
  );

  if (!response.ok) {
    const body = await response.text();
    throw new Error(`GitHub update failed: HTTP ${response.status} ${body.slice(0, 500)}`);
  }
  return response.json();
}

export async function synchronizeCatalog({ commit = true, now = new Date() } = {}) {
  const config = runtimeConfig();
  const [built, currentFile] = await Promise.all([
    buildCatalog({ config, now }),
    readGithubFile(config, config.outputPath, { optional: true })
  ]);

  let previousCatalog = null;
  if (currentFile?.text) {
    try {
      previousCatalog = JSON.parse(currentFile.text);
    } catch {
      previousCatalog = null;
    }
  }

  enforceSafety(built.catalog, previousCatalog, config);

  const changed = !previousCatalog || semanticDigest(built.catalog) !== semanticDigest(previousCatalog);
  const finalCatalog = changed ? built.catalog : applyExistingTimestamp(built.catalog, previousCatalog);
  const text = `${JSON.stringify(finalCatalog, null, 2)}\n`;

  if (!commit || !changed) {
    return {
      ok: true,
      changed,
      committed: false,
      catalog: finalCatalog,
      metrics: built.metrics,
      sources: built.status.map(({ apps, ...entry }) => ({ ...entry, applicationCount: apps.length }))
    };
  }

  const githubResult = await updateGithubFile(config, currentFile, text);
  return {
    ok: true,
    changed: true,
    committed: true,
    commitSha: githubResult?.commit?.sha ?? null,
    catalog: finalCatalog,
    metrics: built.metrics,
    sources: built.status.map(({ apps, ...entry }) => ({ ...entry, applicationCount: apps.length }))
  };
}

export function isAuthorized(request) {
  const secret = env("CRON_SECRET");
  if (!secret) return false;
  const header = request.headers?.authorization ?? request.headers?.get?.("authorization");
  return header === `Bearer ${secret}`;
}
