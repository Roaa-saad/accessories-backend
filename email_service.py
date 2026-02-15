import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv

load_dotenv()

# Email configuration - using Gmail SMTP
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USERNAME = os.getenv("SMTP_USERNAME")  # Your Gmail address
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")  # App password
ADMIN_EMAIL = "roaam5182@gmail.com"


async def send_order_notification(order_data: dict):
    """
    Send order notification email to admin
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print("Warning: SMTP credentials not configured. Email not sent.")
        return False
    
    try:
        # Create email message
        message = MIMEMultipart("alternative")
        message["From"] = SMTP_USERNAME
        message["To"] = ADMIN_EMAIL
        message["Subject"] = f"🛒 New Order #{order_data['order_id']} - {order_data['customer_name']}"
        
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
        
        # Attach HTML content
        message.attach(MIMEText(html, "html"))
        
        # Send email
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            username=SMTP_USERNAME,
            password=SMTP_PASSWORD,
            start_tls=True
        )
        
        print(f"✅ Order notification email sent to {ADMIN_EMAIL}")
        return True
        
    except Exception as e:
        print(f"❌ Error sending email: {e}")
        return False
