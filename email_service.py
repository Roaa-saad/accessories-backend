import os
import httpx
from dotenv import load_dotenv

load_dotenv()

# Mailgun configuration - uses HTTP API (works on Railway)
MAILGUN_API_KEY = os.getenv("MAILGUN_API_KEY")
MAILGUN_DOMAIN = os.getenv("MAILGUN_DOMAIN")
MAILGUN_FROM_EMAIL = os.getenv("MAILGUN_FROM_EMAIL", "Accessories Store <noreply@mg.yourdomain.com>")
ADMIN_EMAILS = ["roaam5182@gmail.com", "mahasaad3343@gmail.com"]


async def send_order_notification(order_data: dict):
    """
    Send order notification email via Mailgun HTTP API
    Works on Railway (no SMTP port blocking)
    """
    if not MAILGUN_API_KEY or not MAILGUN_DOMAIN:
        print("⚠️ Warning: Mailgun credentials not configured. Email not sent.")
        return False
    
    try:
        # Calculate total
        total = sum(item['quantity'] * item['price'] for item in order_data['items'])
        
        # Create HTML email body
        html = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #ddd; border-radius: 8px;">
                <h2 style="color: #4CAF50; text-align: center;">🛒 New Order Received!</h2>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Order Details</h3>
                    <p><strong>Order ID:</strong> #{order_data['order_id']}</p>
                </div>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Customer Information</h3>
                    <p><strong>Name:</strong> {order_data['customer_name']}</p>
                    <p><strong>Email:</strong> {order_data['customer_email']}</p>
                    <p><strong>Phone:</strong> {order_data['customer_phone']}</p>
                    <p><strong>City:</strong> {order_data.get('customer_city', 'N/A')}</p>
                    <p><strong>Address:</strong> {order_data['customer_address']}</p>
                </div>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3 style="margin-top: 0;">Order Items</h3>
                    <table style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background-color: #4CAF50; color: white;">
                                <th style="padding: 10px; text-align: left;">Product</th>
                                <th style="padding: 10px; text-align: center;">Quantity</th>
                                <th style="padding: 10px; text-align: right;">Price</th>
                                <th style="padding: 10px; text-align: right;">Subtotal</th>
                            </tr>
                        </thead>
                        <tbody>
        """
        
        for item in order_data['items']:
            subtotal = item['quantity'] * item['price']
            html += f"""
                            <tr style="border-bottom: 1px solid #ddd;">
                                <td style="padding: 10px;">{item['product_name']}</td>
                                <td style="padding: 10px; text-align: center;">{item['quantity']}</td>
                                <td style="padding: 10px; text-align: right;">{item['price']} EGP</td>
                                <td style="padding: 10px; text-align: right;">{subtotal} EGP</td>
                            </tr>
            """
        
        html += f"""
                        </tbody>
                        <tfoot>
                            <tr style="font-weight: bold; background-color: #f0f0f0;">
                                <td colspan="3" style="padding: 10px; text-align: right;">Total:</td>
                                <td style="padding: 10px; text-align: right;">{total} EGP</td>
                            </tr>
                        </tfoot>
                    </table>
                </div>
                
                <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd;">
                    <p style="color: #666; font-size: 12px;">
                        This is an automated notification from your Accessories Store.
                    </p>
                </div>
            </div>
        </body>
        </html>
        """
        
        print(f"🔄 Sending email via Mailgun API to {', '.join(ADMIN_EMAILS)}")
        
        # Send via Mailgun HTTP API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
                auth=("api", MAILGUN_API_KEY),
                data={
                    "from": MAILGUN_FROM_EMAIL,
                    "to": ADMIN_EMAILS,
                    "subject": f"🛒 New Order #{order_data['order_id']} - {order_data['customer_name']}",
                    "html": html,
                }
            )
        
        if response.status_code == 200:
            print(f"✅ Order notification email sent successfully to {', '.join(ADMIN_EMAILS)}")
            return True
        else:
            print(f"❌ Mailgun API error: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Error sending email: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False
