// Strata demo UI. Everything the AI says or does comes from CREAO agent runs via the local server.
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (c) => `$${(c / 100).toFixed(2)}`;
const store = { get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

let S = null;
let lastJson = "";
const ui = {
  me: store.get("strata-me", "Alex"), sel: "hero_heading", tab: "history", tryOn: null, licence: "commercial",
  budget: 40, sawOpen: false, showAuth: false, catchOpen: false, review: null, licView: null, paying: false,
};

async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Request failed (${r.status})`);
  return data;
}
function toast(msg) { const t = $("#toast"); t.textContent = msg; t.classList.add("on"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("on"), 4200); }

function when(iso) {
  const d = new Date(iso), now = new Date();
  const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
  const diff = (day(now) - day(d)) / 864e5;
  if (diff === 0) return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", hour12: false });
  if (diff === 1) return "Yesterday";
  return d.toLocaleDateString([], { weekday: "short" });
}
const PROP = { color: "colour", font_size: "size", font_weight: "weight", bg: "background", text: "text" };
const propName = (p) => PROP[p] || String(p || "").replace(/_/g, " ");
const initials = (n) => n.slice(0, 2).toUpperCase();
const member = (n) => S.members[n] || { fill: "#eee", ink: "#555" };
const els = () => Object.values(S.elements).sort((a, b) => a.order - b.order);
const assetOf = (id) => S.catalog.find((a) => a.id === id);
const mine = (kind, extra = () => true) => S.runs.filter((r) => r.kind === kind && r.member === ui.me && extra(r)).slice(-1)[0];
const busy = (r) => r && (r.status === "queued" || r.status === "running");
const dollars = (c) => (c % 100 ? money(c) : `$${c / 100}`);
const cap = (x) => String(x || "")[0]?.toUpperCase() + String(x || "").slice(1);
const lower = (k) => (S.elements[k]?.name || k).toLowerCase();
const leftOf = (m) => { const md = S.mandates[m]; return md.limit_cents - md.spent_cents; };
const toApprove = () => Object.values(S.carts).filter((c) => c.status === "needs_approval" && c.approval_requested && S.mandates[c.member]?.set_by === ui.me);
const issueOf = (k) => S.export.issues.find((i) => i.element_key === k);

function runLine(r, what) {
  if (!r) return "";
  if (busy(r)) {
    const secs = Math.max(0, Math.round((Date.now() - new Date(r.started)) / 1000));
    const src = r.mode === "creao" ? "CREAO agent" : "offline stand-in";
    return `<div class="working"><span>Strata is ${esc(what)}… <span class="meta">(${src}${r.mode === "creao" ? ", about a minute" : ""})</span></span><span class="runtag">${r.run_id && r.run_id !== "offline" ? "run " + esc(r.run_id.slice(0, 8)) + " · " : ""}${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}</span></div>`;
  }
  if (r.status === "failed" && Date.now() - new Date(r.finished) < 60000) return `<div class="failed">The agent couldn't finish: ${esc(r.message)}. Try again.</div>`;
  return "";
}
const sawBox = (saw) => saw && saw.length ? `<details class="saw" ${ui.sawOpen ? "open" : ""}><summary>What Strata saw</summary><ul>${saw.map((x) => `<li>${esc(x)}</li>`).join("")}</ul><div class="never">Never sent to the agent: card number, payment token, anyone's contact details.</div></details>` : "";
const modeTag = (mode, runId) => mode === "creao" ? `<span class="runtag">CREAO${runId ? " · run " + esc(String(runId).slice(0, 8)) : ""}</span>` : mode === "offline" ? `<span class="chip tape">offline stand-in</span>` : "";

// ---------------------------------------------------------------- top bar
function catchCount() {
  const since = S.last_seen[ui.me] || "";
  return S.history.filter((h) => h.at > since && h.author !== ui.me && h.on_behalf_of !== ui.me).length;
}
function renderTop() {
  const modes = Object.values(S.modes);
  const m = modes.every((x) => x === "creao") ? ["creao", "AI: CREAO agent"] : modes.some((x) => x === "creao") ? ["creao", `AI: CREAO (${modes.filter((x) => x === "creao").length}/3 jobs)`] : modes.every((x) => x === "offline") ? ["offline", "AI: offline stand-ins"] : ["missing", "AI: not connected"];
  const n = catchCount(), ap = toApprove();
  $("#top").innerHTML = `
    <div class="brand">Strata</div>
    <div class="file">${esc(S.file.name)}<span class="mono">v.${S.file.version} · client work</span></div>
    <div class="spacer"></div>
    <span class="mode ${m[0]}" title="Every shortlist, edit and catch-up is decided by a CREAO agent">${m[1]}</span>
    ${ap.length ? `<button class="linkish approve-count" data-act="approvals">${ap.length} to approve</button>` : ""}
    <button class="linkish" data-act="catch">≡ Catch me up ${n ? `<span class="count">${n} new</span>` : ""}</button>
    <div class="avatars">${Object.values(S.members).map((p) => `<button class="av ${p.name === ui.me ? "me" : ""}" title="Viewing as ${esc(p.name)} (${esc(p.role)})" aria-label="View as ${esc(p.name)}, ${esc(p.role)}" aria-pressed="${p.name === ui.me}" style="background:${p.fill};color:${p.ink}" data-me="${esc(p.name)}">${esc(initials(p.name))}</button>`).join("")}<span class="av ai" title="Strata, the AI teammate" aria-label="Strata, the AI teammate" role="img">S</span></div>
    <button class="btn quiet" data-act="export">Export for client</button>
    <button class="btn ${ui.tab === "shop" ? "dark" : ""}" data-act="shop">Asset shop</button>`;
}

// ---------------------------------------------------------------- layers
const ICON = { nav: "▭", heading: "T", text: "¶", button: "▭", illustration_slot: "◫", icon_row: "▭" };
function renderRail() {
  $("#rail").innerHTML = `<div class="label">Layers</div>
    <div class="layer frame"><span class="ico">#</span>Desktop — Landing</div>
    ${els().map((e) => `<div class="layer child ${e.key === ui.sel ? "sel" : ""}" data-sel="${e.key}" tabindex="0" role="button" aria-pressed="${e.key === ui.sel}"><span class="ico">${ICON[e.kind]}</span>${esc(e.name)}<span class="mark ${e.authorship === "ai" ? "ai" : ""}"></span></div>`).join("")}
    <div class="layer frame"><span class="ico">#</span>Mobile — Landing</div>
    <div class="legend"><div><span class="ai"></span>Drafted by Strata, in pencil</div><div><span></span>Inked by a person</div></div>`;
}

// ---------------------------------------------------------------- canvas (the client's page has its own brand)
function elAttrs(e) {
  const bad = issueOf(e.key);
  return `class="el ${e.authorship} ${e.key === ui.sel ? "sel" : ""} ${bad ? "lic-issue" : ""}" data-sel="${e.key}" tabindex="0" role="button" aria-label="${esc(e.name)}"`;
}
const issueTag = (k) => { const i = issueOf(k); return i ? `<span class="lic-tag">${i.licence_id ? "personal license" : "no license"}</span>` : ""; };
function renderCanvas() {
  const E = S.elements, h = E.hero_heading.props, sub = E.hero_subcopy.props, b = E.cta_button.props;
  const slot = E.hero_illustration, placed = slot.props.asset_id, tryAny = ui.tryOn && assetOf(ui.tryOn);
  const tryAsset = tryAny && tryAny.kind !== "icon_set" ? tryAny : null, tryIcons = tryAny && tryAny.kind === "icon_set" ? tryAny : null;
  let slotHtml;
  if (tryAsset) slotHtml = `<div class="slot try"><span class="tag" style="color:var(--ink)">trying on · ${esc(tryAsset.title)}</span><img src="/assets/${tryAsset.id}.png" alt=""><div class="watermark">PREVIEW · STRATA · PREVIEW</div></div>`;
  else if (placed) {
    const lic = S.licences.find((l) => l.status === "active" && l.asset_id === placed && l.element_keys.includes("hero_illustration"));
    slotHtml = `<div class="slot placed">${lic ? `<span class="tag" style="color:var(--ink)">licensed · ${esc(assetOf(placed)?.title)}</span>` : ""}<img src="/assets/${esc(placed)}.png" alt="${esc(assetOf(placed)?.title)}"></div>`;
  }
  else slotHtml = `<div class="slot draft"><span class="tag">pencil draft</span><svg width="140" height="90" viewBox="0 0 140 90" fill="none" stroke="#6A90B8" stroke-width="1.5" stroke-dasharray="4 4"><circle cx="100" cy="22" r="12"/><path d="M6 72c18-10 28-22 44-12s26 8 40-6 26-16 44-20"/><path d="M6 84h128" stroke-dasharray="0"/></svg></div>`;
  const icons = tryIcons ? tryIcons.id : E.feature_row.props.asset_id;
  const locked = E.hero_heading.locked_props.includes("color") && E.hero_heading.locked_by;
  $("#canvas").innerHTML = `
    <div class="frame-label">Desktop — Landing · 1280 <label><input type="checkbox" data-act="auth" aria-label="Show who made what" ${ui.showAuth ? "checked" : ""}> Show who made what</label></div>
    <div class="sample ${ui.showAuth ? "auth" : ""}">
      <div ${elAttrs(E.nav)}><div class="s-nav"><div class="s-logo">${esc(E.nav.props.text)}</div><div class="s-links">${E.nav.props.links.map((l) => `<span>${esc(l)}</span>`).join("")}</div></div></div>
      <div class="s-hero">
        <div>
          <h1 ${elAttrs(E.hero_heading)} style="color:${esc(h.color)};font-size:${+h.font_size}px;font-weight:${+h.font_weight}"><span class="s-h1" style="display:block;margin:0">${esc(h.text)}</span></h1>
          <p ${elAttrs(E.hero_subcopy)}><span class="s-sub" style="display:block;margin:0;color:${esc(sub.color)};font-size:${+sub.font_size}px">${esc(sub.text)}</span></p>
          <div ${elAttrs(E.cta_button)} style="display:inline-block"><span class="s-btn" style="background:${esc(b.bg)};color:${esc(b.color)}">${esc(b.text)}</span></div>
        </div>
        <div ${elAttrs(slot)}>${slotHtml}${issueTag(slot.key)}</div>
      </div>
      <div ${elAttrs(E.feature_row)}>${tryIcons ? `<span class="lic-tag try-tag">trying on · ${esc(tryIcons.title)}</span>` : issueTag("feature_row")}<div class="s-features ${tryIcons ? "trying" : ""}">${E.feature_row.props.items.map(([t, d]) => `<div class="s-feat">${icons ? `<img src="/assets/${esc(icons)}.png" alt="">` : ""}<b>${esc(t)}</b><span>${esc(d)}</span></div>`).join("")}</div></div>
    </div>
    ${locked ? `<div class="note">keep the navy. it's the brand, not a mood. — ${esc(locked[0])}.</div>` : ""}`;
  document.querySelectorAll("#canvas h1.el, #canvas p.el").forEach((n) => { n.style.margin = n.tagName === "H1" ? "0 0 18px" : "0 0 22px"; });
}

// ---------------------------------------------------------------- panel
function renderTabs() {
  $("#tabs").innerHTML = [["history", "History"], ["shop", "Shop"], ["rules", "Team rules"], ["licences", "Licenses"]]
    .map(([k, l]) => `<button class="${ui.tab === k ? "on" : ""}" data-tab="${k}">${l}</button>`).join("");
}
function who(h) { return h.actor === "ai" ? `Strata, for ${h.on_behalf_of || "the team"}` : h.author; }
function conflictCard(c) {
  const lockedByMe = ui.me === c.locked_by || ui.me === "Priya";
  const val = c.locked_value && /^#/.test(c.locked_value) ? `<span class="swatch" style="background:${esc(c.locked_value)}"></span> ${esc(c.locked_value)}` : esc(c.locked_value);
  return `<div class="card-tape"><div><b>Strata stopped before changing the ${esc(propName(c.prop))}.</b></div>
    <div style="margin-top:6px">${esc(c.member)} asked: <b>“${esc(c.request || c.wants)}”</b>${c.request && /^#[0-9a-f]{6}$/i.test(c.wants) ? ` <span class="swatch" style="background:${esc(c.wants)}"></span> ${esc(c.wants)}` : ""}. ${esc(c.locked_by)} locked the ${esc(propName(c.prop))} at ${val}.</div>
    ${c.reason ? `<div class="why" style="color:var(--tape-text);border-color:var(--tape-text)">${esc(c.reason)}</div>` : ""}
    <div class="row">${lockedByMe ? `<button class="btn" data-conf="${c.id}" data-choice="keep">Keep ${esc(c.locked_by)}'s</button><button class="btn quiet" data-conf="${c.id}" data-choice="use">Use ${esc(c.member)}'s</button>` : ""}
    ${c.status === "open" && ui.me === c.member ? `<button class="btn quiet" data-conf="${c.id}" data-choice="ask">Ask ${esc(c.locked_by)}</button>` : ""}
    ${c.status === "asked" && !lockedByMe ? `<span class="meta">Waiting for ${esc(c.locked_by)}</span>` : ""}</div></div>`;
}
function renderHistory() {
  const e = S.elements[ui.sel];
  const hs = S.history.filter((h) => h.element_key === e.key).sort((a, b) => (a.at < b.at ? 1 : -1));
  const people = new Set(hs.filter((h) => h.actor === "human").map((h) => h.author));
  const conflicts = S.conflicts.filter((c) => c.element_key === e.key && (c.status === "open" || c.status === "asked"));
  const lock = e.locked_props.length ? `<div class="lockline"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="2" y="5.5" width="8" height="5.5" rx="1"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>${cap(e.locked_props.map(propName).join(", "))} locked by ${esc(e.locked_by)}${e.props.color ? ` · <span class="swatch" style="background:${esc(e.props.color)}"></span>` : ""}</div>` : "";
  return `<div class="label">Provenance</div><h2>${esc(e.name)}</h2>
    <p class="sub">${hs.length ? `${hs.length} change${hs.length === 1 ? "" : "s"}${people.size ? ` by ${people.size} ${people.size === 1 ? "person" : "people"}` : ""}${hs.some((h) => h.actor === "ai") ? ` · ${hs.filter((h) => h.actor === "ai").length} drafted by Strata` : ""}` : "No changes yet"}</p>
    ${lock}${conflicts.map(conflictCard).join("")}
    <ul class="tl">${hs.map((h) => {
      const ai = h.actor === "ai", m = member(h.author);
      return `<li><span class="dot ${ai ? "ai" : ""}" style="${ai ? "" : `border-color:${m.ink};background:${m.fill}`}"></span>
        <div class="who ${ai ? "ai" : ""}"><span>${esc(who(h))}</span><span class="mono">${when(h.at)}</span></div>
        <div class="what ${h.status === "undone" ? "struck" : ""}">${esc(h.summary)}</div>
        ${h.status === "undone" ? `<div class="what">Undone by ${esc(h.undone_by)}. Strata learns from that.</div>` : ""}
        ${h.ai_reason ? `<div class="why">${esc(h.ai_reason)}</div>` : ""}
        ${h.status === "proposed" ? `<div class="verdict"><button class="btn" data-judge="${h.id}" data-v="keep">Keep</button><button class="btn quiet" data-judge="${h.id}" data-v="undo">Undo</button></div>` : ""}
        ${h.status === "kept" && h.kept_by ? `<div class="meta" style="margin-top:4px">Kept by ${esc(h.kept_by)}</div>` : ""}</li>`;
    }).join("")}</ul>`;
}

function spotKey() { return S.elements[ui.sel]?.kind === "icon_row" ? "feature_row" : "hero_illustration"; }
function renderShop() {
  const spot = spotKey(), el = S.elements[spot];
  const sl = S.shortlists[`${ui.me}:${spot}`];
  const r = mine("curate", (x) => (x.spot_key || "hero_illustration") === spot);
  const md = S.mandates[ui.me], left = md.limit_cents - md.spent_cents;
  const chosen = ui.tryOn && assetOf(ui.tryOn);
  const price = chosen ? chosen.prices[ui.licence] : 0;
  let html = `<div class="label">Asset shop</div><h2>For the ${esc(el.name.toLowerCase())}</h2>
    <p class="sub">Strata ranks the catalog by what your team keeps and undoes. Click one to try it on. Nothing is bought yet.</p>
    <div class="controls"><div class="seg">${["personal", "commercial", "extended"].map((l) => `<button class="${ui.licence === l ? "on" : ""}" data-lic="${l}">${l[0].toUpperCase() + l.slice(1)}</button>`).join("")}</div>
      <span class="budget">up to $<input data-budget value="${esc(ui.budget)}" inputmode="numeric" aria-label="Budget in dollars"></span>
      <button class="btn ai" data-act="curate" ${busy(r) ? "disabled" : ""}>${sl ? "Re-rank with Strata" : "Ask Strata for a shortlist"}</button></div>
    ${runLine(r, "ranking the catalog against your team's taste")}`;
  if (sl) {
    html += `<div class="ainote"><span class="s">S</span><div><div class="sum" title="${esc(sl.summary)}">${esc(sl.summary)}</div><div style="margin-top:4px">${modeTag(sl.mode, sl.run_id)}</div>${sawBox(sl.saw)}</div></div>
      <div class="items">${sl.items.map((i) => {
        const a = assetOf(i.asset_id); if (!a) return "";
        const bad = i.breaks && i.breaks.length;
        return `<div class="item ${ui.tryOn === a.id ? "on" : ""}" data-try="${esc(a.id)}" tabindex="0" role="button" aria-pressed="${ui.tryOn === a.id}" aria-label="Try on ${esc(a.title)}"><img src="/assets/${a.id}.png" alt="">
          <div><div class="t">${esc(a.title)}</div><div class="c">${esc(a.creator)} · ${esc(a.style)}, ${a.colours} colour${a.colours > 1 ? "s" : ""}</div>
          <div class="w ${bad ? "bad" : ""}">${esc(i.why)}</div></div><div class="p">${money(a.prices[ui.licence])}</div></div>`;
      }).join("")}</div>`;
  } else if (!busy(r)) {
    html += `<div class="card-ok" style="background:var(--sunken);color:var(--graphite)">No shortlist yet. Strata's Curator agent reads your team's rules, ${esc(ui.me)}'s spending limit and the catalog, then explains each pick.</div>`;
  }
  if (chosen) {
    const over = price > left || !md.allowed_licences.includes(ui.licence);
    const pct = (x) => `${Math.min(100, (x / md.limit_cents) * 100)}%`;
    html += `<div class="buybar"><div class="row"><span>${esc(cap(ui.licence))} license · ${esc(chosen.title)}</span><span class="mono" style="font-size:16px">${money(price)}</span></div>
      <div class="bar"><i class="spent" style="width:${pct(md.spent_cents)}"></i><i class="${over ? "over" : "this"}" style="width:${pct(Math.min(price, left))}"></i></div>
      <div class="meta">${!md.allowed_licences.includes(ui.licence) ? `${esc(cap(ui.licence))} isn't in ${esc(ui.me)}'s limit · ${esc(md.set_by)} can approve` : over ? `Over ${esc(ui.me)}'s ${money(md.limit_cents)} limit · ${esc(md.set_by)} can approve` : `Within ${esc(ui.me)}'s ${money(md.limit_cents)} monthly limit · ${money(left - price)} left after this`}</div>
      <button class="btn dark" data-act="review">Review and buy</button></div>`;
  }
  return html;
}

function renderRules() {
  return `<div class="label">What Strata has learned</div><h2>Team rules</h2><p class="sub">Learned from what people keep and undo. Each Keep or Undo on an AI edit changes these numbers.</p>
    ${S.rules.map((r) => {
      const conf = (r.kept + 1) / (r.kept + r.undone + 2);
      const chip = r.scope === "team" ? `<span class="chip">Team</span>` : r.scope === "personal" ? `<span class="chip" style="background:${member(r.members[0]).fill};color:${member(r.members[0]).ink};border-color:transparent">Only for ${esc(r.members[0])}</span>` : `<span class="chip ai">Split</span>`;
      return `<div class="rule ${r.scope}"><div class="rt">${esc(r.text)}</div>
        <div class="rm">${chip}${r.members.map((n) => `<span class="mini" style="background:${member(n).fill};color:${member(n).ink}">${initials(n)}</span>`).join("")}
        <span class="mono meta">kept ${r.kept} · undone ${r.undone}</span>${r.pinned ? `<span class="meta">pinned</span>` : ""}</div>
        ${r.scope === "split" ? `<div class="meta" style="margin-top:6px;color:var(--ai-text)">Strata won't apply this; it asks instead.</div>` : `<div class="conf"><i style="width:${conf * 100}%"></i></div>`}</div>`;
    }).join("")}
    <p class="meta" style="margin-top:16px">Team rules need two people agreeing. Personal rules follow one person. Split rules become questions, never edits.</p>`;
}

function renderLicences() {
  if (ui.licView && S.licences.some((l) => l.licence_id === ui.licView)) return renderLicDetail(S.licences.find((l) => l.licence_id === ui.licView));
  return `<div class="label">Licenses</div><h2>What this file may ship</h2><p class="sub">Every license is tied to the elements that use it. Click one to see how it got here.</p>
    ${S.licences.map((l) => {
      const a = assetOf(l.asset_id);
      return `<div class="lic" data-licid="${esc(l.licence_id)}" tabindex="0" role="button" aria-label="License ${esc(l.licence_id)}, ${esc(a?.title)}"><img src="/assets/${esc(l.asset_id)}.png" alt=""><div><b>${esc(a?.title)}</b> · ${esc(l.tier)}<div class="meta">${l.element_keys.map((k) => esc(S.elements[k]?.name || k)).join(", ")} · bought by ${esc(l.member)} · <span class="mono">${esc(l.licence_id)}</span></div>
        ${l.status === "upgraded" ? `<span class="chip">upgraded</span>` : l.tier === "personal" && S.file.client_work ? `<span class="chip tape">not for client work</span>` : `<span class="chip ok">ok for client work</span>`}</div><div class="mono">${money(l.amount_cents)}</div></div>`;
    }).join("")}`;
}

function renderLicDetail(l) {
  const a = assetOf(l.asset_id) || {}, md = S.mandates[l.member];
  const row = (k, v) => `<div class="kv"><span>${esc(k)}</span><span>${v}</span></div>`;
  const how = l.how || [`Bought by ${l.member}`, `placed on the ${l.element_keys.map(lower).join(", ")}`];
  return `<button class="linkish back" data-act="lic-back">← All licenses</button>
    <div class="label">License</div><h2>${esc(S.elements[l.element_keys[0]]?.name || a.title)}</h2>
    <p class="sub">${esc(a.title)} · bought by ${esc(l.member)} ${/:/.test(when(l.at)) ? "at" : "on"} ${esc(when(l.at))}${l.status === "upgraded" ? " · since upgraded" : ""}</p>
    <div class="kvs">
      ${row("License", `<span class="mono">${esc(l.licence_id)} · ${esc(l.tier)}</span>`)}
      ${row("Creator", esc(a.creator))}
      ${row("Paid", `<span class="mono">${money(l.paid_cents ?? l.amount_cents)}${l.card ? ` · ${esc(l.card)}` : ""}</span>`)}
      ${md ? row("Limit left", `<span class="mono">${money(Math.max(0, leftOf(l.member)))} of ${dollars(md.limit_cents)}</span>`) : ""}
      ${row("Covers", l.element_keys.map((k) => `<div>${esc(S.elements[k]?.name || k)}</div>`).join(""))}
    </div>
    <div class="label" style="margin-top:22px">How it got here</div>
    <p class="how">${how.map(esc).join(" → ")}</p>`;
}

const TIERS = [["personal", "Personal", "Not for client work"], ["commercial", "Commercial", "Tally's site and app · what this file needs"], ["extended", "Extended", "Print and merchandise"]];
function trailSteps(c) {
  const lead = S.mandates[c.member]?.set_by, has = (s) => c.trail.some((t) => t.step === s);
  const steps = c.trail.map((t) => ({ st: t.ok === false ? "warn" : "done", t: t.step, x: t.text }));
  if (c.status === "needs_approval") steps.push({ st: "current", t: "Approval", x: c.approval_requested ? `Waiting for ${lead}'s OK.` : `${lead} needs to approve this one purchase.` });
  if (!has("Payment")) steps.push({ st: c.status === "ready" || c.status === "paying" ? "current" : "pending", t: "Payment", x: `Visa ending ${S.payment_method.last4}, simulated. The agent never sees the card.` });
  if (!has("Receipt")) steps.push({ st: "pending", t: "Receipt", x: `License filed against the ${lower(c.element_key)}` });
  return steps;
}
function renderReview() {
  const c = S.carts[ui.review], a = assetOf(c.asset_id) || {}, lead = S.mandates[c.member]?.set_by;
  const locked = c.status !== "ready" && c.status !== "needs_approval" && c.status !== "declined";
  const tiers = c.upgrade_of ? [["commercial", "Commercial", `Upgrade from the personal license ${c.upgrade_of}`]] : TIERS;
  const body = `<div class="label">Review</div><h2>${c.upgrade_of ? "Upgrade" : "Buy"} ${esc(a.title)}</h2>
    <p class="sub">by ${esc(a.creator)} · goes on the ${esc(lower(c.element_key))}</p>
    <div class="radios" role="radiogroup" aria-label="License">${tiers.map(([k, n, d]) => `<label class="radio ${c.licence === k ? "on" : ""}">
      <input type="radio" name="tier" value="${k}" data-tier ${c.licence === k ? "checked" : ""} ${locked || c.upgrade_of ? "disabled" : ""}>
      <span><b>${n}</b><span class="d">${esc(d)}</span></span><span class="mono">${dollars(c.upgrade_of ? c.amount_cents : a.prices[k])}</span></label>`).join("")}</div>
    ${S.file.client_work && c.licence === "personal" ? `<div class="warn-inline">This file is client work. A personal license can't ship to a client.</div>` : ""}
    <div class="label" style="margin-top:22px">Paper trail</div>
    <ul class="ptrail">${trailSteps(c).map((s) => `<li class="${s.st}"><span class="pt" aria-hidden="true">${s.st === "done" ? `<svg width="9" height="9" viewBox="0 0 9 9" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M1.5 4.6l2 2 4-4.4"/></svg>` : ""}</span><b>${esc(s.t)}</b><div>${esc(s.x)}</div></li>`).join("")}</ul>
    <button class="linkish back" data-act="back">← Back to shop</button>`;
  let foot;
  if ((c.status === "ready" || c.status === "paying") && ui.me !== c.member) {
    foot = `<button class="btn pay" disabled>Approved · ${esc(c.member)} can pay now</button>`;
  } else if (c.status === "ready" || c.status === "paying") {
    const going = ui.paying || c.status === "paying";
    foot = `<button class="btn dark pay" data-act="pay" ${going ? "disabled" : ""}>${going ? "Authorizing with Visa (simulated)…" : `Pay ${money(c.amount_cents)}`}</button>`;
  } else if (ui.me === lead && c.member !== lead) {
    foot = `<button class="btn dark pay" data-act="approve">Approve ${money(c.amount_cents)} for ${esc(c.member)}</button>`;
  } else if (c.approval_requested) {
    foot = `<button class="btn pay" disabled>Waiting for ${esc(lead)}'s OK</button>`;
  } else {
    foot = `<button class="btn dark pay" data-act="ask-approval">Ask ${esc(lead)} to approve</button>`;
  }
  return [body, `${foot}<div class="foot-note">Test mode · simulated Visa payment · nothing real is charged</div>`];
}

function renderGuard() {
  const x = S.export;
  if (x.ok) return `<div class="guard ok">Every asset in this file is licensed for client work.</div>`;
  return `<div class="guard"><div class="mono gl">before you export for a client</div>${x.issues.map((i) => {
    const what = i.kind === "icon_set" ? "icons" : "art", where = lower(i.element_key);
    return `<p>${i.licence_id ? `The “${esc(i.asset)}” ${what} in the ${esc(where)} ${what === "icons" ? "are" : "is"} on ${esc(i.member)}'s personal license. Client work needs commercial.` : `The “${esc(i.asset)}” ${what} in the ${esc(where)} ${what === "icons" ? "have" : "has"} no license yet.`}</p>
      <div class="row">${i.licence_id ? `<button class="btn dark" data-upgrade="${esc(i.licence_id)}" data-asset="${esc(i.asset_id)}" data-el="${esc(i.element_key)}">Upgrade for ${dollars(i.upgrade_cents)}</button>` : ""}
      <button class="btn" data-swap="${esc(i.element_key)}">Swap the ${what}</button></div>`;
  }).join("")}</div>`;
}

function renderPanel() {
  if (ui.review && !S.carts[ui.review]) ui.review = null;
  const review = ui.review && renderReview();
  $("#tabs").style.display = review ? "none" : "";
  if (!review) renderTabs();
  const body = review ? review[0] : { history: renderHistory, shop: renderShop, rules: renderRules, licences: renderLicences }[ui.tab]();
  const b = $("#panel-body"), keepScroll = b.scrollTop, focused = document.activeElement?.hasAttribute?.("data-budget");
  b.innerHTML = body;
  b.scrollTop = keepScroll;
  if (focused) { const i = b.querySelector("[data-budget]"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
  const foot = review ? review[1] : ui.tab === "licences" && !ui.licView ? renderGuard() : "";
  $("#panel-foot").innerHTML = foot;
  $("#panel-foot").className = review ? "pay-foot" : foot ? "guard-foot" : "";
  const e = S.elements[ui.sel], canEdit = Object.keys(S.editable[e.kind] || {}).length > 0;
  $("#ask").style.display = ui.tab === "history" && !review ? "" : "none";
  $("#ask-form").style.display = canEdit ? "" : "none";
  $("#ask-input").placeholder = `Ask Strata about this ${e.name.toLowerCase()}…`;
  const topic = { heading: /heading/i, text: /copy|text|tint/i, button: /button/i, nav: /nav/i }[e.kind] || /$^/;
  const rules = S.rules.filter((r) => r.scope !== "split" && topic.test(r.text) && (r.scope === "team" || r.members.includes(ui.me)));
  $("#ask-rule").textContent = !canEdit ? "Strata edits text and style here; use the shop for art and icons." : rules.length ? `Rules in play: ${rules.map((r) => r.text.toLowerCase()).join(" · ")}` : "No team rules about this element yet; Strata will learn from your Keep and Undo.";
  $("#ask-status").innerHTML = canEdit ? runLine(mine("teammate", (r) => r.element_key === ui.sel), "thinking about this " + e.name.toLowerCase()) : "";
}

// ---------------------------------------------------------------- catch-up popover
function renderPop() {
  document.querySelector(".pop")?.remove();
  if (!ui.catchOpen) return;
  const c0 = S.catchups[ui.me], c = c0 && c0.at > (S.last_seen[ui.me] || "") ? c0 : null, r = mine("catchup");
  const pop = document.createElement("div");
  pop.className = "pop";
  const btn = document.querySelector('[data-act="catch"]')?.getBoundingClientRect();
  pop.style.left = `${Math.max(16, Math.min(window.innerWidth - 396, (btn ? btn.left : 600) - 20))}px`;
  pop.innerHTML = `<div class="label">Since you were here, ${esc(ui.me)}</div>
    ${c ? `<ul>${c.lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>${c.question ? `<div class="ainote"><span class="s">?</span><div>${esc(c.question)}</div></div>` : ""}<div style="margin:8px 0">${modeTag(c.mode, c.run_id)}</div>${sawBox(c.saw)}` : `<p class="sub" style="margin-top:8px">${catchCount()} changes by others since you last looked.</p>`}
    ${runLine(r, "reading what changed")}
    <div style="display:flex;gap:8px;margin-top:10px"><button class="btn ai" data-act="catchup" ${busy(r) ? "disabled" : ""}>${c ? "Refresh" : "Catch me up"}</button><button class="btn quiet" data-act="seen">Mark as seen</button></div>`;
  document.body.appendChild(pop);
}

function focusKey() {
  const f = document.activeElement;
  if (!f || f === document.body) return null;
  const k = ["sel", "try", "tab", "act", "me", "licid", "tier"].find((x) => f.dataset && x in f.dataset);
  return k ? `[data-${k}="${CSS.escape(f.dataset[k])}"]${k === "tier" ? `[value="${CSS.escape(f.value)}"]` : ""}` : null;
}
function render() {
  if (!S) return;
  if (!S.elements[ui.sel]) ui.sel = "hero_heading";
  const fk = focusKey();
  renderTop(); renderRail(); renderCanvas(); renderPanel(); renderPop();
  if (fk && (document.activeElement === document.body || !document.activeElement)) document.querySelector(fk)?.focus({ preventScroll: true });
}

// ---------------------------------------------------------------- actions
async function refresh(force) {
  const s = await api("/api/state");
  const j = JSON.stringify(s);
  const live = s.runs.some(busy);
  if (force || j !== lastJson || live) { lastJson = j; S = s; render(); }
}
async function act(fn) { try { await fn(); await refresh(true); } catch (e) { toast(e.message); await refresh(true).catch(() => {}); } }
const newCart = (body) => act(async () => { const c = await api("/api/cart", { member: ui.me, ...body }); ui.review = c.id; ui.licView = null; });
const openShop = (k) => { ui.review = null; ui.tab = "shop"; ui.sel = k || "hero_illustration"; ui.tryOn = null; render(); };

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("[data-sel],[data-tab],[data-me],[data-act],[data-try],[data-lic],[data-judge],[data-conf],[data-upgrade],[data-swap],[data-licid]");
  if (!t) return;
  const d = t.dataset;
  if (d.sel) { ui.sel = d.sel; if (ui.tab === "shop" && !["hero_illustration", "feature_row"].includes(d.sel)) ui.tab = "history"; ui.tryOn = ui.tab === "shop" ? ui.tryOn : null; if (ui.review && S.carts[ui.review]?.element_key !== d.sel) ui.review = null; return render(); }
  if (d.tab) { ui.tab = d.tab; ui.licView = null; if (d.tab !== "shop") ui.tryOn = null; else if (!["hero_illustration", "feature_row"].includes(ui.sel)) ui.sel = "hero_illustration"; return render(); }
  if (d.me) { if (ui.review) { ui.review = null; ui.tab = "shop"; } ui.me = d.me; store.set("strata-me", d.me); ui.tryOn = null; return render(); }
  if (d.try) { ui.tryOn = d.try; return render(); }
  if (d.lic) { ui.licence = d.lic; return render(); }
  if (d.licid) { ui.licView = d.licid; return render(); }
  if (d.swap) return openShop(d.swap);
  if (d.judge) return act(() => api(`/api/history/${d.judge}/${d.v}`, { member: ui.me }));
  if (d.conf) return act(() => api(`/api/conflicts/${d.conf}`, { member: ui.me, choice: d.choice }));
  if (d.upgrade) return newCart({ asset_id: d.asset, licence: "commercial", element_key: d.el, upgrade_of: d.upgrade });
  switch (d.act) {
    case "shop": return openShop();
    case "auth": ui.showAuth = t.checked; return render();
    case "catch": ui.catchOpen = !ui.catchOpen; return render();
    case "seen": ui.catchOpen = false; return act(() => api("/api/seen", { member: ui.me }));
    case "catchup": return act(() => api("/api/agents/catchup", { member: ui.me }));
    case "curate": { const b = parseFloat(ui.budget); if (!Number.isFinite(b)) ui.budget = "40"; return act(() => api("/api/agents/curate", { member: ui.me, spot_key: spotKey(), licence: ui.licence, budget_cents: Math.round((Number.isFinite(b) ? b : 40) * 100) })); }
    case "review": return newCart({ asset_id: ui.tryOn, licence: ui.licence, element_key: spotKey() });
    case "back": return openShop(S.carts[ui.review]?.element_key);
    case "ask-approval": return act(() => api(`/api/cart/${ui.review}/ask`, { member: ui.me }));
    case "approve": return act(() => api(`/api/cart/${ui.review}/approve`, { member: ui.me }));
    case "approvals": { const c = toApprove()[0]; if (c) { ui.review = c.id; ui.sel = c.element_key; ui.tab = "shop"; ui.tryOn = c.asset_id; } return render(); }
    case "pay": {
      if (ui.paying) return;
      ui.paying = true; render();
      const id = ui.review;
      return act(async () => {
        try { const c = await api(`/api/cart/${id}/pay`, { member: ui.me }); if (c.status === "paid") { ui.review = null; ui.tab = "licences"; ui.licView = c.licence_id; ui.tryOn = null; ui.sel = c.element_key; } }
        finally { ui.paying = false; }
      });
    }
    case "export": ui.review = null; ui.tab = "licences"; ui.licView = null; ui.tryOn = null; return render();
    case "lic-back": ui.licView = null; return render();
  }
});
document.addEventListener("change", (ev) => {
  const t = ev.target;
  if (!t.hasAttribute("data-tier") || !ui.review) return;
  const c = S.carts[ui.review];
  ui.licence = t.value;
  newCart({ asset_id: c.asset_id, licence: t.value, element_key: c.element_key });
});
document.addEventListener("toggle", (ev) => { if (ev.target.classList?.contains("saw")) ui.sawOpen = ev.target.open; }, true);
document.addEventListener("input", (ev) => { if (ev.target.hasAttribute("data-budget")) ui.budget = ev.target.value.replace(/[^0-9.]/g, ""); });
$("#ask-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const q = $("#ask-input").value.trim().slice(0, 500);
  if (!q) return toast("Tell Strata what to change first.");
  $("#ask-input").value = "";
  act(() => api("/api/agents/teammate", { member: ui.me, element_key: ui.sel, request: q }));
});
document.addEventListener("keydown", (ev) => {
  if ((ev.key === "Enter" || ev.key === " ") && ev.target.matches?.("[data-sel],[data-try],[data-licid]")) { ev.preventDefault(); ev.target.click(); return; }
  if (ev.key === "Escape") { ui.catchOpen = false; render(); }
});

(async () => {
  await refresh(true);
  setInterval(() => refresh(false).catch(() => {}), 1500);
})();
