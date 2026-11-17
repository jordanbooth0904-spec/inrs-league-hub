/* INRS League Hub sign-in helper (Cloudflare Worker).
   /login     -> sends the visitor to Discord's sign-in page (only asks for their name and avatar)
   /callback  -> Discord sends them back here; we look up who they are and send them back to the site with a
                 one-time Firebase sign-in token. The site swaps it for a normal Firebase login.
   Secrets (Worker > Settings > Variables, type "Secret"):
     DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET   from the Discord Developer Portal app
     FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY from a Firebase service account JSON key
     SITE_URL   e.g. https://inrs.page/
     APPS_WEBHOOK (secret, optional)  a Discord webhook in a FORUM channel. Each league application gets its own
                 post (thread) there; later edits and admin status changes are added to that thread.
   /app-notify -> the site calls this after someone applies or an admin saves a review. The worker reads the
                 application from the database itself (so nothing posted can be faked by the caller) and only posts
                 when something actually changed since the last post.                                         */
const DB = "https://inrs-league-hub-default-rtdb.firebaseio.com";
export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    const site = String(env.SITE_URL || "").replace(/#.*$/, "");
    const back = (frag) => Response.redirect(site + "#" + frag, 302);
    const origin = new URL(site || "https://inrs.page/").origin;
    const cors = { "Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "POST, OPTIONS", "Access-Control-Allow-Headers": "Content-Type" };
    if (u.pathname === "/app-notify") {
      if (req.method === "OPTIONS") return new Response(null, { status: 204, headers: cors });
      try {
        const out = await appNotify(env, await req.json());
        return new Response(JSON.stringify(out), { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
      } catch (e) {
        return new Response(JSON.stringify({ ok: false, error: String(e.message || e).slice(0, 200) }), { status: 200, headers: { ...cors, "Content-Type": "application/json" } });
      }
    }
    try {
      if (u.pathname === "/login") {
        const state = u.searchParams.get("state") || "";
        if (!/^[a-z0-9]{8,64}$/i.test(state)) return new Response("Bad request", { status: 400 });
        const q = new URLSearchParams({ client_id: env.DISCORD_CLIENT_ID, redirect_uri: u.origin + "/callback",
          response_type: "code", scope: "identify", state, prompt: "none" });
        return Response.redirect("https://discord.com/oauth2/authorize?" + q, 302);
      }
      if (u.pathname === "/callback") {
        const code = u.searchParams.get("code"), state = u.searchParams.get("state") || "";
        if (!code || !/^[a-z0-9]{8,64}$/i.test(state)) return back("signin-error");
        const tr = await fetch("https://discord.com/api/oauth2/token", {
          method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
          body: new URLSearchParams({ client_id: env.DISCORD_CLIENT_ID, client_secret: env.DISCORD_CLIENT_SECRET,
            grant_type: "authorization_code", code, redirect_uri: u.origin + "/callback" }) });
        if (!tr.ok) return back("signin-error");
        const tok = await tr.json();
        const ur = await fetch("https://discord.com/api/users/@me", { headers: { Authorization: "Bearer " + tok.access_token } });
        if (!ur.ok) return back("signin-error");
        const me = await ur.json();
        const name = String(me.global_name || me.username || "Driver").slice(0, 40);
        const avatar = me.avatar ? "https://cdn.discordapp.com/avatars/" + me.id + "/" + me.avatar + ".png?size=64" : "";
        const ct = await customToken(env, "discord:" + me.id, { dname: name, davatar: avatar });
        return back("signin=" + encodeURIComponent(ct) + "&state=" + encodeURIComponent(state));
      }
      return new Response("INRS sign-in helper", { status: 200 });
    } catch (e) {
      return back("signin-error");
    }
  },
};

const b64u = (buf) => btoa(String.fromCharCode(...new Uint8Array(buf))).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
const b64uStr = (s) => b64u(new TextEncoder().encode(s));

/* Firebase custom token: a JWT signed with the service account key (RS256). Valid for 1 hour, used once. */
async function customToken(env, uid, claims) {
  const pem = String(env.FIREBASE_PRIVATE_KEY).replace(/\\n/g, "\n").replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const now = Math.floor(Date.now() / 1000);
  const body = { iss: env.FIREBASE_CLIENT_EMAIL, sub: env.FIREBASE_CLIENT_EMAIL,
    aud: "https://identitytoolkit.googleapis.com/google.identity.identitytoolkit.v1.IdentityToolkit",
    iat: now, exp: now + 3600, uid, claims };
  const head = b64uStr(JSON.stringify({ alg: "RS256", typ: "JWT" })) + "." + b64uStr(JSON.stringify(body));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(head));
  return head + "." + b64u(sig);
}

/* ---------- league applications -> Discord forum threads ---------- */
async function googleToken(env) {
  const pem = String(env.FIREBASE_PRIVATE_KEY).replace(/\\n/g, "\n").replace(/-----[^-]+-----/g, "").replace(/\s+/g, "");
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey("pkcs8", der, { name: "RSASSA-PKCS1-v1_5", hash: "SHA-256" }, false, ["sign"]);
  const now = Math.floor(Date.now() / 1000);
  const body = { iss: env.FIREBASE_CLIENT_EMAIL, scope: "https://www.googleapis.com/auth/firebase.database https://www.googleapis.com/auth/userinfo.email",
    aud: "https://oauth2.googleapis.com/token", iat: now, exp: now + 3600 };
  const head = b64uStr(JSON.stringify({ alg: "RS256", typ: "JWT" })) + "." + b64uStr(JSON.stringify(body));
  const sig = await crypto.subtle.sign("RSASSA-PKCS1-v1_5", key, new TextEncoder().encode(head));
  const r = await fetch("https://oauth2.googleapis.com/token", { method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ grant_type: "urn:ietf:params:oauth:grant-type:jwt-bearer", assertion: head + "." + b64u(sig) }) });
  if (!r.ok) throw new Error("google token " + r.status);
  return (await r.json()).access_token;
}
async function dbGet(tok, path) { const r = await fetch(DB + "/" + path + ".json?access_token=" + tok); if (!r.ok) throw new Error("db read " + r.status); return r.json(); }
async function dbPut(tok, path, v) { const r = await fetch(DB + "/" + path + ".json?access_token=" + tok, { method: "PUT", body: JSON.stringify(v) }); if (!r.ok) throw new Error("db write " + r.status); }
const STATUS = { "": "New", reviewing: "Under review", accepted: "Accepted", waitlist: "Waitlisted", declined: "Not accepted" };
const COLOR = { "": 0xf5c542, reviewing: 0x4aa3ff, accepted: 0x3ecf8e, waitlist: 0x8a8f98, declined: 0xff6b6b };
const clip = (s, n) => { s = String(s == null ? "" : s); return s.length > n ? s.slice(0, n - 1) + "…" : s; };
async function hook(env, q, payload) {
  for (let t = 0; t < 3; t++) {
    const r = await fetch(env.APPS_WEBHOOK + (env.APPS_WEBHOOK.includes("?") ? "&" : "?") + "wait=true" + q, { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(Object.assign({ username: "INRS Applications", allowed_mentions: { parse: [] } }, payload)) });
    if (r.status === 429) { const j = await r.json().catch(() => ({})); await new Promise((res) => setTimeout(res, Math.min(5000, 1000 * (j.retry_after || 1)))); continue; }
    if (!r.ok) throw new Error("discord " + r.status + " " + clip(await r.text(), 120));
    return r.json();
  }
  throw new Error("discord rate limited");
}
function answerEmbeds(form, app, title, color) {
  const qs = Array.isArray(form && form.questions) ? form.questions : [];
  const a = app.answers || {}, seen = new Set(), parts = [];
  const add = (label, v) => { if (v === undefined || v === null || v === "") return; parts.push("**" + clip(label, 200) + "**\n" + clip(v === true ? "Yes" : v, 1500)); };
  qs.forEach((q) => { seen.add(q.id); add(q.label, a[q.id]); });
  Object.keys(a).forEach((k) => { if (!seen.has(k)) add(k, a[k]); });
  const embeds = []; let cur = "";
  parts.forEach((p) => { if ((cur + "\n\n" + p).length > 3900) { embeds.push(cur); cur = p; } else cur = cur ? cur + "\n\n" + p : p; });
  if (cur) embeds.push(cur);
  return embeds.slice(0, 4).map((d, i) => ({ title: i ? undefined : title, description: d, color }));
}
async function appNotify(env, b) {
  if (!env.APPS_WEBHOOK) return { ok: false, error: "APPS_WEBHOOK not set" };
  const form = String((b && b.form) || ""), uid = String((b && b.uid) || "");
  if (!/^[\w-]{1,20}$/.test(form) || !/^discord:\d{5,30}$/.test(uid)) return { ok: false, error: "bad request" };
  const tok = await googleToken(env);
  const [app, rev, pub, posted, f] = await Promise.all([dbGet(tok, "applications/" + form + "/" + uid), dbGet(tok, "appReviews/" + form + "/" + uid),
    dbGet(tok, "appStatus/" + form + "/" + uid), dbGet(tok, "appDiscord/" + form + "/" + uid), dbGet(tok, "site/appForm")]);
  if (!app || !app.answers) return { ok: true, skipped: "no application" };
  const a = app.answers, did = uid.slice(8), status = (rev && rev.status) || "", rec = posted || {};
  const who = clip(a.name || app.name || "Applicant", 60);
  const head = "Discord: <@" + did + "> (" + clip(app.name, 60) + ") · submitted <t:" + Math.floor((app.at || Date.now()) / 1000) + ":f>";
  let did1 = false;
  if (!rec.thread) {
    const tn = clip([who, a.series, a.tier && String(a.tier).replace(/\s*\(.*\)/, "")].filter(Boolean).join(" · "), 95);
    const m = await hook(env, "", { thread_name: tn, content: head, embeds: answerEmbeds(f, app, "Application: " + who, COLOR[""]) });
    rec.thread = m.channel_id; rec.updated = app.updated || app.at || 0; rec.status = ""; did1 = true;
  } else if ((app.updated || 0) > (rec.updated || 0)) {
    await hook(env, "&thread_id=" + rec.thread, { content: "✏️ **Answers updated** <t:" + Math.floor(app.updated / 1000) + ":R>", embeds: answerEmbeds(f, app, "Updated application: " + who, COLOR[""]) });
    rec.updated = app.updated; did1 = true;
  }
  const sig = status + "|" + ((pub && pub.msg) || "") + "|" + ((rev && rev.note) || "");
  if (rev && sig !== (rec.statusSig || "|" + "|")) {
    const lines = ["**Status: " + (STATUS[status] || status || "New") + "**"];
    if (pub && pub.msg) lines.push("Message to applicant: " + clip(pub.msg, 600));
    if (rev.note) lines.push("Admin note: " + clip(rev.note, 600));
    if (rev.by) lines.push("By <@" + String(rev.by).replace(/^discord:/, "") + ">");
    await hook(env, "&thread_id=" + rec.thread, { embeds: [{ description: lines.join("\n"), color: COLOR[status] || COLOR[""] }] });
    rec.statusSig = sig; rec.status = status; did1 = true;
  }
  if (did1) { rec.at = Date.now(); await dbPut(tok, "appDiscord/" + form + "/" + uid, rec); }
  return { ok: true, posted: did1, thread: rec.thread };
}
