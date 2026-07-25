import asyncio
import html
import os
from typing import Any

import httpx


BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


def get_brevo_config_status() -> dict:
    """Return safe configuration diagnostics without exposing secret values."""
    required = {
        "BREVO_API_KEY": os.getenv("BREVO_API_KEY"),
        "BREVO_SENDER_EMAIL": os.getenv("BREVO_SENDER_EMAIL"),
        "ADMIN_EMAIL": os.getenv("ADMIN_EMAIL"),
    }
    missing = [name for name, value in required.items() if not str(value or "").strip()]
    return {
        "ready": not missing,
        "missing": missing,
        "sender_configured": bool(str(required["BREVO_SENDER_EMAIL"] or "").strip()),
        "admin_configured": bool(str(required["ADMIN_EMAIL"] or "").strip()),
        "api_key_configured": bool(str(required["BREVO_API_KEY"] or "").strip()),
    }


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe(value: Any) -> str:
    return html.escape(_clean(value), quote=True)


def _money(value: Any) -> str:
    try:
        return f"{float(value or 0):,.2f} EGP"
    except (TypeError, ValueError):
        return "0.00 EGP"


def _items_rows(items: list[dict]) -> str:
    if not items:
        return """
        <tr>
            <td colspan="4" style="padding:14px;border:1px solid #ead7de;text-align:center;">
                No products found
            </td>
        </tr>
        """

    rows: list[str] = []
    for item in items:
        name = _safe(item.get("product_name") or "Product")
        quantity = int(item.get("quantity") or 0)
        price = float(item.get("price") or 0)
        line_total = price * quantity

        rows.append(
            f"""
            <tr>
                <td style="padding:10px;border:1px solid #ead7de;">{name}</td>
                <td style="padding:10px;border:1px solid #ead7de;text-align:center;">{quantity}</td>
                <td style="padding:10px;border:1px solid #ead7de;text-align:center;">{_money(price)}</td>
                <td style="padding:10px;border:1px solid #ead7de;text-align:center;">{_money(line_total)}</td>
            </tr>
            """
        )

    return "".join(rows)


def _email_shell(title: str, body: str) -> str:
    return f"""
    <!doctype html>
    <html lang="en">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>{html.escape(title)}</title>
    </head>
    <body style="margin:0;background:#f8f3f5;font-family:Arial,Helvetica,sans-serif;color:#2a2024;">
        <div style="max-width:720px;margin:0 auto;padding:24px 12px;">
            <div style="background:#ffffff;border-radius:16px;overflow:hidden;border:1px solid #ead7de;">
                <div style="background:#8b2f52;color:#ffffff;padding:22px;text-align:center;">
                    <div style="font-size:26px;font-weight:700;letter-spacing:2px;">LUMIIE</div>
                    <div style="margin-top:6px;font-size:15px;">{html.escape(title)}</div>
                </div>
                <div style="padding:24px;">
                    {body}
                </div>
            </div>
            <p style="text-align:center;color:#7d6c73;font-size:12px;margin:14px 0 0;">
                This is an automatic transactional email from LUMIIE.
            </p>
        </div>
    </body>
    </html>
    """


def _order_table(order_data: dict) -> str:
    return f"""
    <table style="width:100%;border-collapse:collapse;margin-top:18px;font-size:14px;">
        <thead>
            <tr style="background:#f7edf1;">
                <th style="padding:10px;border:1px solid #ead7de;text-align:left;">Product</th>
                <th style="padding:10px;border:1px solid #ead7de;">Qty</th>
                <th style="padding:10px;border:1px solid #ead7de;">Price</th>
                <th style="padding:10px;border:1px solid #ead7de;">Total</th>
            </tr>
        </thead>
        <tbody>
            {_items_rows(order_data.get("items") or [])}
        </tbody>
    </table>
    """


def build_admin_email(order_data: dict) -> str:
    order_id = _safe(order_data.get("order_id"))
    coupon = _safe(order_data.get("discount_code") or "No coupon")
    notes = _safe(order_data.get("notes") or "No notes")

    body = f"""
        <h2 style="margin:0 0 12px;color:#8b2f52;">New order #{order_id}</h2>
        <p style="margin:0 0 18px;line-height:1.7;">
            A new order was placed successfully on the website.
        </p>

        <div style="background:#fff8fb;border:1px solid #ead7de;border-radius:12px;padding:16px;line-height:1.9;">
            <div><strong>Customer:</strong> {_safe(order_data.get("customer_name"))}</div>
            <div><strong>Email:</strong> {_safe(order_data.get("customer_email"))}</div>
            <div><strong>Phone:</strong> {_safe(order_data.get("customer_phone"))}</div>
            <div><strong>City:</strong> {_safe(order_data.get("customer_city"))}</div>
            <div><strong>Address:</strong> {_safe(order_data.get("customer_address"))}</div>
            <div><strong>Coupon:</strong> {coupon}</div>
            <div><strong>Notes:</strong> {notes}</div>
        </div>

        {_order_table(order_data)}

        <div style="margin-top:18px;background:#f7edf1;border-radius:12px;padding:16px;line-height:1.9;">
            <div><strong>Discount:</strong> {_money(order_data.get("discount_amount"))}</div>
            <div><strong>Shipping:</strong> {_money(order_data.get("shipping_amount"))}</div>
            <div style="font-size:18px;color:#8b2f52;"><strong>Order total:</strong> {_money(order_data.get("total_amount"))}</div>
        </div>
    """

    return _email_shell(f"New order #{order_id}", body)


def build_customer_email(order_data: dict) -> str:
    order_id = _safe(order_data.get("order_id"))
    customer_name = _safe(order_data.get("customer_name") or "Customer")

    body = f"""
        <h2 style="margin:0 0 12px;color:#8b2f52;">Thank you, {customer_name} 🤍</h2>
        <p style="margin:0;line-height:1.8;">
            We received your order <strong>#{order_id}</strong> successfully.
            No confirmation action is required from you. Our team will contact you if needed.
        </p>

        {_order_table(order_data)}

        <div style="margin-top:18px;background:#f7edf1;border-radius:12px;padding:16px;line-height:1.9;">
            <div><strong>Delivery city:</strong> {_safe(order_data.get("customer_city"))}</div>
            <div><strong>Delivery address:</strong> {_safe(order_data.get("customer_address"))}</div>
            <div><strong>Discount:</strong> {_money(order_data.get("discount_amount"))}</div>
            <div><strong>Shipping:</strong> {_money(order_data.get("shipping_amount"))}</div>
            <div style="font-size:18px;color:#8b2f52;"><strong>Total:</strong> {_money(order_data.get("total_amount"))}</div>
        </div>

        <p style="margin:22px 0 0;line-height:1.8;text-align:center;">
            Thank you for shopping with LUMIIE.
        </p>
    """

    return _email_shell(f"Order #{order_id} received", body)


async def _send_email(
    *,
    recipient_email: str,
    recipient_name: str,
    subject: str,
    html_content: str,
) -> dict:
    api_key = _clean(os.getenv("BREVO_API_KEY"))
    sender_email = _clean(os.getenv("BREVO_SENDER_EMAIL")).lower()
    sender_name = _clean(os.getenv("BREVO_SENDER_NAME") or "LUMIIE")
    reply_to_email = _clean(os.getenv("BREVO_REPLY_TO_EMAIL")).lower()

    if not api_key:
        error = "BREVO_API_KEY is missing"
        print(f"BREVO CONFIG ERROR: {error}", flush=True)
        return {"ok": False, "error": error}

    if not sender_email:
        error = "BREVO_SENDER_EMAIL is missing"
        print(f"BREVO CONFIG ERROR: {error}", flush=True)
        return {"ok": False, "error": error}

    if not recipient_email:
        error = "recipient email is missing"
        print(f"BREVO CONFIG ERROR: {error}", flush=True)
        return {"ok": False, "error": error}

    payload: dict[str, Any] = {
        "sender": {
            "name": sender_name,
            "email": sender_email,
        },
        "to": [
            {
                "name": recipient_name or "Customer",
                "email": recipient_email.lower().strip(),
            }
        ],
        "subject": subject,
        "htmlContent": html_content,
        "tags": ["lumie-order"],
    }

    if reply_to_email:
        payload["replyTo"] = {
            "name": sender_name,
            "email": reply_to_email,
        }

    headers = {
        "accept": "application/json",
        "content-type": "application/json",
        "api-key": api_key,
    }

    retryable_statuses = {408, 425, 429, 500, 502, 503, 504}

    print(
        f"BREVO: sending '{subject}' to {recipient_email} "
        f"from {sender_email}",
        flush=True,
    )

    async with httpx.AsyncClient(timeout=12.0) as client:
        for attempt in range(1, 4):
            try:
                response = await client.post(
                    BREVO_API_URL,
                    headers=headers,
                    json=payload,
                )

                if 200 <= response.status_code < 300:
                    try:
                        response_data = response.json()
                    except ValueError:
                        response_data = {"raw": response.text}
                    message_id = response_data.get("messageId")
                    print(
                        f"BREVO: email accepted for {recipient_email}; "
                        f"message_id={message_id}",
                        flush=True,
                    )
                    return {
                        "ok": True,
                        "recipient": recipient_email,
                        "status_code": response.status_code,
                        "message_id": message_id,
                    }

                print(
                    "BREVO ERROR:",
                    response.status_code,
                    response.text,
                    flush=True,
                )

                if response.status_code not in retryable_statuses:
                    return {
                        "ok": False,
                        "recipient": recipient_email,
                        "status_code": response.status_code,
                        "error": response.text,
                    }

            except (httpx.TimeoutException, httpx.RequestError) as error:
                print(f"BREVO NETWORK ERROR: {error}", flush=True)
            except Exception as error:
                print(f"BREVO UNEXPECTED ERROR: {error}", flush=True)
                return {
                    "ok": False,
                    "recipient": recipient_email,
                    "error": f"{type(error).__name__}: {error}",
                }

            if attempt < 3:
                await asyncio.sleep(attempt * 2)

    return {
        "ok": False,
        "recipient": recipient_email,
        "error": "Brevo request failed after retries",
    }


async def send_order_notification(order_data: dict) -> dict:
    """
    Automatically sends two transactional emails after the order is saved:
    1) admin notification
    2) customer order details

    Email failure never cancels or changes the saved order.
    """
    try:
        order_id = _clean(order_data.get("order_id") or "New")
        admin_email = _clean(os.getenv("ADMIN_EMAIL")).lower()
        customer_email = _clean(order_data.get("customer_email")).lower()
        customer_name = _clean(order_data.get("customer_name") or "Customer")
        sender_name = _clean(os.getenv("BREVO_SENDER_NAME") or "LUMIIE")

        tasks = []

        if admin_email:
            tasks.append(
                _send_email(
                    recipient_email=admin_email,
                    recipient_name="LUMIIE Admin",
                    subject=f"New order #{order_id} - {sender_name}",
                    html_content=build_admin_email(order_data),
                )
            )
        else:
            print("BREVO: ADMIN_EMAIL is missing", flush=True)

        if customer_email:
            tasks.append(
                _send_email(
                    recipient_email=customer_email,
                    recipient_name=customer_name,
                    subject=f"We received your order #{order_id} - {sender_name}",
                    html_content=build_customer_email(order_data),
                )
            )
        else:
            print(
                f"BREVO: customer email missing for order #{order_id}",
                flush=True,
            )

        if not tasks:
            return {
                "ok": False,
                "order_id": order_id,
                "error": "No email recipients were configured",
            }

        raw_results = await asyncio.gather(*tasks, return_exceptions=True)
        results = []
        for result in raw_results:
            if isinstance(result, Exception):
                results.append(
                    {
                        "ok": False,
                        "error": f"{type(result).__name__}: {result}",
                    }
                )
            else:
                results.append(result)

        return {
            "ok": all(item.get("ok") for item in results),
            "order_id": order_id,
            "results": results,
        }

    except Exception as error:
        # The order is already saved; email problems must not affect checkout.
        print(f"BREVO ORDER EMAIL ERROR: {error}", flush=True)
        return {
            "ok": False,
            "order_id": _clean(order_data.get("order_id") or "New"),
            "error": f"{type(error).__name__}: {error}",
        }
