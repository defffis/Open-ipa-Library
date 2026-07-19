import { execFile } from "node:child_process";
import { promisify } from "node:util";

const execFileAsync = promisify(execFile);
const URL = "https://decrypt.day/library";
const USER_AGENT = "PlayCover/3.1.0 CFNetwork/1494.0.7 Darwin/23.4.0";

export default async function handler(request, response) {
  if (request.method !== "GET") {
    response.setHeader("Allow", "GET");
    return response.status(405).json({ ok: false, error: "Method not allowed" });
  }

  try {
    const { stdout, stderr } = await execFileAsync(
      "curl",
      [
        "-sS",
        "--location",
        "--max-time",
        "25",
        URL,
        "-H",
        `User-Agent: ${USER_AGENT}`,
        "-H",
        "Accept: application/json"
      ],
      {
        timeout: 30_000,
        maxBuffer: 15 * 1024 * 1024,
        encoding: "utf8"
      }
    );

    let payload;
    try {
      payload = JSON.parse(stdout);
    } catch {
      return response.status(502).json({
        ok: false,
        error: "curl returned invalid JSON",
        stderr: stderr.slice(0, 300),
        details: stdout.slice(0, 300)
      });
    }

    if (!Array.isArray(payload)) {
      return response.status(502).json({
        ok: false,
        error: "curl returned JSON whose root is not an array"
      });
    }

    response.setHeader("Access-Control-Allow-Origin", "*");
    response.setHeader("Cache-Control", "public, s-maxage=300, stale-while-revalidate=60");
    response.setHeader("Content-Type", "application/json; charset=utf-8");
    return response.status(200).send(stdout);
  } catch (error) {
    return response.status(502).json({
      ok: false,
      error: error instanceof Error ? error.message : String(error),
      code: error?.code ?? null,
      stderr: typeof error?.stderr === "string" ? error.stderr.slice(0, 300) : null,
      stdout: typeof error?.stdout === "string" ? error.stdout.slice(0, 300) : null
    });
  }
}
