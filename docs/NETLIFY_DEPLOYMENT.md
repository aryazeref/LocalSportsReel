# Netlify deployment for LocalSportsReel

This repository contains **two separate applications**:

1. \`frontend/\` is a Next.js static-export website suitable for Netlify.
2. \`backend/\` is a FastAPI server that must be hosted separately (for example
   on Render). The FastAPI server also needs access to \`fan-companion/\`.

## Fixing Netlify "Site is live" but every route is 404

A normal \`.next/\` folder is **not** the same as a public static site.
If Netlify publishes \`frontend/.next\` without applying its Next.js
adapter, there may be no \`index.html\` at the published root.

We use Next.js \`output: "export"\` instead. \`npm run build\` emits:

- \`frontend/out/index.html\` — homepage
- \`frontend/out/companion/index.html\` — Companion
- \`frontend/out/liiga/index.html\` — Liiga
- \`frontend/out/predictions/index.html\` — Predictions
- \`frontend/out/pricing/index.html\` — Pricing
- \`frontend/out/404.html\` — fallback page

The \`frontend/netlify.toml\` file explicitly sets the output directory to
\`out\`. This is **relative to the site's base directory \`frontend\`**, so
Netlify may show \`frontend/out\` in its final resolved config.

### Netlify setup

- Repository: \`aryazeref/LocalSportsReel\`
- Production branch: \`feature/unified-platform\` (until merged into main)
- Base directory: \`frontend\`
- Build command: \`npm run build\`
- Publish directory: **\`out\`**, not \`.next\` (the checked-in
  \`frontend/netlify.toml\` normally overrides the UI setting).
- Build environment: \`NETLIFY_NEXT_PLUGIN_SKIP=true\` is supplied by
  \`frontend/netlify.toml\`. No Next.js server function is required.

A successful deployment log should mention:
\`Config file ... frontend/netlify.toml\`;
\`Starting to deploy site from 'frontend/out'\`;
and \`Site is live\`. Then visit the public Netlify homepage.

If Netlify still reports \`frontend/.next\`, the build isn't using the
updated config/branch. Change the UI Publish directory to \`out\`
(relative to the Base directory), run **Clear cache and deploy site**,
and verify the deployed commit matches your latest branch.

### Connect the real Python backend

Set ONLY the browser-public backend URL on Netlify:

    NEXT_PUBLIC_API_BASE_URL=https://YOUR-FASTAPI-HOST

Do **not** set \`GEMINI_API_KEY\`, \`OPENAI_API_KEY\`,
\`COMPANION_ENABLE_LLM\`, or \`LLM_PROVIDER\` on Netlify.
Those belong **only on the deployed Python server**, not the frontend.

Set the FastAPI host's environment variable to your real website origin:

    FRONTEND_ORIGINS=https://localsportreel.netlify.app

The backend handles all Liiga requests, forecasts and AI conversations.
Until it is hosted and connected, the static website will load but
the data-driven views will display connection errors.

### Local development

\`npm run dev\` still runs the Next.js development server in \`frontend/\`.
\`npm run build\` creates \`frontend/out/\` for static hosting.
A static export is not run using \`next start\`; it needs an HTTP file
server to serve \`out\` locally. To return to server-rendered Next.js
later, replace \`output: "export"\` with its server-based configuration
and enable Netlify's OpenNext adapter.
