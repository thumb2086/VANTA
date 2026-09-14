# VANTA WebGL Build

Exported Godot 4.4 WebGL build for browser deployment.

## Quick Deploy (Cloudflare Workers)

```bash
# From project root
cd client
# Export (if not already done)
godot --headless --export-release "Web" ../webgl_build/index.html
# Deploy
cd ..
npx wrangler deploy
```

## Files

- `index.html` — Main entry point
- `index.js` — Godot WASM loader
- `index.wasm` — Engine binary
- `index.pck` — Game pack (assets, scripts, scenes)
- `index.png` — Splash/logo
- `webgl_build.data` — Memory file (if present)

## Local Testing

```bash
# Serve the build locally
npx serve webgl_build
# Or with Python
cd webgl_build && python -m http.server 8080
```

Open `http://localhost:8080` in browser.

## Requirements

- Godot 4.4+ with Web export template installed
- Browser with WebAssembly support (Chrome 91+, Firefox 89+, Safari 15+)
- Cloudflare account (for Workers deployment)

## Notes

- WebGL build does not support threads by default (singleplayer/relay only)
- WASM binary caching: first load downloads ~25MB, subsequent loads use browser cache
- Canvas resize policy set to `Adaptive` — respects container size
