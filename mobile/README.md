# Keelway Mobile

Approve agent actions and watch runs from your phone, against the Keelway running on your computer. No cloud relay: the phone talks straight to your machine over Wi-Fi, LAN or Tailscale.

## Run it

```bash
# on your computer
keelway dev --host 0.0.0.0      # prints a "Phone" link with your LAN address and token

# in this folder
npm install
npx expo start                   # scan the QR with Expo Go
```

Paste the Phone link into the app (or open `keelway://pair?link=<url-encoded link>`). The token is kept in the OS keychain (Expo SecureStore); on web it is in `localStorage`.

## What it does

- Lists agent runs (`GET /v1/agent/runs`) and Studio status (`GET /v1/studio/status`), polling every 3 s, backing off to 30 s while unreachable and pausing in the background. The last known state stays on screen while offline.
- Approve / Deny the pending tool call (`POST /v1/agent/approve/{task_id}`). Approving asks for Face ID / fingerprint (device passcode or a confirm dialog as fallback). Tokens without `approve_tier3` see the request but not the buttons.
- Air-gap badge toggles `POST /v1/studio/airgap` (owner/admin only).
- English, Kiswahili, Français, العربية (right-to-left).

## Notes

- Plain `http://` on a LAN is allowed: Android via `usesCleartextTraffic`, iOS via `NSAllowsLocalNetworking`. Use Tailscale or HTTPS off your own network.
- Expo web (`npx expo start --web`) is a browser origin, so start Keelway with `ALLOWED_ORIGINS=http://localhost:8081`.
- `npm run typecheck` runs `tsc --noEmit`.
