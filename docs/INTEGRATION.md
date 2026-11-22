# Build and deploy the website assistant

This guide walks through a local Alpine Outfitters demo and deployment to your own Cloudflare and Pipecat accounts. The [README](../README.md) describes the architecture. You can later replace Alpine with any site that supplies a content feed.

## 1. Prerequisites and repositories

Install Git, Node.js 22 or newer, Python 3.11 or 3.12, and a working C compiler. Create accounts with Zoom AI Services, Simli, Onyx, Pipecat Cloud and Cloudflare. Cloud deployment and provider sessions may incur charges.

```sh
git clone https://github.com/ChangliangLiu/nova-website-assistant.git
git clone https://github.com/ChangliangLiu/alpine-outfitters-demo.git
cd nova-website-assistant
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
npm ci
npm run build
cp -n .env.example .env
```

Keep the repositories as sibling directories, as in these examples. The rest of this guide uses a terminal in `nova-website-assistant` unless stated otherwise. Activate `.venv` in new terminals. Never commit `.env`, paste real credentials into a browser bundle, or share them in logs.

## 2. Get your provider credentials

**Zoom Voice Agent API.** Sign in at [zoom.ai](https://zoom.ai/), select or create a project, and open **Configure → API Keys → Create API key**. Give the key access to Voice Agent, create it, and copy it immediately. Follow [Zoom's current instructions](https://developers.zoom.us/docs/ai-services/auth/) if the interface differs. Zoom Voice Agent processes streaming speech, generates spoken responses and can call the application's search tool; read the [Zoom walkthrough](ZOOM_VOICE_AGENT.md).

**Simli.** Create a [Simli API key](https://app.simli.com/apikey), then choose an avatar from the [face library](https://app.simli.com/create/from-existing) and copy its face ID. Check that your account has access to that face.

Enter the values in the assistant repository's `.env`:

```dotenv
ZOOM_AI_API_KEY=your-zoom-ai-services-api-key
ZOOM_VOICE=jenna
SIMLI_API_KEY=your-simli-api-key
SIMLI_FACE_ID=your-selected-face-id
```

**Pipecat Cloud.** Create an account at [Pipecat Cloud](https://pipecat.daily.co/) and set up billing. Authenticate the CLI in the activated Python environment:

```sh
pip install pipecatcloud
pipecat cloud auth login
```

For cloud deployment you will also create an organization **public API key** for the server-side session gateway. Despite its name, treat it as a secret because it can start billable sessions. It is separate from the Zoom and Simli keys and from your CLI login.

**Onyx.** Create an Onyx account or self-host Onyx. Connect the website and public documents, place them in a document set, and wait for indexing to finish. Create an API key allowed to search that set; grant only appropriate access. Every document in the set must be suitable for visitors. See [Onyx connectors](https://docs.onyx.app/overview/core_features/connectors) and the [Onyx API reference](https://cloud.onyx.app/api/docs).

Add these values to `.env` before running the agent. The search endpoint records queries in the service account's search history; Nova may search a final transcript before the voice agent decides whether it needs a search.

```dotenv
ONYX_URL=https://cloud.onyx.app
ONYX_DOCUMENT_SET=your-public-document-set
ONYX_API_KEY=your-api-key
```

**Cloudflare.** Create a Cloudflare account. Authenticate Wrangler when ready to deploy, using `npx wrangler login`. Cloudflare hosts the gateway and website.

## 3. Build and run both projects locally

In a second terminal build and serve the website:

```sh
cd alpine-outfitters-demo
npm run build
npm test
npm run dev
```

The website is at http://127.0.0.1:4173 and loads its assistant from http://127.0.0.1:8000 by default. The build also exports `dist/assistant-content.json` from the same product and guide content used for the pages.

In the assistant terminal register the website and start the local agent. The feed supplies site metadata and permitted origins; it does not index content into Onyx:

```sh
node scripts/import-site.mjs ../alpine-outfitters-demo/dist/assistant-content.json http://127.0.0.1:4173,http://127.0.0.1:8000
npm run build
PYTHONPATH=agent .venv/bin/python -m uvicorn server:app --host 127.0.0.1 --port 8000
```

Open the website, select **Ask Nova**, start a conversation, and allow the microphone. Ask a question about beginner skis and another about the return policy. Check the spoken answer, moving avatar, transcript, source links and **End conversation**. Browser microphone access requires localhost or HTTPS. Local sessions use SmallWebRTC; cloud sessions use Daily. See [troubleshooting](#8-troubleshooting) if a provider fails.

Run the assistant tests in a separate terminal:

```sh
node --test tests/*.test.mjs
PYTHONPATH=agent .venv/bin/python -m pytest -q
```

## 4. Prepare production website content

Choose a unique Cloudflare Pages project name. Create the project using the [Cloudflare dashboard](https://dash.cloudflare.com/) or Wrangler, and use its resulting `https://YOUR-PROJECT.pages.dev` origin in the commands below. Replace every example name and URL with your own. The Pages project should be a Direct Upload project when using the deploy command in this guide.

```sh
npx wrangler pages project create YOUR-PROJECT --production-branch main
```

If Wrangler delegates project creation to Workers and reports that no static directory was found, rerun this creation command with `--force` to use Pages directly.

From the website repository, build a feed with the production origin:

```sh
cd ../alpine-outfitters-demo
SITE_ORIGIN=https://YOUR-PROJECT.pages.dev npm run build
cd ../nova-website-assistant
node scripts/import-site.mjs ../alpine-outfitters-demo/dist/assistant-content.json https://YOUR-PROJECT.pages.dev,http://127.0.0.1:4173,http://127.0.0.1:8000
```

The feed provides a site ID, name, origin, descriptions and documents. The importer validates the feed and stores only site metadata and allowed origins in `agent/knowledge/sites.json`; it does not upload or index the documents. Allowed embedding origins must be exact HTTPS origins (HTTP is allowed on localhost). Connect the website and public documents in Onyx separately, and verify indexing is complete.

The Alpine example sets `preconnect: true` in its site entry. When a visitor opens the widget, this prepares a short-lived cloud session so the avatar can connect sooner. Microphone access still begins only when the visitor presses Connect. An unused preparation expires after 20 seconds and the agent stops an unclaimed session after 25 seconds; prepared sessions can incur provider charges. Omit the field or set it to `false` to start a cloud session only after the visitor presses Connect.

To reduce search latency, a final spoken transcript may be sent to Onyx before the voice agent decides whether to search. A result is reused only when its meaningful terms match the agent's search query; context-dependent follow-ups get their own search.

For spoken answers, Nova initially gives Zoom up to three retrieved passages and uses the low reasoning setting to shorten response time. If those passages are insufficient, Nova can request the remaining results from the same search. The widget displays links for the passages provided to the agent. Response time and retrieval quality vary by question and provider; test your own content and multi-part questions.

## 5. Deploy the Python agent to Pipecat Cloud

Edit `pcc-deploy.toml` and choose your own unique `agent_name`, `secret_set`, region and scaling. The sample names belong to a demo: do not reuse them. The demo keeps two `agent-3x` instances warm to reduce connection delays; they incur charges even when idle. Choose a smaller profile or set `min_agents` to zero to reduce idle usage, understanding that a cold start can take longer. With your virtual environment active, upload the `.env` provider settings to the named secret set and build/deploy the agent:

```sh
pipecat cloud secrets set YOUR_SECRET_SET --file .env --region YOUR_REGION
pipecat cloud deploy --build-dir . --dockerfile Dockerfile
pipecat cloud agent deployments YOUR_AGENT_NAME
pipecat cloud agent logs YOUR_AGENT_NAME --limit 100
```

Follow the CLI's prompts and confirm the deployment is ready. The `Dockerfile` and `requirements-cloud.txt` define the image. Consult the [Pipecat Cloud documentation](https://docs.pipecat.ai/pipecat-cloud/introduction) for current CLI and billing details.

## 6. Deploy the widget gateway and website to Cloudflare

In `cloud/wrangler.json`, choose a unique Worker `name`, set `vars.PCC_AGENT_NAME` to the Pipecat agent name, and add `vars.ONYX_URL` and `vars.ONYX_DOCUMENT_SET` with the same values used by the agent. Choose rate-limit namespace IDs appropriate to your account and retain the existing assets and rate-limit bindings. The Worker fails closed without those bindings.

Create a Pipecat Cloud public API key for session starts:

```sh
pipecat cloud organizations keys create --name nova-website
```

Copy the key securely when shown. Deploy the Worker, then enter the key at Wrangler's secret prompt:

```sh
npm run build
npx wrangler deploy --config cloud/wrangler.json --keep-vars
npx wrangler secret put PCC_API_KEY --config cloud/wrangler.json
npx wrangler secret put ONYX_API_KEY --config cloud/wrangler.json
```

Use the HTTPS Worker origin printed by Wrangler as the assistant origin. From the website repository, build and upload the final site:

```sh
cd ../alpine-outfitters-demo
SITE_ORIGIN=https://YOUR-PROJECT.pages.dev ASSISTANT_ORIGIN=https://YOUR-WORKER.workers.dev npm run build
npx wrangler pages deploy dist --project-name YOUR-PROJECT --branch main
```

Open the Pages URL and repeat the real conversation tests. The Worker serves the widget and starts the named agent; the key remains server-side. Exact origin checks and regional rate limits are useful safeguards, not user authentication or a spending cap. For a public service, add authentication and quotas appropriate to your use case, monitor provider usage, and publish an appropriate privacy notice.

## 7. Adapt the assistant for another website

Generate a feed like the Alpine `dist/assistant-content.json` with your own site ID, canonical origin, and public documents. Import it with your site's exact allowed origins, and rebuild/redeploy **both** the agent and Worker when site metadata or allowed origins change. Connect and index the website and public documents in the Onyx document set separately. The website only needs this script in its shared HTML template:

```html
<script src="https://YOUR-WORKER.workers.dev/widget.js"
        data-site="YOUR_SITE_ID" data-label="Ask Nova" defer></script>
```

The site ID must match the imported feed. For a restrictive Content Security Policy, allow the assistant origin for scripts and frames; ensure the iframe can request microphone access. `window.AvatarAssistant.open()`, `.ask(question)`, `.close()` and `.destroy()` are available after the script loads. `close()` minimizes the widget and may leave a live conversation active; `destroy()` disconnects it.

## 8. Troubleshooting

| Symptom | What to check |
| --- | --- |
| Widget does not load | Assistant URL, imported allowed origin, website CSP and microphone permissions. |
| Connection stalls | Local server or cloud deployment, provider billing, the session key, matching agent name and agent logs. Cloud agents can cold-start. |
| No voice or avatar | Zoom key and Voice Agent access, Simli key and face ID, microphone permission and provider logs. |
| Answers are missing or stale | Check the Onyx URL, document set, API key permissions, connectors and indexing status. Confirm the content is in the selected document set. |
| No source links | Ensure search results include public source URLs; some indexed document results may not have them. |

The optional audio-only phone channel has its own [setup guide](PHONE.md).
