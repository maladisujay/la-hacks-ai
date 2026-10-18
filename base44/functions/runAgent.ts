// Base44 backend function: start a CREAO agent run from the app (keys stay server-side).
//
// Called by the Strata UI: base44.functions.invoke("runAgent", { kind, inputs, member_name })
// kind: "curate" | "teammate" | "catchup"
// Secrets: CREAO_<KIND>_APP_ID, CREAO_<KIND>_KEY (capi_...), APP_PUBLIC_URL, STRATA_API_SECRET

import { createClientFromRequest } from "npm:@base44/sdk";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

async function secret(name: string): Promise<string | undefined> {
  try {
    const rt = await import("base44:runtime");
    const value = rt.secrets?.get(name);
    if (value) return value;
  } catch (_) { /* older runtime */ }
  return Deno.env.get(name);
}

const AGENTS: Record<string, string> = { curate: "CURATOR", teammate: "TEAMMATE", catchup: "CATCHUP" };

export default async function (req: Request): Promise<Response> {
  const base44 = createClientFromRequest(req);
  const user = await base44.auth.me().catch(() => null);
  if (!user) return json({ error: "sign in first" }, 401); // only app users may spend agent credits

  const { kind, inputs, member_name } = await req.json();
  const role = AGENTS[kind];
  if (!role) return json({ error: "unknown agent kind" }, 400);

  const appId = await secret(`CREAO_${role}_APP_ID`);
  const key = await secret(`CREAO_${role}_KEY`);
  const publicUrl = (await secret("APP_PUBLIC_URL"))?.replace(/\/$/, "");
  const hookSecret = await secret("STRATA_API_SECRET");
  if (!appId || !key || !publicUrl) return json({ error: "CREAO secrets missing" }, 500);

  const db = base44.asServiceRole.entities;
  const run = await db.AgentRun.create({ kind, status: "queued", inputs, member_name });

  const res = await fetch(`https://agent.creao.ai/api/v1/apps/${appId}/runs`, {
    method: "POST",
    headers: { "Authorization": `Bearer ${key}`, "Content-Type": "application/json" },
    body: JSON.stringify({
      inputs: { ...inputs, member_name },
      webhookUrl: `${publicUrl}/functions/creaoWebhook?s=${encodeURIComponent(hookSecret ?? "")}&r=${run.id}`,
    }),
  });
  if (!res.ok) {
    await db.AgentRun.update(run.id, { status: "failed", result_text: `CREAO ${res.status}` });
    return json({ error: `CREAO ${res.status}` }, 502);
  }
  const created = await res.json();
  await db.AgentRun.update(run.id, { status: "running", run_id: created.id });
  return json({ agent_run_id: run.id, run_id: created.id });
}
