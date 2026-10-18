// Base44 backend function: the one stable contract between the Strata app and the Fetch agents.
//
// POST https://<your-app>.base44.app/functions/agentApi
// Headers: Content-Type: application/json, x-strata-secret: <STRATA_API_SECRET>
// Body: { "action": "...", ...params }
//
// Keep this file frozen in Base44 (More options → Freeze Files) once it works, so AI edits to the
// UI can never break the agents. Republish the app after any change here.

import { createClientFromRequest } from "npm:@base44/sdk";

const json = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

// Secrets: `base44:runtime` is the current API (read inside the handler); env is the older one.
async function secret(name: string): Promise<string | undefined> {
  try {
    const rt = await import("base44:runtime");
    const value = rt.secrets?.get(name);
    if (value) return value;
  } catch (_) { /* older runtime */ }
  return Deno.env.get(name);
}

export default async function (req: Request): Promise<Response> {
  if (req.method !== "POST") return json({ error: "POST only" }, 405);
  const expected = await secret("STRATA_API_SECRET");
  if (!expected || req.headers.get("x-strata-secret") !== expected) return json({ error: "unauthorized" }, 401);

  const base44 = createClientFromRequest(req);
  const db = base44.asServiceRole.entities;
  let body: Record<string, any>;
  try {
    body = await req.json();
  } catch (_) {
    return json({ error: "invalid JSON" }, 400);
  }

  const one = async (entity: any, query: Record<string, unknown>) => (await entity.filter(query))?.[0] ?? null;

  try {
    switch (body.action) {
      case "getFile": {
        const f = await one(db.DesignFile, { slug: body.file_id });
        return f ? json(f) : json({ error: "no such file" }, 404);
      }
      case "getRules":
        return json(await db.TasteRule.filter({ team_slug: body.team_id }));
      case "getCatalog":
        return json(body.kind ? await db.Asset.filter({ kind: body.kind }) : await db.Asset.list());
      case "getMandate": {
        const m = await one(db.Mandate, { member_id: body.member_id });
        return m ? json(m) : json({ error: "no mandate" }, 404);
      }
      case "uploadPreview": {
        // body.png_b64: base64 PNG from the Renderer agent → permanent public URL for ASI:One cards.
        const bytes = Uint8Array.from(atob(body.png_b64), (c) => c.charCodeAt(0));
        const file = new File([bytes], body.name ?? "preview.png", { type: "image/png" });
        const { file_url } = await base44.asServiceRole.integrations.Core.UploadFile({ file });
        return json({ url: file_url });
      }
      case "fulfil":
        return json(await fulfil(db, body));
      case "history":
        return json(await db.HistoryAtom.filter({ file_slug: body.file_id }, "-created_date", 200));
      default:
        return json({ error: `unknown action ${body.action}` }, 400);
    }
  } catch (err) {
    return json({ error: String(err) }, 500);
  }
}

// Idempotent on payment_ref: a retried call never charges the mandate twice.
async function fulfil(db: any, b: Record<string, any>) {
  const existing = (await db.Licence.filter({ payment_ref: b.payment_ref }))?.[0];
  if (existing) return existing;

  const file = (await db.DesignFile.filter({ slug: b.file_id }))?.[0];
  if (!file) throw new Error("no such file");
  const mandate = (await db.Mandate.filter({ member_id: b.member_id }))?.[0];
  if (!mandate) throw new Error("no mandate");
  const remaining = mandate.limit_cents - mandate.spent_cents;
  if (b.amount_cents > remaining) throw new Error("over mandate");

  await db.Mandate.update(mandate.id, { spent_cents: mandate.spent_cents + b.amount_cents });

  const placements = { ...(file.placements ?? {}) };
  const spots = (file.spots ?? []).map((s: any) =>
    b.spot_ids.includes(s.id) ? { ...s, status: "licensed", note: `${b.licence} licence` } : s
  );
  for (const id of b.spot_ids) placements[id] = b.asset_id;
  await db.DesignFile.update(file.id, { placements, spots });

  const licence_id = `STR-${crypto.randomUUID().slice(0, 4).toUpperCase()}`;
  const record = await db.Licence.create({
    licence_id,
    file_slug: b.file_id,
    asset_id: b.asset_id,
    tier: b.licence,
    spot_ids: b.spot_ids,
    member_id: b.member_id,
    amount_cents: b.amount_cents,
    payment_ref: b.payment_ref,
    via: b.via ?? "ASI:One",
  });
  await db.HistoryAtom.create({
    file_slug: b.file_id,
    kind: "purchase",
    actor_type: "human",
    author_id: b.member_id,
    via: b.via ?? "ASI:One",
    element_ids: b.spot_ids,
    summary: `Bought ${b.asset_id} (${b.licence}) via ${b.via ?? "ASI:One"}`,
    licence_id,
  });
  return { ...record, licence_id };
}
