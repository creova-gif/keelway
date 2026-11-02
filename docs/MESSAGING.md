# Approvals over Telegram and WhatsApp

When an agent step needs a human, Keelway can send the approval request to your phone with
**Approve** and **Deny** buttons. The Studio approval card stays the source of truth: a message is
a convenience, and a failed send never blocks the agent.

- **Air-gapped means silent.** While air-gap is on, nothing is sent and button presses are refused
  (`POST /v1/messaging/test` returns 409). Answer in the Studio.
- **One button, one call.** Each message carries a one-time nonce bound to the exact pending tool
  call. A press for a call that was already answered, replaced or denied does nothing.
- **Only approvers.** Telegram presses must come from the configured chat and an approver ID;
  WhatsApp replies must be signed by Meta (`X-Hub-Signature-256`) and come from the configured number.
- Every remote decision is written to the audit chain as `remote_approval` with actor
  `telegram:<user id>` or `whatsapp:<number>`.

## Telegram (works behind NAT, no public URL)

1. Create a bot with @BotFather and copy its token.
2. Send your bot a message, then read your chat ID from
   `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. Start Keelway with:

```bash
export KEELWAY_TELEGRAM_BOT_TOKEN=...
export KEELWAY_TELEGRAM_CHAT_ID=...
# optional, for group chats: who may press the buttons (defaults to the chat ID)
export KEELWAY_TELEGRAM_APPROVER_IDS=111,222
keelway dev
```

Keelway long-polls `getUpdates`, so button presses arrive without a webhook.

## WhatsApp (Cloud API)

```bash
export KEELWAY_WHATSAPP_TOKEN=...            # Cloud API access token
export KEELWAY_WHATSAPP_PHONE_NUMBER_ID=...  # sender phone number ID
export KEELWAY_WHATSAPP_TO=2547XXXXXXXX      # your number, digits only
export KEELWAY_WHATSAPP_APP_SECRET=...       # enables buttons + signed replies
export KEELWAY_WHATSAPP_VERIFY_TOKEN=...     # for Meta's webhook handshake
```

Without `KEELWAY_WHATSAPP_APP_SECRET` Keelway sends plain notifications only. Buttons need Meta to
reach `POST /v1/messaging/whatsapp/webhook`, so expose it through a tunnel you trust.

Check what's configured with `GET /v1/messaging/status`, and send a test with `POST /v1/messaging/test`.
