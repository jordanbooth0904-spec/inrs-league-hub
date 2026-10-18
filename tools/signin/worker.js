/* INRS League Hub sign-in helper (Cloudflare Worker).
   /login     -> sends the visitor to Discord's sign-in page (only asks for their name and avatar)
   /callback  -> Discord sends them back here; we look up who they are and send them back to the site with a
                 one-time Firebase sign-in token. The site swaps it for a normal Firebase login.
   Secrets (Worker > Settings > Variables, type "Secret"):
     DISCORD_CLIENT_ID, DISCORD_CLIENT_SECRET   from the Discord Developer Portal app
     FIREBASE_CLIENT_EMAIL, FIREBASE_PRIVATE_KEY from a Firebase service account JSON key
     SITE_URL   e.g. https://jordanbooth0904-spec.github.io/inrs-league-hub/                                  */
export default {
  async fetch(req, env) {
    const u = new URL(req.url);
    const site = String(env.SITE_URL || "").replace(/#.*$/, "");
    const back = (frag) => Response.redirect(site + "#" + frag, 302);
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
