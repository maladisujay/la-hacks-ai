// Base44 backend function: CREAO calls this when an agent run finishes.
// Must answer 2xx within 10 s; delivery is at least once, so it is idempotent on run status.

import { createClientFromRequest } from "npm:@base44/sdk";

async function secret(name: string): Promise<string | undefined> {
  try {
    const rt = await import("base44:runtime");
    const value = rt.secrets?.get(name);
    if (value) return value;
  } catch (_) { /* older runtime */ }
  return Deno.env.get(name);
}

export default async function (req: Request): Promise<Response> {
  const url = new URL(req.url);
  if (url.searchParams.get("s") !== (await secret("STRATA_API_SECRET"))) {
    return new Response("unauthorized", { status: 401 });
  }
  const agentRunId = url.searchParams.get("r");
  const payload = await req.json().catch(() => ({}));
  const base44 = createClientFromRequest(req);
  const db = base44.asServiceRole.entities;

  if (agentRunId) {
    const current = await db.AgentRun.get(agentRunId).catch(() => null);
    if (current && current.status !== "completed") {
      await db.AgentRun.update(agentRunId, {
        status: payload.status === "completed" ? "completed" : "failed",
        result_text: payload.result?.text ?? payload.result?.chatText ?? "",
      });
    }
  }
  return new Response("ok");
}
