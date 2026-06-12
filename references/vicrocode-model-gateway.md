# VicroCode Model Gateway Reference

## Base URLs

Default CN gateway:

```text
https://api.vicoco.cn/api/gateway/v1
```

Global gateway:

```text
https://api.vicrocode.com/api/gateway/v1
```

Anthropic SDK base URL is one path level higher:

```text
https://api.vicoco.cn/api/gateway
```

## Authentication

All public gateway calls require an API Key. Calls made through the `modelhub` skill do not require `超级个体` VIP; any registered member can use the skill after account contact verification.

Sensitive skill operations use a separate 24-hour authorization token. Sensitive operations include API Key creation/listing, usage query, log query, and model tests that use the user's account. On the CN site, the user must have a platform account with a bound and verified phone number.

Skill authorization flow:

```http
POST /api/gateway/skill-auth/phone/start/
Content-Type: application/json

{"phone": "13800138000"}
```

```http
POST /api/gateway/skill-auth/phone/verify/
Content-Type: application/json

{"phone": "13800138000", "code": "1234"}
```

The verify response returns a short-lived token. Send it to skill account endpoints as:

```http
Authorization: Bearer VICROCODE_SKILL_AUTH_TOKEN
```

or:

```http
X-VicroCode-Skill-Auth: VICROCODE_SKILL_AUTH_TOKEN
```

The token is valid for 24 hours and is not a platform login session.

Preferred header:

```http
Authorization: Bearer YOUR_API_KEY
```

Anthropic SDK-style calls may also use:

```http
x-api-key: YOUR_API_KEY
```

For code generation, read the key from an environment variable:

```bash
VICROCODE_API_KEY=...
```

For skill account operations, read the temporary token from:

```bash
VICROCODE_SKILL_AUTH_TOKEN=...
```

## Coin Conversion

VicroCode platform accounting uses:

```text
1 金币 = 0.01 元人民币
1 元人民币 = 100 金币
```

For repeatable answers, run:

```bash
python scripts/vicro_models.py coin-rate
```

This conversion comes from the API gateway billing rule that converts RMB cost to coins by multiplying by `100`, and settlement code that converts consumed coins back to RMB by multiplying by `0.01`. Recharge packages may include bonuses or discounts; do not use those packages to infer the accounting conversion rate.

## Model List

OpenAI-compatible model list:

```http
GET /api/gateway/v1/models
Authorization: Bearer YOUR_API_KEY
```

Expected shape:

```json
{
  "object": "list",
  "data": [
    {
      "id": "model-id",
      "object": "model",
      "owned_by": "vicrocode",
      "permission": []
    }
  ]
}
```

The public model-list response is intentionally minimal and does not include pricing, route group, or provider-channel detail. Do not infer production prices from offline import snapshots under `api-gateway-packages`; provider slugs in those files can differ from production naming such as `cm`.

Exact current pricing should come from the authenticated pricing endpoint:

```http
GET /api/gateway/v1/models/pricing?model=sora-2
Authorization: Bearer YOUR_API_KEY
```

Expected shape:

```json
{
  "status": "success",
  "data": {
    "model": {
      "public_model_name": "sora-2",
      "route_full_url": "https://api.vicoco.cn/api/gateway/v1/videos/generations",
      "billing_options": [
        {
          "billing_type": "per_request",
          "billing_type_label": "按次",
          "pricing_summary": "按次 250 金币/次",
          "route_summaries": []
        },
        {
          "billing_type": "per_second",
          "billing_type_label": "按秒",
          "pricing_summary": "按秒 30 金币/秒",
          "route_summaries": []
        }
      ]
    }
  }
}
```

If `/models/pricing` is not deployed, tell the user that exact live pricing is unavailable through the API and ask them to check the API Center model detail page.

Anthropic-style model list can be requested through `/api/gateway/v1/v1/models` or by sending `x-api-key` without `Authorization`.

## Endpoints

| Capability | Method | Path | Notes |
| --- | --- | --- | --- |
| Model list | GET | `/models` | Pull models available to the current key. |
| Model pricing | GET | `/models/pricing?model=MODEL_ID` | Pull live price groups and route summaries available to the current key. |
| Chat / multimodal chat | POST | `/chat/completions` | OpenAI-compatible; supports `stream`. |
| Image generation | POST | `/images/generations` | JSON request; returns URL or `b64_json` depending on channel. |
| Image edit | POST | `/images/edits` | `multipart/form-data`; upload `image`. |
| Video task creation | POST | `/videos/generations` | Async; returns `task_id`; per-second models need `duration`, `duration_seconds`, or `seconds`. |
| Video task polling | GET | `/videos/generations/{task_id}` | Poll status/result; do not create another task to poll. |
| Embeddings | POST | `/embeddings` | OpenAI-compatible embeddings format. |
| Anthropic native | POST | `/v1/messages` using `/api/gateway` base | Use Anthropic SDK-compatible shape. |
| Gemini native | POST | `/gemini/models/{model}:generateContent` | Use Gemini native shape. |

Video smoke tests must be explicit because task creation can consume coins:

```bash
python scripts/vicro_models.py --api-key-env VICROCODE_API_KEY test-video MODEL --duration 5 --poll
```

Poll an already-created task without creating a new one:

```bash
python scripts/vicro_models.py --api-key-env VICROCODE_API_KEY poll-video TASK_ID
```

## Common Errors

| HTTP | Code | Meaning |
| --- | --- | --- |
| 401 | `missing_api_key` / `invalid_api_key` | Missing or invalid API Key. |
| 401 | `missing_skill_auth_token` / `invalid_skill_auth_token` / `expired_skill_auth_token` | Missing, invalid, or expired skill authorization token. |
| 400 | `missing_model` | Request body has no `model`. |
| 400 | `missing_video_duration` | A per-second video model needs duration. |
| 402 | `insufficient_balance` | User coin balance is insufficient. |
| 403 | `api_key_unavailable` | Key is disabled, expired, or route is unavailable. |
| 403 | `phone_verification_required` | CN account must bind and verify a phone number before API use. |
| 404 | `model_not_found` | Model ID does not exist or is not exposed to this key. |
| 429 | `daily_request_limit` / `daily_coin_limit` | API Key limit reached. |
| 429 | `sms_rate_limited` / `skill_auth_rate_limited` | Phone-code sending or verification attempts are too frequent. |
| 502 | `upstream_error` / `all_channels_failed` | Upstream failed or all routes failed. |

## Choosing Models

Use exact IDs from the live model list. If the user types an alias:

- Normalize by lowercasing and removing punctuation: `sora2` and `sora-2` become comparable.
- Search by substring and token match.
- Show likely candidates instead of silently choosing one.
- Ask whether to test the preferred candidate.

Cost/effectiveness heuristics when detailed pricing is unavailable:

- Cheaper or lower latency: `mini`, `flash`, `lite`, `haiku`, `small`, `8b`.
- Stronger quality/reasoning/coding: `pro`, `max`, `sonnet`, `opus`, `coder`, `reasoning`, `thinking`, newer date/version.
- Video/image models often have endpoint-specific parameters and pricing. Verify endpoint type before coding.

When live pricing is available, prefer actual `billing_options` over name heuristics. If a model has both `per_request` and `per_second`, show both and ask the user which billing mode to integrate. If only `/models` data is available, state that pricing is not available from that endpoint.

## Registration And API Key Creation

Default CN path:

```text
https://www.vicoco.cn/register-login
```

Global path:

```text
https://www.vicrocode.com/register-login
```

After login:

1. Bind and verify a phone number on the CN site.
2. To create an API Key through the website UI, open:

```text
用户中心 -> API中心 -> 我的API -> 新建 API Key
```

3. To create an API Key through the skill, run `auth-start`, `auth-verify`, then `keys-create`.

Tell users:

- Save the full API Key immediately; it is shown only once.
- Store it in `VICROCODE_API_KEY`.
- CN site requires phone verification before API use.
- Global site may require email verification before API use.
- Do not reveal existing API Key plaintext through the skill; list operations should show only masked prefixes.
