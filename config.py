import os
def _env(k, d=""):
    return os.environ.get(k, d).strip()
# simple .env loader
if os.path.exists(".env"):
    for line in open(".env", encoding="utf-8"):
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)
BOT_TOKEN = _env("BOT_TOKEN")
ADMIN_IDS = {int(x) for x in _env("ADMIN_IDS").split(",") if x.strip()}
CHANNEL_ID = int(_env("CHANNEL_ID", "-1004399158909"))
OWNER_TAG = _env("OWNER_TAG", "@Smart_Method_Owner")
UTC_OFFSET = int(_env("UTC_OFFSET", "6"))
API_URL = "https://nexusairafipj.base44.app/functions/oandaData"
PAIRS = "AUDCAD,AUDCHF,AUDJPY,AUDUSD,CADJPY,CHFJPY,EURAUD,EURCAD,EURCHF,EURGBP,EURJPY,GBPAUD,GBPCAD,GBPCHF,GBPJPY,GBPUSD,USDCAD,USDCHF,USDJPY,EURUSD".split(",")
MIN_PAYOUT = 80
DAILY_LIMIT = 5
AUTO_INTERVAL_MIN = 5   # channel auto signal every N minutes
