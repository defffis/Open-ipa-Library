import { rawGithubUrl, runtimeConfig } from "../lib/catalog.js";

export default async function handler(request, response) {
  if (request.method !== "GET" && request.method !== "HEAD") {
    response.setHeader("Allow", "GET, HEAD");
    return response.status(405).json({ ok: false, error: "Method not allowed" });
  }

  const config = runtimeConfig();
  const upstream = await fetch(rawGithubUrl(config), {
    headers: { Accept: "application/json", "User-Agent": "Open-ipa-Library-Vercel" },
    cache: "no-store"
  });

  if (!upstream.ok) {
    return response.status(502).json({
      ok: false,
      error: `Catalog upstream returned HTTP ${upstream.status}`
    });
  }

  const text = await upstream.text();
  try {
    JSON.parse(text);
  } catch {
    return response.status(502).json({ ok: false, error: "Catalog upstream returned invalid JSON" });
  }

  response.setHeader("Content-Type", "application/json; charset=utf-8");
  response.setHeader("Cache-Control", "public, s-maxage=300, stale-while-revalidate=3600");
  response.setHeader("Access-Control-Allow-Origin", "*");
  response.setHeader("X-Content-Type-Options", "nosniff");
  return request.method === "HEAD" ? response.status(200).end() : response.status(200).send(text);
}
