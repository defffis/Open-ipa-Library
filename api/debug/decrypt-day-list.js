import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const UA = "PlayCover/3.1.0 CFNetwork/1494.0.7 Darwin/23.4.0";

export default async function handler(request, response) {
  try {
    const target = typeof request.query?.url === "string" ? request.query.url : "https://decrypt.day/app/list";
    if (!target.startsWith("https://decrypt.day/")) {
      return response.status(400).json({ ok: false, error: "Invalid URL" });
    }
    const { stdout } = await execFileAsync("curl", ["-sS", "--location", "--max-time", "25", target, "-H", `User-Agent: ${UA}`], {
      timeout: 30000,
      maxBuffer: 20 * 1024 * 1024,
      encoding: "utf8"
    });
    const hrefs = [...stdout.matchAll(/href=["']([^"']+)["']/gi)].map((m) => m[1]);
    const appHrefs = [...new Set(hrefs.filter((h) => /\/app\//.test(h)))];
    const pageHrefs = [...new Set(hrefs.filter((h) => /(?:page|offset|cursor|start)=/i.test(h)))];
    const scripts = [...new Set([...stdout.matchAll(/<script[^>]+src=["']([^"']+)["']/gi)].map((m) => m[1]))];
    return response.status(200).json({
      ok: true,
      target,
      htmlLength: stdout.length,
      appHrefCount: appHrefs.length,
      firstAppHrefs: appHrefs.slice(0, 20),
      pageHrefs: pageHrefs.slice(0, 50),
      scripts,
      textStart: stdout.slice(0, 1500)
    });
  } catch (error) {
    return response.status(502).json({ ok: false, error: error instanceof Error ? error.message : String(error) });
  }
}
