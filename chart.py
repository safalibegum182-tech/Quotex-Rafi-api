import io, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from market import ema, fmt

def candle_chart(pair, candles, direction=None, n=40):
    cs = candles[-n:]
    fig, ax = plt.subplots(figsize=(9, 5), dpi=110)
    fig.patch.set_facecolor("#0d1117"); ax.set_facecolor("#0d1117")
    for i, c in enumerate(cs):
        col = "#26a69a" if c["close"] >= c["open"] else "#ef5350"
        ax.plot([i, i], [c["low"], c["high"]], color=col, lw=1)
        ax.bar(i, abs(c["close"] - c["open"]) or 1e-6, bottom=min(c["open"], c["close"]), color=col, width=0.6)
    closes = [c["close"] for c in candles]
    for n_, col in ((9, "#ffd54f"), (21, "#42a5f5")):
        e = ema(closes, n_)[-len(cs):]
        ax.plot(range(len(cs)), e, color=col, lw=1.2, label=f"EMA{n_}")
    if direction:
        y = cs[-1]["close"]
        ax.annotate("CALL ▲" if direction == "CALL" else "PUT ▼", xy=(len(cs) - 1, y),
                    xytext=(len(cs) - 12, max(c["high"] for c in cs)), color="#26a69a" if direction == "CALL" else "#ef5350",
                    fontsize=14, weight="bold", arrowprops=dict(arrowstyle="->", color="white"))
    ax.set_title(f"{fmt(pair)}  M1  ·  CB SIGNALS PRO", color="white")
    ax.tick_params(colors="#8b949e"); ax.legend(facecolor="#161b22", labelcolor="white")
    for s in ax.spines.values(): s.set_color("#30363d")
    ax.set_xticks([])
    buf = io.BytesIO(); fig.tight_layout(); fig.savefig(buf, format="png"); plt.close(fig)
    buf.seek(0); return buf
