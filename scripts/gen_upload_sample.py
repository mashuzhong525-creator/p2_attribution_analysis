# -*- coding: utf-8 -*-
"""生成"上传数据分析"用的样例 CSV（商品经营日报，埋归因故事）。

故事线（供上传后做归因分析验证）：
- 2026-06-15 起「信息流」渠道素材疲劳：曝光持续放量，但点击不涨 → CTR 从 ~2.6% 掉到 ~1.3%；
- 信息流是 GMV 主力渠道，其转化下滑直接拖垮整体 GMV（日均 ~55 万 → ~36 万）；
- 运营误判为流量不足，6/15 后反而给信息流加投广告（ad_spend 上升），ROAS 从 ~4.2 恶化到 ~2.3；
- 「搜索」渠道全程稳定（自然流量基本盘），「直播」渠道缓慢增长，可作对照组。

用法：python scripts/gen_upload_sample.py [输出路径]
默认输出到桌面 gmv_daily_sample.csv，UTF-8 带 BOM（Excel 直开不乱码）。
"""
from __future__ import annotations

import random
import sys
from datetime import date, timedelta
from pathlib import Path

random.seed(42)

START = date(2026, 6, 1)
DAYS = 60          # 6/1 ~ 7/30
FATIGUE_FROM = 15  # 6/15 起信息流素材疲劳

CHANNELS = ["信息流", "搜索", "直播"]


def round2(x: float) -> float:
    return round(x + random.uniform(-0.05, 0.05), 2)


def one_day(day_idx: int) -> list[list]:
    """返回某天 3 个渠道的行。"""
    d = START + timedelta(days=day_idx)
    rows = []
    for ch in CHANNELS:
        if ch == "信息流":
            imp = int(600_000 * (1 + day_idx * 0.004) * random.uniform(0.95, 1.05))
            if day_idx < FATIGUE_FROM:
                ctr = random.uniform(0.024, 0.028)          # 素材新鲜期 CTR ~2.6%
                spend = int(80_000 * random.uniform(0.9, 1.1))
            else:
                decay = 1 - min((day_idx - FATIGUE_FROM) * 0.018, 0.55)
                ctr = random.uniform(0.024, 0.028) * decay  # 疲劳后逐步掉到 ~1.3%
                spend = int(100_000 * random.uniform(0.9, 1.1))  # 误判加投
            clicks = int(imp * ctr)
            cvr = random.uniform(0.030, 0.036) * (1 if day_idx < FATIGUE_FROM else 0.92)
            orders = int(clicks * cvr)
            aov = round(random.uniform(168, 185) if day_idx < FATIGUE_FROM
                        else random.uniform(140, 150), 1)  # 疲劳期促销降价，客单价同步走低
        elif ch == "搜索":
            imp = int(150_000 * random.uniform(0.96, 1.04))
            ctr = random.uniform(0.055, 0.062)              # 稳定
            clicks = int(imp * ctr)
            cvr = random.uniform(0.048, 0.055)
            orders = int(clicks * cvr)
            aov = round(random.uniform(150, 162), 1)
            spend = int(12_000 * random.uniform(0.9, 1.1))
        else:  # 直播
            imp = int(90_000 * (1 + day_idx * 0.006) * random.uniform(0.95, 1.05))
            ctr = random.uniform(0.032, 0.038)
            clicks = int(imp * ctr)
            cvr = random.uniform(0.060, 0.070)
            orders = int(clicks * cvr)
            aov = round(random.uniform(120, 132), 1)
            spend = int(9_000 * random.uniform(0.9, 1.1))
        gmv = round(orders * aov, 2)
        roas = round2(gmv / spend) if spend else 0.0
        rows.append([
            d.isoformat(), ch, imp, clicks, f"{clicks / imp:.4f}",
            orders, gmv, spend, roas,
        ])
    return rows


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.home() / "Desktop" / "gmv_daily_sample.csv"
    header = ["date", "channel", "impressions", "clicks", "ctr",
              "orders", "gmv", "ad_spend", "roas"]
    lines = [",".join(header)]
    for i in range(DAYS):
        for r in one_day(i):
            lines.append(",".join(str(x) for x in r))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8-sig")

    # 简单自检：分阶段日均 GMV / 信息流 CTR，确认故事线成立
    def phase_stat(lo: int, hi: int) -> tuple[float, float]:
        gmv_sum = ctr_sum = feed_days = 0
        for i in range(lo, hi):
            for r in one_day(i):
                if r[1] == "信息流":
                    ctr_sum += float(r[4]); feed_days += 1
                gmv_sum += r[6]
        n_days = hi - lo
        return gmv_sum / n_days, ctr_sum / feed_days

    g1, c1 = phase_stat(0, FATIGUE_FROM)
    g2, c2 = phase_stat(FATIGUE_FROM, DAYS)
    print(f"OK -> {out}  ({DAYS} 天 x {len(CHANNELS)} 渠道 = {DAYS * len(CHANNELS)} 行)")
    print(f"素材疲劳前: 日均GMV≈{g1/10000:.1f}万, 信息流CTR≈{c1:.2%}")
    print(f"素材疲劳后: 日均GMV≈{g2/10000:.1f}万, 信息流CTR≈{c2:.2%}")
    print(f"GMV 跌幅≈{(1 - g2/g1):.0%}, CTR 跌幅≈{(1 - c2/c1):.0%}")


if __name__ == "__main__":
    main()
