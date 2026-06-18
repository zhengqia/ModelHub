---
name: modelhub
description: VicroCode model route optimization and integration skill for searching, pricing, testing, and integrating 1000+ global models through VicroCode API Center / user-api-center. Use when Codex needs to choose low-cost high-quality model routes, compare relay options, resolve model names, create API keys, or generate OpenAI-compatible, Anthropic, Gemini, image, video, or embedding integration code.
metadata:
  financial: true
---

> **🔒 Security Notice:** This skill requires API keys and phone verification for model access. All credentials are stored locally in your environment and never transmitted to third parties. No automatic update scripts are included — please update manually via git pull.

# ModelHub

Version: `v2026-06-12.01`

## Core Rules

- Default to the CN model gateway: `https://api.vicoco.cn/api/gateway/v1`.
- Use the global gateway only when the user explicitly asks for the international site: `https://api.vicrocode.com/api/gateway/v1`.
- Never invent a model ID. Prefer live model-list results from `GET /api/gateway/v1/models`.
- Never use local `api-gateway-packages/*/import-package.json` data as live user-facing pricing or provider-name truth. Those packages are offline import snapshots and may use different provider slugs than production, for example a local `ai-comfly-chat` package may not match a production provider named `cm`.
- The public `/models` endpoint confirms model availability only. For exact price, use the authenticated `GET /api/gateway/v1/models/pricing?model=MODEL_ID` endpoint. If that endpoint is unavailable, fall back to `/models` only for availability and say live pricing cannot be read.
- Assume users do not already have an API Key unless they clearly say they do. First guide them to register and verify a platform account, then create an API Key through this skill or user-api-center.
- Calling models through this skill does not require `超级个体` VIP. Any registered member can use the skill after account contact verification.
- Sensitive account operations through this skill require 24-hour phone-code authorization on the CN site. Sensitive operations include creating API Keys, listing API Keys, querying usage, querying logs, or testing models with a user key.
- Never ask the user to paste an API Key into chat for code examples. Use environment variables such as `VICROCODE_API_KEY`.
- Do not run live test calls until the user explicitly agrees, because tests may consume coins.
- If the user has no VicroCode username, verified phone, or API Key, guide them through registration, phone verification, 24-hour skill authorization, and API Key creation before testing.
- If the user asks how coins convert to RMB, use the platform rule `1 金币 = 0.01 元人民币` and `1 元人民币 = 100 金币`. Run `python scripts/vicro_models.py coin-rate` for a repeatable answer. Do not infer a different rate from recharge bonus packages.

## Workflow

1. Identify the target use case: chat, coding, image, image edit, video, embedding, Anthropic native messages, Gemini native generateContent, or another endpoint.
2. Ask for missing high-impact constraints: preferred vendor, quality versus cost priority, latency tolerance, streaming need, context length, and whether their VicroCode account is registered with a verified phone.
3. Load `references/vicrocode-model-gateway.md` when implementing or explaining API details.
4. If the user has not configured the API Key yet, print or summarize the setup guide:
   ```bash
   python scripts/vicro_models.py guide
   ```
5. For creating API Keys, listing API Keys, checking usage, checking logs, or running tests without an existing API Key, start phone authorization:
   ```bash
   python scripts/vicro_models.py auth-start PHONE
   python scripts/vicro_models.py auth-verify PHONE CODE
   ```
   Store the returned token in `VICROCODE_SKILL_AUTH_TOKEN`. The token expires after 24 hours.
6. If the user wants the skill to create an API Key, run:
   ```bash
   python scripts/vicro_models.py --skill-auth-token-env VICROCODE_SKILL_AUTH_TOKEN keys-create --name "Codex Skill"
   ```
   The full API Key is returned only once. Tell the user to store it in `VICROCODE_API_KEY`, then avoid reprinting it.
7. Fetch the live model list only after API Key setup is available:
   ```bash
   python scripts/vicro_models.py --api-key-env VICROCODE_API_KEY list
   ```
8. If the user supplies a loose model name such as `sora2`, normalize and search:
   ```bash
   python scripts/vicro_models.py --api-key-env VICROCODE_API_KEY search sora2
   ```
9. If several exact-looking candidates exist, list them with the tradeoff you can infer from endpoint type, vendor/name, and available pricing metadata. Ask which one to use before editing code.
10. If the user asks for price, run `price MODEL`. Treat `billing_options` as authoritative and show each option separately, for example `按次` and `按秒`. If `/models/pricing` is unavailable, only confirm model availability and do not infer live price from local import packages.
11. If the user asks how much one coin is worth, run:
   ```bash
   python scripts/vicro_models.py coin-rate
   ```
12. Generate integration code using the exact endpoint family:
   - OpenAI-compatible chat: `/chat/completions`
   - Image generation: `/images/generations`
   - Image edit: `/images/edits`
   - Video task creation: `/videos/generations`
   - Video task polling: `/videos/generations/{task_id}`
   - Embeddings: `/embeddings`
   - Anthropic native: base `https://api.vicoco.cn/api/gateway`, route `/v1/messages`
   - Gemini native: `/gemini/models/{model}:generateContent`
13. Offer a live smoke test only after the user confirms. Use `test-chat` for chat models, `test-video` for video task creation, and `poll-video` for existing video tasks. Clearly state that live creation can consume coins.

## Model Advice

- For cheap tests, prefer smaller or lite models when the live list contains names such as `mini`, `flash`, `lite`, `haiku`, `8b`, or `small`.
- For stronger reasoning or coding, prefer models with names such as `sonnet`, `opus`, `pro`, `max`, `coder`, `reasoning`, `thinking`, or higher dated versions.
- For image/video, do not assume chat endpoints. Use the model detail or endpoint family from the API Center before writing code.
- When price data is not available from the live API Center pricing response, say so directly. Do not present offline package values as current production prices.
- If a video model returns multiple billing options, ask the user to choose a route family before integration. `按次` is simpler for fixed task pricing; `按秒` is better when duration controls cost but requires passing `duration`, `duration_seconds`, or `seconds`.

## Registration And API Key Help

If the user has no API Key or cannot access API Center:

1. For CN/default users, direct them to `https://www.vicoco.cn/register-login`.
2. Tell them any registered member can use this skill after account contact verification; `超级个体` VIP is not required for skill-based model calls.
3. Tell CN users to bind and verify a phone number on the platform before using sensitive skill operations.
4. For sensitive skill operations, ask for the phone number only after explaining why it is needed, then run `auth-start PHONE`. The platform sends a verification code if the phone belongs to a verified VicroCode account.
5. After the user provides the code, run `auth-verify PHONE CODE` and store the returned token in `VICROCODE_SKILL_AUTH_TOKEN` for 24 hours.
6. Use `keys-create` to create an API Key when needed. Remind them the full key is shown only once and should be stored in `VICROCODE_API_KEY`.
7. If they prefer the website UI, tell them to open `用户中心 -> API中心 -> 我的API -> 新建 API Key`.

## Sensitive Operation Safety

- Do not treat phone possession as login. Use only the platform's skill-auth token returned after code verification.
- Do not use skill-auth for unrelated account actions. It is only for modelhub API Key creation/listing, usage query, log query, and explicit model tests.
- Do not reveal existing API Key plaintext through this skill. Creating a new key may return the plaintext once; later list operations should show only masked prefixes.
- If the authorization token is missing or expired, ask the user to repeat `auth-start` and `auth-verify`.
- If the user asks to send many codes, refuse and explain that the platform rate limits by user, phone, and IP to prevent abuse.

## Useful Script

Use `scripts/vicro_models.py` for repeatable API access:

- `guide`: print registration, phone verification, 24-hour skill authorization, and API Key setup guidance.
- `auth-start PHONE`: send a phone verification code for 24-hour skill authorization.
- `auth-verify PHONE CODE`: verify the phone code and return a 24-hour skill authorization token.
- `me`: show the account attached to the current skill authorization token.
- `keys-list`: list API Keys for the authorized account without revealing plaintext.
- `keys-create`: create an API Key for the authorized account and print the plaintext once.
- `usage`: query API Center usage summary for the authorized account.
- `logs`: query recent API Center call logs for the authorized account.
- `list`: fetch and print model IDs.
- `search QUERY`: fetch models and rank likely matches.
- `price MODEL`: fetch live model pricing, route groups, and mixed billing options from `/models/pricing`; fall back to availability-only when that endpoint is not deployed.
- `coin-rate`: print the VicroCode coin-to-RMB conversion rule and optionally convert `--coins` or `--cny` amounts.
- `test-chat MODEL`: run a minimal chat completion after explicit user approval.
- `test-video MODEL`: create a minimal video generation task after explicit user approval.
- `poll-video TASK_ID`: poll an existing video generation task without creating a new one.

The script uses only Python standard library modules.
