const DECRYPT_DAY_LIBRARY_URL = "https://decrypt.day/library";
const PLAYCOVER_USER_AGENT = "PlayCover/3.1.0 CFNetwork/1494.0.7 Darwin/23.4.0";

export default async function handler(request, response) {
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ ok: false, error: "Method not allowed" });
  }

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 25_000);

  try {
    const upstream = await fetch(DECRYPT_DAY_LIBRARY_URL, {
      method: "GET",
      redirect: "follow",
      cache: "no-store",
      signal: controller.signal,
      headers: {
        Accept: "application/json, text/plain;q=0.9, */*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Cache-Control": "no-cache",
        Pragma: "no-cache",
        Referer: "https://decrypt.day/",
        "User-Agent": PLAYCOVER_USER_AGENT
      }
    });

    const text = await upstream.text();

    if (!upstream.ok) {
      return response.status(upstream.status).json({
        ok: false,
        error: `decrypt.day returned HTTP ${upstream.status}`,
        details: text.slice(0, 300)
      });
    }

    try {
      const payload = JSON.parse(text);
      if (!Array.isArray(payload)) {
        return response.status(502).json({
          ok: false,
          error: "decrypt.day returned JSON, but the root value is not an array"
        });
      }
    } catch {
      return response.status(502).json({
        ok: false,
        error: "decrypt.day returned invalid JSON",
        details: text.slice(0, 300)
      });
    }

    response.setHeader("Access-Control-Allow-Origin", "*");
    response.setHeader("Cache-Control", "public, s-maxage=300, stale-while-revalidate=60");
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    return response.status(200).send(text);
  } catch (error) {
    const message = error?.name === "AbortError"
      ? "decrypt.day request timed out"
      : error instanceof Error
        ? error.message
        : String(error);

    return response.status(502).json({ ok: false, error: message });
  } finally {
    clearTimeout(timer);
  }
}
