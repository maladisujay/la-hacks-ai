// Strata demo UI. Everything the AI says or does comes from CREAO agent runs via the local server.
const $ = (s) => document.querySelector(s);
const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const money = (c) => `$${(c / 100).toFixed(2)}`;
const store = { get: (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } }, set: (k, v) => { try { localStorage.setItem(k, v); } catch {} } };

let S = null;
let lastJson = "";
const ui = {
  me: store.get("strata-me", "Alex"), sel: "hero_heading", tab: "history", tryOn: null, licence: "commercial",
  budget: 40, showAuth: false, catchOpen: false, overlay: null, cart: null, exportCheck: null,
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
const initials = (n) => n.slice(0, 2).toUpperCase();
const member = (n) => S.members[n] || { fill: "#eee", ink: "#555" };
const els = () => Object.values(S.elements).sort((a, b) => a.order - b.order);
const assetOf = (id) => S.catalog.find((a) => a.id === id);
const mine = (kind, extra = () => true) => S.runs.filter((r) => r.kind === kind && r.member === ui.me && extra(r)).slice(-1)[0];
const busy = (r) => r && (r.status === "queued" || r.status === "running");

function runLine(r, what) {
  if (!r) return "";
  if (busy(r)) {
    const secs = Math.max(0, Math.round((Date.now() - new Date(r.started)) / 1000));
    const src = r.mode === "creao" ? "CREAO agent" : "offline stand-in";
    return `<div class="working"><span>Strata is ${esc(what)}… <span class="meta">(${src}, usually 1–3 min)</span></span><span class="runtag">${r.run_id && r.run_id !== "offline" ? "run " + esc(r.run_id.slice(0, 8)) + " · " : ""}${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, "0")}</span></div>`;
  }
  if (r.status === "failed" && Date.now() - new Date(r.finished) < 60000) return `<div class="failed">The agent couldn't finish: ${esc(r.message)}. Try again.</div>`;
  return "";
}
const modeTag = (mode, runId) => mode === "creao" ? `<span class="runtag">CREAO${runId ? " · run " + esc(String(runId).slice(0, 8)) : ""}</span>` : mode === "offline" ? `<span class="chip tape">offline stand-in</span>` : "";

// ---------------------------------------------------------------- top bar
function catchCount() {
  const since = S.last_seen[ui.me] || "";
  return S.history.filter((h) => h.at > since && h.author !== ui.me && h.on_behalf_of !== ui.me).length;
}
function renderTop() {
  const modes = Object.values(S.modes);
  const m = modes.every((x) => x === "creao") ? ["creao", "AI: CREAO agents"] : modes.some((x) => x === "creao") ? ["creao", `AI: ${modes.filter((x) => x === "creao").length}/3 CREAO agents`] : modes.every((x) => x === "offline") ? ["offline", "AI: offline stand-ins"] : ["missing", "AI: not connected"];
  const n = catchCount();
  $("#top").innerHTML = `
    <div class="brand">Strata</div>
    <div class="file">${esc(S.file.name)}<span class="mono">v.${S.file.version} · client work</span></div>
    <div class="spacer"></div>
    <span class="mode ${m[0]}" title="Ranking, edits and catch-ups come from CREAO agents">${m[1]}</span>
    <button class="linkish" data-act="catch">≡ Catch me up ${n ? `<span class="count">${n} new</span>` : ""}</button>
    <div class="avatars">${Object.values(S.members).map((p) => `<button class="av ${p.name === ui.me ? "me" : ""}" title="Viewing as ${p.name} (${p.role})" style="background:${p.fill};color:${p.ink}" data-me="${p.name}">${initials(p.name)}</button>`).join("")}<span class="av ai" title="Strata, the AI teammate">S</span></div>
    <button class="btn quiet" data-act="export">Export for client</button>
    <button class="btn ${ui.tab === "shop" ? "dark" : ""}" data-act="shop">Asset shop</button>`;
}

// ---------------------------------------------------------------- layers
const ICON = { nav: "▭", heading: "T", text: "¶", button: "▭", illustration_slot: "◫", icon_row: "▭" };
function renderRail() {
  $("#rail").innerHTML = `<div class="label">Layers</div>
    <div class="layer frame"><span class="ico">#</span>Desktop — Landing</div>
    ${els().map((e) => `<div class="layer child ${e.key === ui.sel ? "sel" : ""}" data-sel="${e.key}"><span class="ico">${ICON[e.kind]}</span>${esc(e.name)}<span class="mark ${e.authorship === "ai" ? "ai" : ""}"></span></div>`).join("")}
    <div class="layer frame"><span class="ico">#</span>Mobile — Landing</div>
    <div class="legend"><div><span class="ai"></span>Drafted by Strata, in pencil</div><div><span></span>Inked by a person</div></div>`;
}

// ---------------------------------------------------------------- canvas (the client's page has its own brand)
function elAttrs(e) { return `class="el ${e.authorship} ${e.key === ui.sel ? "sel" : ""}" data-sel="${e.key}"`; }
function renderCanvas() {
  const E = S.elements, h = E.hero_heading.props, sub = E.hero_subcopy.props, b = E.cta_button.props;
  const slot = E.hero_illustration, placed = slot.props.asset_id, tryAsset = ui.tryOn && assetOf(ui.tryOn);
  let slotHtml;
  if (tryAsset) slotHtml = `<div class="slot try"><span class="tag" style="color:var(--ink)">trying on · ${esc(tryAsset.title)}</span><img src="/assets/${tryAsset.id}.png" alt=""><div class="watermark">PREVIEW · STRATA · PREVIEW</div></div>`;
  else if (placed) slotHtml = `<div class="slot placed"><img src="/assets/${placed}.png" alt="${esc(assetOf(placed)?.title)}"></div>`;
  else slotHtml = `<div class="slot draft"><span class="tag">pencil draft</span><svg width="140" height="90" viewBox="0 0 140 90" fill="none" stroke="#6A90B8" stroke-width="1.5" stroke-dasharray="4 4"><circle cx="100" cy="22" r="12"/><path d="M6 72c18-10 28-22 44-12s26 8 40-6 26-16 44-20"/><path d="M6 84h128" stroke-dasharray="0"/></svg></div>`;
  const icons = E.feature_row.props.asset_id;
  const locked = E.hero_heading.locked_by;
  $("#canvas").innerHTML = `
    <div class="frame-label">Desktop — Landing · 1280 <label><input type="checkbox" data-act="auth" ${ui.showAuth ? "checked" : ""}> Show who made what</label></div>
    <div class="sample ${ui.showAuth ? "auth" : ""}">
      <div ${elAttrs(E.nav)}><div class="s-nav"><div class="s-logo">${esc(E.nav.props.text)}</div><div class="s-links">${E.nav.props.links.map((l) => `<span>${esc(l)}</span>`).join("")}</div></div></div>
      <div class="s-hero">
        <div>
          <h1 ${elAttrs(E.hero_heading)} style="color:${esc(h.color)};font-size:${+h.font_size}px;font-weight:${+h.font_weight}"><span class="s-h1" style="display:block;margin:0">${esc(h.text)}</span></h1>
          <p ${elAttrs(E.hero_subcopy)}><span class="s-sub" style="display:block;margin:0;color:${esc(sub.color)};font-size:${+sub.font_size}px">${esc(sub.text)}</span></p>
          <div ${elAttrs(E.cta_button)} style="display:inline-block"><span class="s-btn" style="background:${esc(b.bg)};color:${esc(b.color)}">${esc(b.text)}</span></div>
        </div>
        <div ${elAttrs(slot)}>${slotHtml}</div>
      </div>
      <div ${elAttrs(E.feature_row)}><div class="s-features">${E.feature_row.props.items.map(([t, d]) => `<div class="s-feat">${icons ? `<img src="/assets/${icons}.png" alt="">` : ""}<b>${esc(t)}</b><span>${esc(d)}</span></div>`).join("")}</div></div>
    </div>
    ${locked ? `<div class="note">keep the navy. it's the brand, not a mood. — ${esc(locked[0])}.</div>` : ""}`;
  document.querySelectorAll("#canvas h1.el, #canvas p.el").forEach((n) => { n.style.margin = n.tagName === "H1" ? "0 0 18px" : "0 0 22px"; });
}

// ---------------------------------------------------------------- panel
function renderTabs() {
  $("#tabs").innerHTML = [["history", "History"], ["shop", "Shop"], ["rules", "Team rules"], ["licences", "Licences"]]
    .map(([k, l]) => `<button class="${ui.tab === k ? "on" : ""}" data-tab="${k}">${l}</button>`).join("");
}
function who(h) { return h.actor === "ai" ? `Strata, for ${h.on_behalf_of || "the team"}` : h.author; }
function conflictCard(c) {
  const lockedByMe = ui.me === c.locked_by || ui.me === "Priya";
  const val = c.locked_value && /^#/.test(c.locked_value) ? `<span class="swatch" style="background:${esc(c.locked_value)}"></span> ${esc(c.locked_value)}` : esc(c.locked_value);
  return `<div class="card-tape"><div><b>Strata stopped before changing the ${esc(c.prop)}.</b></div>
    <div style="margin-top:6px">${esc(c.member)} asked for <b>${esc(c.wants)}</b>. ${esc(c.locked_by)} locked it at ${val}.</div>
    ${c.reason ? `<div class="why" style="color:var(--tape-text);border-color:var(--tape-text)">${esc(c.reason)}</div>` : ""}
    <div class="row">${lockedByMe ? `<button class="btn" data-conf="${c.id}" data-choice="keep">Keep ${esc(c.locked_by)}'s</button><button class="btn quiet" data-conf="${c.id}" data-choice="use">Use ${esc(c.member)}'s</button>` : ""}
    ${c.status === "open" && ui.me === c.member ? `<button class="btn quiet" data-conf="${c.id}" data-choice="ask">Ask ${esc(c.locked_by)}</button>` : ""}
    ${c.status === "asked" ? `<span class="meta">Waiting for ${esc(c.locked_by)}</span>` : ""}</div></div>`;
}
function renderHistory() {
  const e = S.elements[ui.sel];
  const hs = S.history.filter((h) => h.element_key === e.key).sort((a, b) => (a.at < b.at ? 1 : -1));
  const people = new Set(hs.filter((h) => h.actor === "human").map((h) => h.author));
  const conflicts = S.conflicts.filter((c) => c.element_key === e.key && (c.status === "open" || c.status === "asked"));
  const lock = e.locked_props.length ? `<div class="lockline"><svg width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.3"><rect x="2" y="5.5" width="8" height="5.5" rx="1"/><path d="M4 5.5V4a2 2 0 0 1 4 0v1.5"/></svg>${e.locked_props.map(esc).join(", ")} locked by ${esc(e.locked_by)}${e.props.color ? ` · <span class="swatch" style="background:${esc(e.props.color)}"></span>` : ""}</div>` : "";
  return `<div class="label">Provenance</div><h2>${esc(e.name)}</h2>
    <p class="sub">${hs.length} changes by ${people.size} ${people.size === 1 ? "person" : "people"} · ${hs.filter((h) => h.actor === "ai").length} drafted by Strata</p>
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
      <span class="budget">up to $<input data-budget value="${ui.budget}" inputmode="numeric"></span>
      <button class="btn ai" data-act="curate" ${busy(r) ? "disabled" : ""}>${sl ? "Re-rank with Strata" : "Ask Strata for a shortlist"}</button></div>
    ${runLine(r, "ranking the catalog against your team's taste")}`;
  if (sl) {
    html += `<div class="ainote"><span class="s">S</span><div>${esc(sl.summary)}<div style="margin-top:4px">${modeTag(sl.mode, sl.run_id)}</div></div></div>
      <div class="items">${sl.items.map((i) => {
        const a = assetOf(i.asset_id); if (!a) return "";
        const bad = i.breaks && i.breaks.length;
        return `<div class="item ${ui.tryOn === a.id ? "on" : ""}" data-try="${a.id}"><img src="/assets/${a.id}.png" alt="">
          <div><div class="t">${esc(a.title)}</div><div class="c">${esc(a.creator)} · ${esc(a.style)}, ${a.colours} colour${a.colours > 1 ? "s" : ""}</div>
          <div class="w ${bad ? "bad" : ""}">${esc(i.why)}</div></div><div class="p">${money(a.prices[ui.licence])}</div></div>`;
      }).join("")}</div>`;
  } else if (!busy(r)) {
    html += `<div class="card-ok" style="background:var(--sunken);color:var(--graphite)">No shortlist yet. Strata's Curator agent reads your team's rules, ${esc(ui.me)}'s spending limit and the catalog, then explains each pick.</div>`;
  }
  if (chosen) {
    const over = price > left || !md.allowed_licences.includes(ui.licence);
    const pct = (x) => `${Math.min(100, (x / md.limit_cents) * 100)}%`;
    html += `<div class="buybar"><div class="row"><span>${esc(ui.licence[0].toUpperCase() + ui.licence.slice(1))} licence · ${esc(chosen.title)}</span><span class="mono" style="font-size:16px">${money(price)}</span></div>
      <div class="bar"><i class="spent" style="width:${pct(md.spent_cents)}"></i><i class="${over ? "over" : "this"}" style="width:${pct(Math.min(price, left))}"></i></div>
      <div class="meta">${over ? `Over ${esc(ui.me)}'s ${money(md.limit_cents)} limit · ${esc(md.set_by)} can approve` : `Within ${esc(ui.me)}'s ${money(md.limit_cents)} monthly limit · ${money(left - price)} left after this`}</div>
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
  const name = (k) => S.elements[k]?.name || k;
  return `<div class="label">Licences</div><h2>What this file may ship</h2><p class="sub">Every licence is tied to the elements that use it.</p>
    ${S.licences.map((l) => {
      const a = assetOf(l.asset_id);
      return `<div class="lic"><img src="/assets/${l.asset_id}.png" alt=""><div><b>${esc(a?.title)}</b> · ${esc(l.tier)}<div class="meta">${l.element_keys.map(name).map(esc).join(", ")} · bought by ${esc(l.member)} · <span class="mono">${esc(l.licence_id)}</span></div>
        ${l.status === "upgraded" ? `<span class="chip">upgraded</span>` : l.tier === "personal" && S.file.client_work ? `<span class="chip tape">not for client work</span>` : `<span class="chip ok">ok for client work</span>`}</div><div class="mono">${money(l.amount_cents)}</div></div>`;
    }).join("")}
    <button class="btn" style="margin-top:16px" data-act="export">Check export for client</button>`;
}

function renderPanel() {
  renderTabs();
  const body = { history: renderHistory, shop: renderShop, rules: renderRules, licences: renderLicences }[ui.tab]();
  const b = $("#panel-body"), keepScroll = b.scrollTop, focused = document.activeElement?.hasAttribute?.("data-budget");
  b.innerHTML = body;
  b.scrollTop = keepScroll;
  if (focused) { const i = b.querySelector("[data-budget]"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
  const e = S.elements[ui.sel];
  $("#ask").style.display = ui.tab === "history" ? "" : "none";
  $("#ask-input").placeholder = `Ask Strata about this ${e.name.toLowerCase()}…`;
  const rules = S.rules.filter((r) => r.scope === "team" || (r.scope === "personal" && r.members.includes(ui.me)));
  $("#ask-rule").textContent = rules.length ? `Rules in play: ${rules.map((r) => r.text.toLowerCase()).join(" · ")}` : "";
  $("#ask-status").innerHTML = runLine(mine("teammate", (r) => r.element_key === ui.sel), "thinking about this " + e.name.toLowerCase());
}

// ---------------------------------------------------------------- overlays
function renderOverlay() {
  const o = $("#overlay");
  document.querySelector(".pop")?.remove();
  if (ui.catchOpen) {
    const c = S.catchups[ui.me], r = mine("catchup");
    const pop = document.createElement("div");
    pop.className = "pop"; pop.style.right = "330px";
    pop.innerHTML = `<div class="label">Since you were here, ${esc(ui.me)}</div>
      ${c ? `<ul>${c.lines.map((l) => `<li>${esc(l)}</li>`).join("")}</ul>${c.question ? `<div class="ainote"><span class="s">?</span><div>${esc(c.question)}</div></div>` : ""}<div style="margin:8px 0">${modeTag(c.mode, c.run_id)}</div>` : `<p class="sub" style="margin-top:8px">${catchCount()} changes by others since you last looked.</p>`}
      ${runLine(r, "reading what changed")}
      <div style="display:flex;gap:8px;margin-top:10px"><button class="btn ai" data-act="catchup" ${busy(r) ? "disabled" : ""}>${c ? "Refresh" : "Catch me up"}</button><button class="btn quiet" data-act="seen">Mark as seen</button></div>`;
    document.body.appendChild(pop);
  }
  if (!ui.overlay) { o.className = ""; o.innerHTML = ""; return; }
  o.className = "on";
  if (ui.overlay === "review") {
    const c = S.carts[ui.cart] || {};
    const a = assetOf(c.asset_id) || {};
    const lead = S.mandates[c.member]?.set_by;
    const payLabel = S.payments === "stripe-test" ? "Pay with Stripe (test · Visa 4242)" : "Pay (simulated test payment)";
    o.innerHTML = `<div class="sheet"><div class="label">${c.status === "paid" ? "Receipt" : "Review"}</div><h3>${esc(a.title)} · ${esc(c.licence)} licence</h3>
      <div style="display:flex;gap:14px;align-items:center"><img src="/assets/${esc(a.id)}.png" style="width:72px;height:72px;object-fit:contain;background:var(--sunken);border-radius:4px" alt="">
      <div><div>${esc(S.licence_labels[c.licence])}</div><div class="meta">${esc(a.creator)} · for ${esc(S.elements[c.element_key]?.name)}</div><div class="mono" style="font-size:18px;margin-top:4px">${money(c.amount_cents || 0)}</div></div></div>
      <ul class="trail">${(c.trail || []).map((t) => `<li class="${t.ok === false ? "warn" : ""}"><b>${esc(t.step)}</b>${esc(t.text)}</li>`).join("")}</ul>
      <div class="meta">Nothing is charged without this review, and never above a limit without ${esc(lead)}'s OK.</div>
      <div class="actions">
        ${c.status === "paid" ? `<button class="btn dark" data-act="close">Done</button>` : `<button class="btn quiet" data-act="close">Cancel</button>`}
        ${c.status === "needs_approval" ? (ui.me === lead ? `<button class="btn dark" data-act="approve">Approve as ${esc(lead)}</button>` : `<button class="btn" disabled>Waiting for ${esc(lead)}'s OK</button>`) : ""}
        ${c.status === "ready" ? `<button class="btn dark" data-act="pay">${payLabel}</button>` : ""}</div></div>`;
  }
  if (ui.overlay === "export") {
    const x = ui.exportCheck;
    o.innerHTML = `<div class="sheet"><div class="label">Export for client</div><h3>${x ? (x.ok ? "Ready to export" : "Not yet: licence check") : "Checking licences…"}</h3>
      ${x && x.ok ? `<div class="card-ok">Every asset in this file is licensed for client work.</div>` : ""}
      ${x ? x.issues.map((i) => `<div class="card-tape"><b>${esc(i.element)}</b> uses ${esc(i.asset)}: ${esc(i.problem)}.
        ${i.licence_id ? `<div class="row"><button class="btn" data-upgrade="${esc(i.licence_id)}" data-asset="${esc(i.asset_id)}" data-el="${esc(i.element_key)}">Upgrade to commercial · ${money(i.upgrade_cents)}</button></div>` : ""}</div>`).join("") : ""}
      <div class="actions"><button class="btn quiet" data-act="close">Close</button>${x && x.ok ? `<button class="btn dark" data-act="close">Export</button>` : ""}</div></div>`;
  }
}

function render() {
  if (!S) return;
  if (!S.elements[ui.sel]) ui.sel = "hero_heading";
  renderTop(); renderRail(); renderCanvas(); renderPanel(); renderOverlay();
}

// ---------------------------------------------------------------- actions
async function refresh(force) {
  const s = await api("/api/state");
  const j = JSON.stringify(s);
  const live = s.runs.some(busy);
  if (force || j !== lastJson || live) { lastJson = j; S = s; render(); }
}
async function act(fn) { try { await fn(); await refresh(true); } catch (e) { toast(e.message); } }

document.addEventListener("click", (ev) => {
  const t = ev.target.closest("[data-sel],[data-tab],[data-me],[data-act],[data-try],[data-lic],[data-judge],[data-conf],[data-upgrade]");
  if (!t) return;
  const d = t.dataset;
  if (d.sel) { ui.sel = d.sel; if (ui.tab === "shop" && !["hero_illustration", "feature_row"].includes(d.sel)) ui.tab = "history"; ui.tryOn = ui.tab === "shop" ? ui.tryOn : null; return render(); }
  if (d.tab) { ui.tab = d.tab; if (d.tab !== "shop") ui.tryOn = null; else if (!["hero_illustration", "feature_row"].includes(ui.sel)) ui.sel = "hero_illustration"; return render(); }
  if (d.me) { ui.me = d.me; store.set("strata-me", d.me); ui.tryOn = null; return render(); }
  if (d.try) { ui.tryOn = d.try; return render(); }
  if (d.lic) { ui.licence = d.lic; return render(); }
  if (d.judge) return act(() => api(`/api/history/${d.judge}/${d.v}`, { member: ui.me }));
  if (d.conf) return act(() => api(`/api/conflicts/${d.conf}`, { member: ui.me, choice: d.choice }));
  if (d.upgrade) return act(async () => { const c = await api("/api/cart", { member: ui.me, asset_id: d.asset, licence: "commercial", element_key: d.el, upgrade_of: d.upgrade }); ui.cart = c.id; ui.overlay = "review"; });
  switch (d.act) {
    case "shop": ui.tab = "shop"; ui.sel = "hero_illustration"; return render();
    case "auth": ui.showAuth = t.checked; return render();
    case "catch": ui.catchOpen = !ui.catchOpen; return render();
    case "seen": ui.catchOpen = false; return act(() => api("/api/seen", { member: ui.me }));
    case "catchup": return act(() => api("/api/agents/catchup", { member: ui.me }));
    case "curate": return act(() => api("/api/agents/curate", { member: ui.me, spot_key: spotKey(), licence: ui.licence, budget_cents: Math.round((+ui.budget || 0) * 100) }));
    case "review": return act(async () => { const c = await api("/api/cart", { member: ui.me, asset_id: ui.tryOn, licence: ui.licence, element_key: spotKey() }); ui.cart = c.id; ui.overlay = "review"; });
    case "approve": return act(() => api(`/api/cart/${ui.cart}/approve`, { member: ui.me }));
    case "pay": return act(async () => { const r = await api(`/api/cart/${ui.cart}/pay`, {}); if (r.url) location.href = r.url; else ui.tryOn = null; });
    case "export": ui.overlay = "export"; ui.exportCheck = null; render(); return act(async () => { ui.exportCheck = await api("/api/export-check"); });
    case "close": ui.overlay = null; ui.exportCheck = null; return render();
  }
});
document.addEventListener("input", (ev) => { if (ev.target.hasAttribute("data-budget")) ui.budget = ev.target.value.replace(/[^0-9.]/g, ""); });
$("#ask-form").addEventListener("submit", (ev) => {
  ev.preventDefault();
  const q = $("#ask-input").value.trim();
  if (!q) return;
  $("#ask-input").value = "";
  act(() => api("/api/agents/teammate", { member: ui.me, element_key: ui.sel, request: q }));
});
document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") { ui.overlay = null; ui.catchOpen = false; render(); } });

(async () => {
  const p = new URLSearchParams(location.search);
  await refresh(true);
  if (p.get("paid")) { ui.cart = p.get("paid"); ui.overlay = "review"; ui.tab = "licences"; history.replaceState(null, "", "/"); render(); }
  setInterval(() => refresh(false).catch(() => {}), 1500);
})();
