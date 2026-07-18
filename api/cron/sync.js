import { isAuthorized, synchronizeCatalog } from "../../lib/catalog.js";

export default async function handler(request, response) {
  if (request.method !== "GET" && request.method !== "POST") {
    response.setHeader("Allow", "GET, POST");
    return response.status(405).json({ ok: false, error: "Method not allowed" });
  }

  if (!isAuthorized(request)) {
    return response.status(401).json({ ok: false, error: "Unauthorized" });
  }

  try {
    const result = await synchronizeCatalog({ commit: true });
    return response.status(200).json({
      ok: true,
      changed: result.changed,
      committed: result.committed,
      commitSha: result.commitSha ?? null,
      metrics: result.metrics,
      sources: result.sources
    });
  } catch (error) {
    console.error("Catalog synchronization failed", error);
    return response.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
}
