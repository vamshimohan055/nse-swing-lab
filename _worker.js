// Cloudflare Pages worker: serves the NSE Swing Lab Streamlit app over HTTPS
// and forwards all requests to the upstream origin (a Cloudflare quick tunnel).
//
// Streamlit's WebSocket connection is rejected unless the Origin header matches
// the Host header. The worker therefore rewrites the upstream Host to match the
// incoming public Origin so that the WebSocket check passes.

export default {
  async fetch(request, env) {
    const upstream = env.UPSTREAM_URL || "http://localhost:8501";
    const url = new URL(request.url);

    const target = upstream.replace(/\/$/, "") + url.pathname + url.search;

    const reqHeaders = new Headers(request.headers);
    reqHeaders.set("Host", url.hostname);
    reqHeaders.set("X-Forwarded-Host", url.hostname);
    reqHeaders.set("X-Forwarded-Proto", url.protocol.replace(":", ""));
    reqHeaders.set("Origin", url.origin);
    if (!reqHeaders.has("X-Forwarded-For")) {
      reqHeaders.set("X-Forwarded-For", request.headers.get("CF-Connecting-IP") || "127.0.0.1");
    }

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
