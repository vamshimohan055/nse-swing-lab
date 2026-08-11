# Cloudflare deployment

Two pieces, both in `cloudflare/`:

1. **`_worker.js`** — Cloudflare Pages Functions script. Proxies every
   request to the upstream Streamlit server and injects standard security
   headers. Drop this in the root of your Pages project.

2. **`wrangler.toml`** — Wrangler config (Pages, project name `nse-swing-lab`).
   Override `UPSTREAM_URL` as a Pages env var or in the dashboard once the
   upstream is reachable.

## Deployment options

### Option A — Cloudflare Pages + Cloudflare Tunnel (recommended, free)

```bash
# 1. Run the Streamlit app on a server reachable via a Tunnel
streamlit run src/nse_swing_lab/app.py --server.port 8501 --server.address 0.0.0.0

# 2. Expose it
cloudflared tunnel --url http://localhost:8501
# copy the https://*.trycloudflare.com URL it prints

# 3. Deploy the worker
cd cloudflare
wrangler pages deploy . --project-name nse-swing-lab
# In the Pages dashboard, set env var UPSTREAM_URL=<your trycloudflare URL>
```

### Option B — Streamlit Community Cloud + Worker proxy

1. Push the repo to GitHub.
2. Deploy to https://share.streamlit.io — note the public URL, e.g.
   `https://nse-swing-lab.streamlit.app`.
3. In the Cloudflare Pages project, set `UPSTREAM_URL` to that Streamlit
   URL. The worker will proxy traffic to Streamlit over its WSS-aware path.

## Sharing

After deploy, Cloudflare gives you a `https://nse-swing-lab.pages.dev`
URL. Add a custom domain in the Pages dashboard if you want your own
hostname.
