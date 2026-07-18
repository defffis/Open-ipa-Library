import { isAuthorized, synchronizeCatalog } from "../lib/catalog.js";

export default async function handler(request, response) {
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ ok: false, error: "Method not allowed" });
  }

  if (!isAuthorized(request)) {
    return response.status(401).json({ ok: false, error: "Unauthorized" });
  }

  try {
    const result = await synchronizeCatalog({ commit: false });
    response.setHeader("Cache-Control", "no-store");
    return response.status(200).json(result);
  } catch (error) {
    return response.status(500).json({
      ok: false,
      error: error instanceof Error ? error.message : String(error)
    });
  }
}
