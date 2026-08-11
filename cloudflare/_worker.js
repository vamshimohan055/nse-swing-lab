// Cloudflare Pages worker: serves the NSE Swing Lab Streamlit app over HTTPS
// and forwards all requests to the upstream origin.
//
// Deploy: `wrangler pages deploy .` from the project root after setting
// UPSTREAM_URL to your Streamlit host (e.g. a Cloudflare Tunnel or
// `streamlit run` exposed via `cloudflared`).

export default {
  async fetch(request, env) {
    const upstream = env.UPSTREAM_URL || "http://localhost:8501";
    const url = new URL(request.url);
    const target = upstream.replace(/\/$/, "") + url.pathname + url.search;

    const reqHeaders = new Headers(request.headers);
    reqHeaders.set("Host", new URL(upstream).host);
    reqHeaders.set("X-Forwarded-Host", url.hostname);
    reqHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));

    const resp = await fetch(target, {
      method: request.method,
      headers: reqHeaders,
      body: request.body,
      redirect: "follow",
    });

    const outHeaders = new Headers(resp.headers);
    outHeaders.set("X-Frame-Options", "SAMEORIGIN");
    outHeaders.set("Referrer-Policy", "strict-origin-when-cross-origin");
    outHeaders.set("X-Content-Type-Options", "nosniff");
    return new Response(resp.body, { status: resp.status, headers: outHeaders });
  },
};
