import os
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

# Twilio WhatsApp configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_FROM = os.getenv("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")  # Twilio sandbox number
ADMIN_WHATSAPP_NUMBERS = [
    os.getenv("ADMIN_WHATSAPP_1", "whatsapp:+201234567890"),  # Replace with your number
    os.getenv("ADMIN_WHATSAPP_2", "whatsapp:+201234567890")   # Replace with second admin number
]


async def send_order_notification(order_data: dict):
    """
    Send order notification via WhatsApp using Twilio
    Much easier than email - no verification needed!
    """
    if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
        print("⚠️ Warning: Twilio credentials not configured. WhatsApp message not sent.")
        return False
    
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Calculate total
        total = sum(item['quantity'] * item['price'] for item in order_data['items'])
        
        # Create WhatsApp message
        message_text = f"""🛒 *NEW ORDER RECEIVED!*

📋 *Order ID:* #{order_data['order_id']}

👤 *Customer Info:*
• Name: {order_data['customer_name']}
• Email: {order_data['customer_email']}
• Phone: {order_data['customer_phone']}
• City: {order_data.get('customer_city', 'N/A')}
• Address: {order_data['customer_address']}

📦 *Order Items:*
"""
        
        for item in order_data['items']:
            subtotal = item['quantity'] * item['price']
            message_text += f"• {item['product_name']}\n  Qty: {item['quantity']} × {item['price']} EGP = {subtotal} EGP\n"
        
        message_text += f"\n💰 *Total: {total} EGP*"
        
        print(f"🔄 Sending WhatsApp notifications to {len(ADMIN_WHATSAPP_NUMBERS)} admin(s)")
        
        # Send to all admin WhatsApp numbers
        success_count = 0
        for admin_number in ADMIN_WHATSAPP_NUMBERS:
            try:
                message = client.messages.create(
                    from_=TWILIO_WHATSAPP_FROM,
                    body=message_text,
                    to=admin_number
                )
                print(f"✅ WhatsApp sent to {admin_number}: {message.sid}")
                success_count += 1
            except Exception as e:
                print(f"❌ Failed to send to {admin_number}: {e}")
        
        if success_count > 0:
            print(f"✅ WhatsApp notifications sent to {success_count}/{len(ADMIN_WHATSAPP_NUMBERS)} admin(s)")
            return True
        else:
            print("❌ Failed to send WhatsApp to any admin")
            return False
        
    except Exception as e:
        print(f"❌ Error sending WhatsApp: {type(e).__name__}: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return False
