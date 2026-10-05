import asyncio, datetime as dt, json, os, random
from telegram import Update, InlineKeyboardButton as B, InlineKeyboardMarkup as M
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from config import *
from market import get_candles, analyze, fmt
from chart import candle_chart

STATE_FILE = "state.json"
state = {"auto": False, "usage": {}, "stats": {"win": 0, "loss": 0}}
if os.path.exists(STATE_FILE): state.update(json.load(open(STATE_FILE)))
def save(): json.dump(state, open(STATE_FILE, "w"))

TZ = dt.timezone(dt.timedelta(hours=UTC_OFFSET))
HDR = f"⏰ TF: M1  |  UTC: +{UTC_OFFSET}  |  MTG: No MTG"
def now(): return dt.datetime.now(TZ)
def is_admin(u): return u in ADMIN_IDS

def main_kb(uid):
    rows = [[B("📊 Analysis", callback_data="analysis")],
            [B("🔮 Future Signals", callback_data="future")],
            [B("📈 Stats", callback_data="stats")]]
    if is_admin(uid): rows.append([B("🛠 Admin Dashboard", callback_data="admin")])
    return M(rows)

async def start(u: Update, c: ContextTypes.DEFAULT_TYPE):
    await u.message.reply_text(
        f"✨ Welcome to CB SIGNALS PRO PREMIUM ✨\n\nHi {u.effective_user.first_name}! 👋\n"
        "Live M1 market analysis with chart-based signals.\nUse the buttons below 👇",
        reply_markup=main_kb(u.effective_user.id))

async def scan(min_payout=MIN_PAYOUT):
    async def one(p):
        try:
            cs = await get_candles(p, 300); a = analyze(cs)
            return (p, cs, a) if a else None
        except Exception: return None
    res = [r for r in await asyncio.gather(*(one(p) for p in PAIRS)) if r]
    res = [r for r in res if r[2]["payout"] >= min_payout]
    res.sort(key=lambda r: r[2]["payout"], reverse=True)
    return res

def signal_text(pair, a, entry):
    return (f"✨ CB SIGNALS PRO PREMIUM ✨\n\n🕯️ Asset: {fmt(pair)}\n📊 Trend: {a['trend']}\n"
            f"🎯 Signal: {'🟢 CALL' if a['direction']=='CALL' else '🔴 PUT'}\n"
            f"📈 Confluence: {a['score']}%  (RSI {a['rsi']})\n⏳ Timeframe: M1\n"
            f"⏰ Entry Time: {entry:%H:%M}\n👑 MTG: Disabled\n👤 Owner: {OWNER_TAG}\n\n"
            f"💡 Analysis: EMA 9/21/50 trend alignment + RSI + last-candle momentum on {fmt(pair)} "
            f"point to {a['direction']}.\n\n⚠️ Not financial advice. Trade at your own risk.")

async def send_signal(bot, chat_id, pair, cs, a, job_queue):
    entry = (now() + dt.timedelta(minutes=1)).replace(second=0, microsecond=0)
    await bot.send_photo(chat_id, candle_chart(pair, cs, a["direction"]), caption=signal_text(pair, a, entry))
    delay = (entry + dt.timedelta(minutes=1, seconds=8) - now()).total_seconds()
    job_queue.run_once(check_result, delay, data={"chat": chat_id, "pair": pair, "dir": a["direction"], "entry": entry.isoformat()})

async def check_result(c: ContextTypes.DEFAULT_TYPE):
    d = c.job.data; entry = dt.datetime.fromisoformat(d["entry"])
    cs = await get_candles(d["pair"], 10)
    ep = int(entry.timestamp()); cnd = next((x for x in cs if x["epoch"] == ep), None)
    if not cnd:
        await c.bot.send_message(d["chat"], f"❓ Result unavailable for {fmt(d['pair'])} {entry:%H:%M}"); return
    o, cl = cnd["open"], cnd["close"]
    win = cl > o if d["dir"] == "CALL" else cl < o
    if cl == o: res = "⚪ DRAW ⚪"
    else:
        res = "🔥 WIN 🔥" if win else "❌ LOSS ❌"
        state["stats"]["win" if win else "loss"] += 1; save()
    await c.bot.send_message(d["chat"],
        f"❓ TRADE RESULT\n\n🕯️ Asset: {fmt(d['pair'])}\n🎯 Signal: {'🟢 CALL' if d['dir']=='CALL' else '🔴 PUT'}\n"
        f"⏰ Entry Time: {entry:%H:%M}\n\n{res}\n\n📉 Entry: {o}\n📈 Exit: {cl}\n\n✨ CB SIGNALS PRO ✨")

async def auto_job(c: ContextTypes.DEFAULT_TYPE):
    if not state["auto"]: return
    res = await scan()
    if not res: return
    best = max(res, key=lambda r: (r[2]["score"], r[2]["payout"]))
    await send_signal(c.bot, CHANNEL_ID, *best, c.job_queue)

async def on_btn(u: Update, c: ContextTypes.DEFAULT_TYPE):
    q = u.callback_query; await q.answer(); uid = q.from_user.id; d = q.data
    back = [B("⬅️ Back", callback_data="home")]
    if d == "home":
        await q.edit_message_text("🏠 Main Menu", reply_markup=main_kb(uid))
    elif d == "analysis":
        await q.edit_message_text(f"🌐 Select Market Type\n{HDR}\n\nPick a market · live analysis generates your signal instantly.",
            reply_markup=M([[B("🌙 OTC Market", callback_data="otc"), B("🌍 Live Market", callback_data="live")], back]))
    elif d == "otc":
        await q.edit_message_text("🌙 OTC Market\n\nNo OTC price feed is connected, so OTC signals are not available. Use 🌍 Live Market.",
            reply_markup=M([[B("🌍 Live Market", callback_data="live")], back]))
    elif d == "live":
        await q.edit_message_text(f"🌐 Select Analysis Mode (Live)\n{HDR}\n\n⚡ Auto Detect #1 Pair:\nScans all {MIN_PAYOUT}%+ payout pairs and picks the strongest confluence.\n\n🎯 Select Manual Pair:\nPairs ordered from highest to lowest payout.",
            reply_markup=M([[B("⚡ Auto Detect", callback_data="auto"), B("🎯 Select Manually", callback_data="manual")], back]))
    elif d in ("auto", "manual"):
        await q.edit_message_text("⏳ Fetching live payouts...")
        res = await scan(); c.user_data["scan"] = res
        if not res:
            await q.edit_message_text("No pairs with 80%+ payout right now.", reply_markup=M([back])); return
        lst = "\n".join(f"{i+1}. {fmt(p)} ({a['payout']}%)" for i, (p, _, a) in enumerate(res))
        if d == "auto":
            await q.edit_message_text(f"⚡ Confirm Auto Detect (#1 Pair)\n\n{len(res)} market(s) detected ({MIN_PAYOUT}%+ payout)\n\n{lst}\n\n❓ Continue to Analysis System?",
                reply_markup=M([[B("🚀 Generate", callback_data="gen:AUTO")], [B("⬅️ Back", callback_data="live")]]))
        else:
            kb = [[B(f"{fmt(p)} {a['payout']}%", callback_data=f"gen:{p}")] for p, _, a in res]
            await q.edit_message_text("🎯 Select a pair:", reply_markup=M(kb + [[B("⬅️ Back", callback_data="live")]]))
    elif d.startswith("gen:"):
        day = now().strftime("%Y-%m-%d"); key = f"{uid}:{day}"
        used = state["usage"].get(key, 0)
        if used >= DAILY_LIMIT and not is_admin(uid):
            await q.edit_message_text(f"⛔ Daily limit reached ({DAILY_LIMIT}/day).", reply_markup=M([back])); return
        res = c.user_data.get("scan") or await scan()
        pick = d[4:]
        if pick == "AUTO":
            await q.edit_message_text("🤖 Scanning high-payout assets...\n⏳ Analyzing candle cycles & momentum...")
            await asyncio.sleep(1.5)
            row = max(res, key=lambda r: (r[2]["score"], r[2]["payout"]))
        else:
            row = next((r for r in res if r[0] == pick), None)
            if not row: await q.edit_message_text("Pair unavailable.", reply_markup=M([back])); return
        state["usage"][key] = used + 1; save()
        await q.edit_message_text(f"🧠 Analyzing {fmt(row[0])}... ({used+1}/{DAILY_LIMIT})\n📊 {max(DAILY_LIMIT-used-1,0)} left · max {DAILY_LIMIT}/day")
        await send_signal(c.bot, q.message.chat_id, *row, c.job_queue)
    elif d == "future":
        await q.edit_message_text("🔮 Building future signal list...")
        res = await scan()
        res.sort(key=lambda r: r[2]["score"], reverse=True)
        t = now().replace(second=0, microsecond=0)
        lines = [f"{(t+dt.timedelta(minutes=3*(i+1))):%H:%M} • {fmt(p)} • {'🟢 CALL' if a['direction']=='CALL' else '🔴 PUT'}"
                 for i, (p, _, a) in enumerate(res[:8])]
        await q.edit_message_text(f"🔮 FUTURE SIGNALS (M1, UTC+{UTC_OFFSET})\n\n" + "\n".join(lines) +
            "\n\n⚠️ Based on the current trend; conditions can change before entry.", reply_markup=M([back]))
    elif d == "stats":
        s = state["stats"]; tot = s["win"] + s["loss"]
        wr = f"{s['win']*100/tot:.1f}%" if tot else "—"
        await q.edit_message_text(f"📈 Results\n\n🔥 Wins: {s['win']}\n❌ Losses: {s['loss']}\n🎯 Win rate: {wr}", reply_markup=M([back]))
    elif d in ("admin", "toggle", "testpost") and is_admin(uid):
        if d == "toggle": state["auto"] = not state["auto"]; save()
        if d == "testpost":
            res = await scan()
            if res: await send_signal(c.bot, CHANNEL_ID, *max(res, key=lambda r: r[2]["score"]), c.job_queue)
        await q.edit_message_text(f"🛠 Admin Dashboard\n\nChannel auto-post: {'🟢 ON' if state['auto'] else '🔴 OFF'}\nEvery {AUTO_INTERVAL_MIN} min · results posted automatically",
            reply_markup=M([[B("🔴 Turn OFF" if state["auto"] else "🟢 Turn ON", callback_data="toggle")],
                            [B("📤 Post one signal now", callback_data="testpost")], back]))

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(on_btn))
    app.job_queue.run_repeating(auto_job, interval=AUTO_INTERVAL_MIN * 60, first=10)
    print("Bot running..."); app.run_polling()

if __name__ == "__main__": main()
