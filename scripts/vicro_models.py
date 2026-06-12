#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from decimal import Decimal, InvalidOperation
from typing import Any


DEFAULT_BASE_URL = "https://api.vicoco.cn/api/gateway/v1"
DEFAULT_SITE_URL = "https://www.vicoco.cn"
DEFAULT_PLATFORM_API_BASE = "https://www.vicoco.cn/api"
COIN_TO_CNY_RATE = Decimal("0.01")
CNY_TO_COIN_RATE = Decimal("100")


def build_setup_guide(site_url: str = DEFAULT_SITE_URL) -> str:
    site = site_url.rstrip("/")
    return "\n".join(
        [
            "VicroCode API 中心配置步骤：",
            f"1. 注册或登录：{site}/register-login",
            "2. 绑定并验证手机号。通过 modelhub 技能调用模型不要求“超级个体”会员，注册会员即可。",
            "3. 如需让技能创建 API Key、查用量或查日志，先发送验证码：python scripts/vicro_models.py auth-start 手机号",
            "4. 收到验证码后换取 24 小时授权：python scripts/vicro_models.py auth-verify 手机号 验证码",
            "5. 将返回的 token 配置到环境变量 VICROCODE_SKILL_AUTH_TOKEN。",
            "6. 创建 API Key：python scripts/vicro_models.py keys-create --name \"Codex Skill\"",
            "7. 完整 API Key 只展示一次，请立即保存，并配置到环境变量 VICROCODE_API_KEY。",
            "",
            "不要在聊天中粘贴 API Key。验证码和授权 token 也不要转发给陌生人。",
        ]
    )


def missing_api_key_message(args: argparse.Namespace) -> str:
    return "未检测到 API Key。\n\n" + build_setup_guide(getattr(args, "site_url", DEFAULT_SITE_URL))


def normalize_model_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").lower())


def get_api_key(args: argparse.Namespace) -> str:
    if args.api_key:
        return args.api_key.strip()
    if args.api_key_env:
        return os.environ.get(args.api_key_env, "").strip()
    return os.environ.get("VICROCODE_API_KEY", "").strip()


def get_skill_auth_token(args: argparse.Namespace) -> str:
    if getattr(args, "skill_auth_token", ""):
        return args.skill_auth_token.strip()
    token_env = getattr(args, "skill_auth_token_env", "") or "VICROCODE_SKILL_AUTH_TOKEN"
    if token_env:
        return os.environ.get(token_env, "").strip()
    return os.environ.get("VICROCODE_SKILL_AUTH_TOKEN", "").strip()


def missing_skill_auth_message(args: argparse.Namespace) -> str:
    return "\n".join(
        [
            "未检测到 modelhub 24 小时授权 token。",
            "",
            "请先执行：",
            "python scripts/vicro_models.py auth-start 手机号",
            "python scripts/vicro_models.py auth-verify 手机号 验证码",
            "",
            f"然后把返回的 token 配置到环境变量 {getattr(args, 'skill_auth_token_env', 'VICROCODE_SKILL_AUTH_TOKEN')}。",
        ]
    )


def request_json(
    method: str,
    url: str,
    api_key: str = "",
    payload: dict[str, Any] | None = None,
    timeout: int = 120,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = None
    request_headers = dict(headers or {})
    if api_key:
        request_headers["Authorization"] = f"Bearer {api_key}"
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(url, data=body, headers=request_headers, method=method.upper())
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return json.loads(response.read().decode(charset))
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {exc.code}: {text}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Request failed: {exc}") from exc


def platform_api_url(args: argparse.Namespace, path: str, query: dict[str, Any] | None = None) -> str:
    base = getattr(args, "platform_api_base", DEFAULT_PLATFORM_API_BASE).rstrip("/")
    normalized_path = "/" + path.lstrip("/")
    url = f"{base}{normalized_path}"
    if query:
        cleaned = {key: value for key, value in query.items() if value not in (None, "")}
        if cleaned:
            url = f"{url}?{urllib.parse.urlencode(cleaned)}"
    return url


def request_skill_json(
    args: argparse.Namespace,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query: dict[str, Any] | None = None,
    require_auth: bool = True,
) -> dict[str, Any]:
    headers: dict[str, str] = {}
    if require_auth:
        token = get_skill_auth_token(args)
        if not token:
            raise SystemExit(missing_skill_auth_message(args))
        headers["Authorization"] = f"Bearer {token}"
        headers["X-VicroCode-Skill-Auth"] = token
    return request_json(
        method,
        platform_api_url(args, path, query=query),
        payload=payload,
        timeout=args.timeout,
        headers=headers,
    )


def print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def parse_decimal(value: str, label: str) -> Decimal:
    try:
        return Decimal(str(value).strip())
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise SystemExit(f"Invalid {label}: {value}") from exc


def format_decimal_text(value: Decimal) -> str:
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def extract_models(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = payload.get("data")
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    results = payload.get("results")
    if isinstance(results, list):
        return [item for item in results if isinstance(item, dict)]
    return []


def model_id(item: dict[str, Any]) -> str:
    return str(item.get("id") or item.get("public_model_name") or item.get("model") or "").strip()


def fetch_models(args: argparse.Namespace) -> list[dict[str, Any]]:
    api_key = get_api_key(args)
    if not api_key:
        raise SystemExit(missing_api_key_message(args))
    base_url = args.base_url.rstrip("/")
    payload = request_json("GET", f"{base_url}/models", api_key, timeout=args.timeout)
    return extract_models(payload)


def fetch_model_pricing(args: argparse.Namespace, model: str) -> dict[str, Any]:
    api_key = get_api_key(args)
    if not api_key:
        raise SystemExit(missing_api_key_message(args))
    base_url = args.base_url.rstrip("/")
    query = urllib.parse.urlencode({"model": model})
    payload = request_json("GET", f"{base_url}/models/pricing?{query}", api_key, timeout=args.timeout)
    data = payload.get("data") if isinstance(payload, dict) else {}
    if isinstance(data, dict) and isinstance(data.get("model"), dict):
        return data["model"]
    if isinstance(payload.get("model"), dict):
        return payload["model"]
    return payload


def command_list(args: argparse.Namespace) -> int:
    models = fetch_models(args)
    ids = [model_id(item) for item in models if model_id(item)]
    if args.json:
        print(json.dumps(models, ensure_ascii=False, indent=2))
    else:
        for item in ids:
            print(item)
        print(f"\nTotal: {len(ids)}", file=sys.stderr)
    return 0


def score_match(query: str, candidate: str) -> int:
    normalized_query = normalize_model_name(query)
    normalized_candidate = normalize_model_name(candidate)
    if not normalized_query or not normalized_candidate:
        return 0
    if normalized_query == normalized_candidate:
        return 100
    if normalized_query in normalized_candidate:
        return 80

    score = 0
    query_parts = [part for part in re.split(r"[^a-zA-Z0-9]+", query.lower()) if part]
    candidate_lower = candidate.lower()
    for part in query_parts:
        if part in candidate_lower:
            score += 15

    digits = "".join(re.findall(r"\d+", query))
    if score > 0 and digits and digits in "".join(re.findall(r"\d+", candidate)):
        score += 10
    return score


def command_search(args: argparse.Namespace) -> int:
    models = fetch_models(args)
    ranked: list[tuple[int, str]] = []
    for item in models:
        candidate = model_id(item)
        score = score_match(args.query, candidate)
        if score > 0:
            ranked.append((score, candidate))
    ranked.sort(key=lambda item: (-item[0], item[1]))

    if not ranked:
        print(f"No model candidates matched: {args.query}")
        return 1

    for score, candidate in ranked[: args.limit]:
        print(f"{candidate}\t(score={score})")
    return 0


def command_price(args: argparse.Namespace) -> int:
    try:
        pricing = fetch_model_pricing(args, args.model)
    except SystemExit as exc:
        message = str(exc)
        if any(code in message for code in ("model_not_found", "VIP_REQUIRED", "invalid_api_key", "missing_api_key", "api_key_unavailable")):
            raise
        if "/models/pricing" not in message and "gateway_model_pricing" not in message and "404" not in message:
            raise
        models = fetch_models(args)
        exact_matches = [model_id(item) for item in models if model_id(item) == args.model]
        if not exact_matches:
            candidates: list[tuple[int, str]] = []
            for item in models:
                candidate = model_id(item)
                score = score_match(args.model, candidate)
                if score > 0:
                    candidates.append((score, candidate))
            candidates.sort(key=lambda item: (-item[0], item[1]))
            print(f"未在 /models 中找到精确模型：{args.model}")
            if candidates:
                print("可能候选：")
                for score, candidate in candidates[: args.limit]:
                    print(f"- {candidate} (score={score})")
            return 1

        print(f"模型可用：{args.model}")
        print("当前网关尚未开放 /models/pricing，只能确认模型存在，不能读取实时价格。")
        return 0

    model_name = str(pricing.get("public_model_name") or args.model)
    print(f"模型：{model_name}")
    print(f"接口：{pricing.get('route_method', 'POST')} {pricing.get('route_full_url') or pricing.get('route_path') or '-'}")
    print(f"当前最优线路：{pricing.get('best_provider_name') or '-'} / {pricing.get('best_provider_group_name') or '-'}")
    print("")

    options = pricing.get("billing_options")
    if not isinstance(options, list) or not options:
        options = [pricing]

    print("计费选项：")
    for option in options:
        if not isinstance(option, dict):
            continue
        billing_type = str(option.get("billing_type") or "")
        billing_label = str(option.get("billing_type_label") or billing_type or "unknown")
        summary = str(option.get("pricing_summary") or "").strip()
        unit = str(option.get("unit_label") or "").strip()
        if not summary:
            if billing_type in {"per_request", "per_video_size"}:
                summary = (
                    f"{billing_label} {option.get('fixed_sale_price_min') or option.get('fixed_sale_price') or 0}-"
                    f"{option.get('fixed_sale_price_max') or option.get('fixed_sale_price') or 0} 金币"
                )
            elif billing_type == "per_second":
                summary = (
                    f"{billing_label} {option.get('input_sale_price_min') or option.get('input_sale_price') or 0}-"
                    f"{option.get('input_sale_price_max') or option.get('input_sale_price') or 0} 金币/秒"
                )
            else:
                summary = (
                    f"输入 {option.get('input_sale_price_min') or option.get('input_sale_price') or 0}-"
                    f"{option.get('input_sale_price_max') or option.get('input_sale_price') or 0}，"
                    f"输出 {option.get('output_sale_price_min') or option.get('output_sale_price') or 0}-"
                    f"{option.get('output_sale_price_max') or option.get('output_sale_price') or 0} 金币"
                )
        print(f"- {billing_label}: {summary}")
        if unit:
            print(f"  单位：{unit}")
        routes = option.get("route_summaries")
        if isinstance(routes, list):
            for route in routes[: args.limit]:
                if not isinstance(route, dict):
                    continue
                provider = str(route.get("provider_name") or "-")
                group = str(route.get("provider_group_name") or "-")
                price = str(route.get("display_price_label") or route.get("pricing_summary") or "-")
                health = str(route.get("health_status_label") or route.get("health_status") or "-")
                tags = route.get("summary_tags")
                tag_text = f" [{' / '.join(str(item) for item in tags)}]" if isinstance(tags, list) and tags else ""
                print(f"  - {provider} / {group}: {price}, {health}{tag_text}")

    if len(options) > 1:
        billing_labels = []
        billing_types = set()
        for option in options:
            if not isinstance(option, dict):
                continue
            label = str(option.get("billing_type_label") or option.get("billing_type") or "").strip()
            billing_type = str(option.get("billing_type") or "").strip()
            if label and label not in billing_labels:
                billing_labels.append(label)
            if billing_type:
                billing_types.add(billing_type)
        label_text = "、".join(billing_labels) if billing_labels else "多种计费方式"
        print("")
        print(f"该模型存在多种计费方式（{label_text}）。接入前应让用户选择要走哪种路线。")
        if "per_second" in billing_types:
            print("按秒路线通常需要传 duration/seconds，否则可能无法准确扣费。")
    return 0


def command_coin_rate(args: argparse.Namespace) -> int:
    print("1 金币 = 0.01 元人民币")
    print("1 元人民币 = 100 金币")
    print("说明：API 网关计费按人民币成本 * 100 转金币，金币结算收入按金币 * 0.01 转人民币。")

    if args.coins:
        coins = parse_decimal(args.coins, "--coins")
        print(f"{format_decimal_text(coins)} 金币 = {format_decimal_text(coins * COIN_TO_CNY_RATE)} 元人民币")
    if args.cny:
        cny = parse_decimal(args.cny, "--cny")
        print(f"{format_decimal_text(cny)} 元人民币 = {format_decimal_text(cny * CNY_TO_COIN_RATE)} 金币")
    return 0


def parse_csv_ints(value: str) -> list[int]:
    results: list[int] = []
    for item in re.split(r"[,，\s]+", str(value or "").strip()):
        if not item:
            continue
        try:
            parsed = int(item)
        except ValueError:
            raise SystemExit(f"Invalid integer list item: {item}")
        if parsed > 0 and parsed not in results:
            results.append(parsed)
    return results


def parse_csv_strings(value: str) -> list[str]:
    results: list[str] = []
    for item in re.split(r"[,，\s]+", str(value or "").strip()):
        item = item.strip()
        if item and item not in results:
            results.append(item)
    return results


def command_auth_start(args: argparse.Namespace) -> int:
    payload = {"phone": args.phone}
    data = request_skill_json(
        args,
        "POST",
        "/gateway/skill-auth/phone/start/",
        payload=payload,
        require_auth=False,
    )
    print_json(data)
    return 0


def command_auth_verify(args: argparse.Namespace) -> int:
    payload = {"phone": args.phone, "code": args.code}
    data = request_skill_json(
        args,
        "POST",
        "/gateway/skill-auth/phone/verify/",
        payload=payload,
        require_auth=False,
    )
    print_json(data)
    token = ""
    data_obj = data.get("data") if isinstance(data, dict) else {}
    if isinstance(data_obj, dict):
        token = str(data_obj.get("auth_token") or "").strip()
    if token:
        print("", file=sys.stderr)
        print(f"Set environment variable: VICROCODE_SKILL_AUTH_TOKEN={token}", file=sys.stderr)
    return 0


def command_me(args: argparse.Namespace) -> int:
    print_json(request_skill_json(args, "GET", "/gateway/skill/me/"))
    return 0


def command_keys_list(args: argparse.Namespace) -> int:
    query = {
        "include_route_options": "1" if args.include_route_options else "0",
    }
    print_json(request_skill_json(args, "GET", "/gateway/skill/api-keys/", query=query))
    return 0


def command_keys_create(args: argparse.Namespace) -> int:
    payload = {
        "key_name": args.name,
        "expiry_type": args.expiry_type,
        "daily_request_limit": args.daily_request_limit,
        "daily_coin_limit": args.daily_coin_limit,
        "total_coin_limit": args.total_coin_limit,
        "route_mode": args.route_mode,
        "route_provider_ids": parse_csv_ints(args.route_provider_ids),
        "allowed_ips": parse_csv_strings(args.allowed_ips),
        "remark": args.remark,
        "idempotency_key": args.idempotency_key,
    }
    data = request_skill_json(args, "POST", "/gateway/skill/api-keys/create/", payload=payload)
    print_json(data)
    api_key = ""
    data_obj = data.get("data") if isinstance(data, dict) else {}
    if isinstance(data_obj, dict):
        api_key = str(data_obj.get("api_key") or "").strip()
    if api_key:
        print("", file=sys.stderr)
        print("Full API Key is shown once. Store it in VICROCODE_API_KEY and do not paste it into chat.", file=sys.stderr)
    return 0


def command_usage(args: argparse.Namespace) -> int:
    query = {
        "limit": args.limit,
        "summary_only": "1" if args.summary_only else "0",
    }
    print_json(request_skill_json(args, "GET", "/gateway/skill/usage/", query=query))
    return 0


def command_logs(args: argparse.Namespace) -> int:
    query = {
        "limit": args.limit,
        "page": args.page,
    }
    print_json(request_skill_json(args, "GET", "/gateway/skill/logs/", query=query))
    return 0


def command_test_chat(args: argparse.Namespace) -> int:
    api_key = get_api_key(args)
    if not api_key:
        raise SystemExit(missing_api_key_message(args))
    payload = {
        "model": args.model,
        "messages": [{"role": "user", "content": args.prompt}],
        "stream": False,
    }
    data = request_json(
        "POST",
        f"{args.base_url.rstrip('/')}/chat/completions",
        api_key,
        payload=payload,
        timeout=args.timeout,
    )
    print_json(data)
    return 0


def extract_task_id(payload: dict[str, Any]) -> str:
    for key in ("task_id", "taskId", "taskID", "id", "video_id", "videoId"):
        value = payload.get(key)
        if value:
            return str(value)

    for key in ("data", "task", "job", "result", "output"):
        value = payload.get(key)
        if isinstance(value, dict):
            task_id = extract_task_id(value)
            if task_id:
                return task_id
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    task_id = extract_task_id(item)
                    if task_id:
                        return task_id
    return ""


def extract_status(payload: dict[str, Any]) -> str:
    for key in ("status", "state", "task_status", "taskStatus", "phase"):
        value = payload.get(key)
        if value:
            return str(value).lower()
    for key in ("data", "task", "job", "result", "output"):
        value = payload.get(key)
        if isinstance(value, dict):
            status = extract_status(value)
            if status:
                return status
    return ""


def payload_has_video_result(payload: dict[str, Any]) -> bool:
    for key in ("url", "video_url", "videoUrl", "output_url", "outputUrl", "download_url", "downloadUrl"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return True
    for key in ("data", "task", "job", "result", "output", "videos"):
        value = payload.get(key)
        if isinstance(value, dict) and payload_has_video_result(value):
            return True
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict) and payload_has_video_result(item):
                    return True
                if isinstance(item, str) and item.strip().lower().startswith(("http://", "https://")):
                    return True
    return False


def poll_video_task(args: argparse.Namespace, task_id: str) -> int:
    api_key = get_api_key(args)
    if not api_key:
        raise SystemExit(missing_api_key_message(args))

    base_url = args.base_url.rstrip("/")
    escaped_task_id = urllib.parse.quote(task_id, safe="")
    terminal_success = {"completed", "complete", "succeeded", "success", "finished", "done", "finish", "successed"}
    terminal_failure = {"failed", "failure", "cancelled", "canceled", "error", "rejected", "timeout"}

    for attempt in range(1, args.max_polls + 1):
        data = request_json(
            "GET",
            f"{base_url}/videos/generations/{escaped_task_id}",
            api_key,
            timeout=args.timeout,
        )
        print_json(data)

        status = extract_status(data)
        if status in terminal_success or payload_has_video_result(data):
            return 0
        if status in terminal_failure:
            return 1
        if attempt < args.max_polls:
            time.sleep(args.poll_interval)
    return 0


def command_test_video(args: argparse.Namespace) -> int:
    api_key = get_api_key(args)
    if not api_key:
        raise SystemExit(missing_api_key_message(args))

    payload: dict[str, Any] = {
        "model": args.model,
        "prompt": args.prompt,
    }
    if args.duration:
        payload[args.duration_field] = args.duration
    if args.size:
        payload["size"] = args.size
    if args.extra_json:
        try:
            extra = json.loads(args.extra_json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --extra-json: {exc}") from exc
        if not isinstance(extra, dict):
            raise SystemExit("--extra-json must decode to a JSON object.")
        payload.update(extra)

    data = request_json(
        "POST",
        f"{args.base_url.rstrip('/')}/videos/generations",
        api_key,
        payload=payload,
        timeout=args.timeout,
    )
    print_json(data)

    if not args.poll:
        return 0

    task_id = extract_task_id(data)
    if not task_id:
        raise SystemExit("Video task was created, but no task_id/id was found in the response.")
    return poll_video_task(args, task_id)


def command_poll_video(args: argparse.Namespace) -> int:
    return poll_video_task(args, args.task_id)


def command_guide(args: argparse.Namespace) -> int:
    print(build_setup_guide(args.site_url))
    return 0


def add_poll_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--poll-interval", type=int, default=10, help="Seconds between video polling requests")
    parser.add_argument("--max-polls", type=int, default=30, help="Maximum polling attempts")


def add_video_test_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("model")
    parser.add_argument("--prompt", default="A five-second cinematic shot of a red kite over a quiet lake.")
    parser.add_argument("--duration", default="", help="Optional video duration value, for example 5 or 10")
    parser.add_argument(
        "--duration-field",
        default="duration",
        choices=("duration", "duration_seconds", "seconds"),
        help="Request field name used for duration-sensitive video models",
    )
    parser.add_argument("--size", default="", help="Optional video size, for example 1280x720")
    parser.add_argument("--extra-json", default="", help="Extra JSON object merged into the request payload")
    parser.add_argument("--poll", action="store_true", help="Poll the returned task until completion or max polls")
    add_poll_options(parser)


def add_poll_video_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("task_id")
    add_poll_options(parser)


def _parser_epilog() -> str:
    return "Live test commands may consume coins. Run them only after explicit user approval."


def _configure_test_chat_parser(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("model")
    parser.add_argument("--prompt", default="ping")


def _set_parser_epilog(parser: argparse.ArgumentParser) -> None:
    parser.epilog = _parser_epilog()


def _add_live_test_parser(subparsers: argparse._SubParsersAction, name: str, help_text: str) -> argparse.ArgumentParser:
    parser = subparsers.add_parser(name, help=help_text)
    _set_parser_epilog(parser)
    return parser


def _add_test_chat_parser(subparsers: argparse._SubParsersAction) -> None:
    test_parser = _add_live_test_parser(subparsers, "test-chat", "Run a minimal chat completion after user approval")
    _configure_test_chat_parser(test_parser)
    test_parser.set_defaults(func=command_test_chat)


def _add_test_video_parser(subparsers: argparse._SubParsersAction) -> None:
    test_parser = _add_live_test_parser(subparsers, "test-video", "Create a minimal video task after user approval")
    add_video_test_options(test_parser)
    test_parser.set_defaults(func=command_test_video)


def _add_poll_video_parser(subparsers: argparse._SubParsersAction) -> None:
    poll_parser = subparsers.add_parser("poll-video", help="Poll an existing video generation task")
    add_poll_video_options(poll_parser)
    poll_parser.set_defaults(func=command_poll_video)


def _add_model_discovery_parsers(subparsers: argparse._SubParsersAction) -> None:
    guide_parser = subparsers.add_parser("guide", help="Print registration, phone verification, and API Key setup guidance")
    guide_parser.set_defaults(func=command_guide)

    list_parser = subparsers.add_parser("list", help="Fetch and print available model IDs")
    list_parser.add_argument("--json", action="store_true", help="Print raw JSON model entries")
    list_parser.set_defaults(func=command_list)

    search_parser = subparsers.add_parser("search", help="Search model IDs by fuzzy alias")
    search_parser.add_argument("query")
    search_parser.add_argument("--limit", type=int, default=20)
    search_parser.set_defaults(func=command_search)

    price_parser = subparsers.add_parser("price", help="Confirm model availability and explain live pricing lookup")
    price_parser.add_argument("model")
    price_parser.add_argument("--limit", type=int, default=8)
    price_parser.set_defaults(func=command_price)

    coin_rate_parser = subparsers.add_parser("coin-rate", help="Show VicroCode coin to RMB conversion")
    coin_rate_parser.add_argument("--coins", default="", help="Optional coin amount to convert to RMB")
    coin_rate_parser.add_argument("--cny", default="", help="Optional RMB amount to convert to coins")
    coin_rate_parser.set_defaults(func=command_coin_rate)


def _add_skill_account_parsers(subparsers: argparse._SubParsersAction) -> None:
    auth_start_parser = subparsers.add_parser("auth-start", help="Send a phone code for 24-hour modelhub authorization")
    auth_start_parser.add_argument("phone")
    auth_start_parser.set_defaults(func=command_auth_start)

    auth_verify_parser = subparsers.add_parser("auth-verify", help="Verify phone code and return a 24-hour authorization token")
    auth_verify_parser.add_argument("phone")
    auth_verify_parser.add_argument("code")
    auth_verify_parser.set_defaults(func=command_auth_verify)

    me_parser = subparsers.add_parser("me", help="Show the account attached to the current skill token")
    me_parser.set_defaults(func=command_me)

    keys_list_parser = subparsers.add_parser("keys-list", help="List API Keys without revealing plaintext")
    keys_list_parser.add_argument("--include-route-options", action="store_true", help="Include provider route options")
    keys_list_parser.set_defaults(func=command_keys_list)

    keys_create_parser = subparsers.add_parser("keys-create", help="Create an API Key and print it once")
    keys_create_parser.add_argument("--name", default="Codex Skill", help="API Key display name")
    keys_create_parser.add_argument(
        "--expiry-type",
        default="never",
        choices=("never", "1d", "7d", "1m", "3m", "6m", "1y"),
        help="API Key expiry policy",
    )
    keys_create_parser.add_argument("--daily-request-limit", type=int, default=0)
    keys_create_parser.add_argument("--daily-coin-limit", default="0")
    keys_create_parser.add_argument("--total-coin-limit", default="0")
    keys_create_parser.add_argument("--route-mode", default="smart_all", choices=("smart_all", "provider_select"))
    keys_create_parser.add_argument("--route-provider-ids", default="", help="Comma-separated provider IDs for provider_select")
    keys_create_parser.add_argument("--allowed-ips", default="", help="Comma-separated allowed IPs")
    keys_create_parser.add_argument("--remark", default="Created by modelhub skill")
    keys_create_parser.add_argument("--idempotency-key", default="", help="Optional key to avoid duplicate creation on retry")
    keys_create_parser.set_defaults(func=command_keys_create)

    usage_parser = subparsers.add_parser("usage", help="Query API Center usage for the authorized account")
    usage_parser.add_argument("--limit", type=int, default=20)
    usage_parser.add_argument("--summary-only", action="store_true")
    usage_parser.set_defaults(func=command_usage)

    logs_parser = subparsers.add_parser("logs", help="Query API Center call logs for the authorized account")
    logs_parser.add_argument("--limit", type=int, default=20)
    logs_parser.add_argument("--page", type=int, default=1)
    logs_parser.set_defaults(func=command_logs)


def _add_command_parsers(subparsers: argparse._SubParsersAction) -> None:
    _add_model_discovery_parsers(subparsers)
    _add_skill_account_parsers(subparsers)
    _add_test_chat_parser(subparsers)
    _add_test_video_parser(subparsers)
    _add_poll_video_parser(subparsers)


def command_not_reached(_: argparse.Namespace) -> int:
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="VicroCode model gateway helper")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help=f"Gateway base URL. Default: {DEFAULT_BASE_URL}")
    parser.add_argument("--site-url", default=DEFAULT_SITE_URL, help=f"VicroCode site URL for setup guidance. Default: {DEFAULT_SITE_URL}")
    parser.add_argument("--platform-api-base", default=DEFAULT_PLATFORM_API_BASE, help=f"VicroCode platform API base. Default: {DEFAULT_PLATFORM_API_BASE}")
    parser.add_argument("--api-key-env", default="VICROCODE_API_KEY", help="Environment variable that stores the API key")
    parser.add_argument("--api-key", default="", help="API key value. Prefer --api-key-env for safety")
    parser.add_argument("--skill-auth-token-env", default="VICROCODE_SKILL_AUTH_TOKEN", help="Environment variable that stores the 24-hour skill token")
    parser.add_argument("--skill-auth-token", default="", help="24-hour skill token. Prefer --skill-auth-token-env for safety")
    parser.add_argument("--timeout", type=int, default=120)

    subparsers = parser.add_subparsers(dest="command", required=True)
    _add_command_parsers(subparsers)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
