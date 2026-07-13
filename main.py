import asyncio
import aiohttp
import sys
import json
import re
import phonenumbers

# টার্মিনাল UTF-8 ফিক্স
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# ==================== আপনার তথ্য ====================
BOT_TOKEN = "8865186253:AAHZy2bd44y0ntk4p8XEvU9IGw7o1ZuZqdk"
GROUP_CHAT_ID = "-1003903265566"

API_KEY = "MURAD_1A19846FEA646F45D8EE07B6"
OTP_API_URL = "https://2eee7.com/@Access/@Bot/2eee7/@public/api/success-otp-info"

REFRESH_INTERVAL = 5  # ১ সেকেন্ড পর পর চেক করবে
seen_otps = set()

# ==================== হেল্পার ফাংশন ====================
def get_country_info(phone: str) -> tuple:
    """ফোন নম্বর থেকে দেশের ফ্লাগ ও কোড"""
    try:
        clean_num = str(phone).upper().replace('X', '0').replace('*', '0').replace('-', '').replace(' ', '')
        if not clean_num.startswith('+'):
            clean_num = '+' + clean_num
        parsed_num = phonenumbers.parse(clean_num, None)
        region = phonenumbers.region_code_for_number(parsed_num)
        if region:
            flag = "".join(chr(ord(c) + 127397) for c in region)
            return flag, region
    except Exception:
        pass
    return "🌍", "GLOBAL"

def mask_number(phone: str) -> str:
    """পুরো নাম্বার থেকে প্রথম ৩ + FASTX + শেষ ৩ (যদি ৬ ডিজিটের কম হয় তাহলে পুরোটাই FASTX দিয়ে মাস্ক)"""
    digits = re.sub(r'\D', '', str(phone))
    if len(digits) >= 6:
        return f"{digits[:3]}FASTX{digits[-3:]}"
    elif len(digits) > 3:
        return f"{digits[:3]}FASTX"
    return f"FASTX{digits}"

def format_otp_message(number: str, platform: str) -> str:
    """
    বক্স ডিজাইন:
    প্রথম লাইনে ফ্লাগ + দেশ → প্লাটফর্ম → [ মাস্কড নাম্বার ]
    """
    flag, country_short = get_country_info(number)
    platform_short = platform[:2].upper() if len(platform) >= 2 else platform.upper()
    masked = mask_number(number)  # 447FASTX228

    # বক্সের মধ্যের লেখা
    line = f"{flag} {country_short}➔{platform_short}➔[ {masked} ]"

    top = "┏━━━━━━━━━━━━━━━━━━━━━━━┓"
    mid = f"┃ {line} ┃"
    bot = "┗━━━━━━━━━━━━━━━━━━━━━━━┛"
    powered = "\n\n🕋 **𝙿𝙾𝚆𝙴𝚁𝙴𝙳 𝙱𝚈 [𝗙𝗔𝗦𝗧𝗫]** 🕋"
    return f"{top}\n{mid}\n{bot}{powered}"

async def send_telegram_message(session, text: str, otp_code: str):
    """টেলিগ্রামে মেসেজ পাঠানো + কপি বাটন"""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"

    keyboard = [
        [{"text": f" {otp_code}", "copy_text": {"text": otp_code}, "style": "success"}],
        [
            {"text": "‼️ 𝗣𝗔𝗡𝗘𝗟", "url": "https://t.me/fastx01_bot", "style": "danger"},
            {"text": "📞 𝗖𝗛𝗔𝗡𝗔𝗟", "url": "https://t.me/methodchannal2", "style": "primary"}
        ]
    ]

    payload = {
        "chat_id": GROUP_CHAT_ID,
        "text": text,
        "parse_mode": "Markdown",
        "reply_markup": json.dumps({"inline_keyboard": keyboard}),
        "disable_web_page_preview": True
    }

    for attempt in range(3):
        try:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    return True
                elif resp.status == 429:
                    await asyncio.sleep(5 * (attempt + 1))
                else:
                    await asyncio.sleep(2)
        except Exception as e:
            print(f"❌ পাঠাতে সমস্যা: {e}")
            await asyncio.sleep(2)
    return False

async def fetch_and_send_otps(session):
    """প্যানেল থেকে ওটিপি এনে গ্রুপে পাঠানো"""
    global seen_otps
    headers = {"X-API-Key": API_KEY, "Accept": "application/json"}

    try:
        async with session.get(OTP_API_URL, headers=headers, timeout=15) as resp:
            if resp.status == 200:
                data = await resp.json()
                if data.get("meta", {}).get("status") == "ok":
                    otps = data.get("data", {}).get("otps", [])
                    if not otps:
                        return

                    new_count = 0
                    for item in otps:
                        number = item.get("number")
                        otp = item.get("otp")
                        platform = item.get("platform", "Unknown")

                        if not number or not otp:
                            continue

                        unique_key = (number, otp)
                        if unique_key in seen_otps:
                            continue
                        seen_otps.add(unique_key)

                        msg = format_otp_message(number, platform)
                        await send_telegram_message(session, msg, otp)
                        await asyncio.sleep(0.5)  # স্প্যাম কমাতে সামান্য বিরতি
                        new_count += 1

                    if new_count:
                        print(f"📱 {new_count} টি নতুন ওটিপি পাঠানো হয়েছে।")
                else:
                    print("⚠️ OTP API status 'ok' নয়")
            else:
                print(f"⚠️ OTP HTTP {resp.status}")
    except Exception as e:
        print(f"❌ OTP fetch error: {e}")

# ==================== মেইন ====================
async def main():
    print("🤖 OTP ফরওয়ার্ডার (মাস্কড নাম্বার + ১ সেকেন্ড চেক) চালু হচ্ছে...\n")
    connector = aiohttp.TCPConnector(ssl=False)
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            await fetch_and_send_otps(session)
            await asyncio.sleep(REFRESH_INTERVAL)  # ১ সেকেন্ড

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 বন্ধ")
