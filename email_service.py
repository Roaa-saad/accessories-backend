import os
import base64
import httpx
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Gmail API configuration - 100% FREE, uses OAuth tokens
GMAIL_REFRESH_TOKEN = os.getenv("GMAIL_REFRESH_TOKEN")
GMAIL_CLIENT_ID = os.getenv("GMAIL_CLIENT_ID")
GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
GMAIL_USER_EMAIL = os.getenv("GMAIL_USER_EMAIL", "roaam5182@gmail.com")
ADMIN_EMAILS = ["roaam5182@gmail.com", "mahasaad3343@gmail.com"]


async def get_gmail_access_token():
    """Get fresh access token from refresh token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id": GMAIL_CLIENT_ID,
                "client_secret": GMAIL_CLIENT_SECRET,
                "refresh_token": GMAIL_REFRESH_TOKEN,
                "grant_type": "refresh_token"
            }
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        else:
            raise Exception(f"Failed to get access token: {response.text}")


async def send_order_notification(order_data: dict):
    """
    Send order notification via Gmail API
    100% FREE - No SMTP, uses OAuth tokens
    """
    if not all([GMAIL_REFRESH_TOKEN, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET]):
        print("⚠️ Warning: Gmail API credentials not configured. Email not sent.")
        return False
    
    try:
        # Get access token
        access_token = await get_gmail_access_token()
        
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
        
        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = GMAIL_USER_EMAIL
        message["To"] = ", ".join(ADMIN_EMAILS)
        message["Subject"] = f"🛒 New Order #{order_data['order_id']} - {order_data['customer_name']}"
        message.attach(MIMEText(html, "html"))
        
        # Encode message for Gmail API
        raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        print(f"🔄 Sending email via Gmail API to {', '.join(ADMIN_EMAILS)}")
        
        # Send via Gmail API
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/send",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json"
                },
                json={"raw": raw_message}
            )
        
        if response.status_code == 200:
            print(f"✅ Email sent successfully via Gmail API to {', '.join(ADMIN_EMAILS)}")
            return True
        else:
            print(f"❌ Gmail API error: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"❌ Error sending email: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False
