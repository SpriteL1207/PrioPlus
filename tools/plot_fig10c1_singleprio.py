#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


RATE_WINDOW_NS = 100_000
LINK_RATE_BPS = 100e9


def to_ms(time_ns, origin_ns):
    return (time_ns - origin_ns) / 1e6


def flow_rate_series(flow, origin_ns):
    pkts = flow.get("sentPkt", [])
    if not pkts:
        return [], []

    start = pkts[0]["timeNs"]
    end = pkts[-1]["timeNs"]
    pkt_idx = 0
    xs = []
    ys = []

    wnd_start = start
    while wnd_start <= end:
        wnd_end = wnd_start + RATE_WINDOW_NS
        wnd_bytes = 0
        while pkt_idx < len(pkts) and pkts[pkt_idx]["timeNs"] <= wnd_end:
            wnd_bytes += pkts[pkt_idx]["sizeByte"]
            pkt_idx += 1

        xs.append(to_ms(wnd_start + RATE_WINDOW_NS / 2, origin_ns))
        ys.append(wnd_bytes * 8 / RATE_WINDOW_NS)
        wnd_start = wnd_end

    return xs, ys


def cc_series(flow, name, value_key, origin_ns, scale=1.0):
    series = flow.get("ccStats", {}).get(name, [])
    xs = [to_ms(p["timeNs"], origin_ns) for p in series if value_key in p]
    ys = [p[value_key] * scale for p in series if value_key in p]
    return xs, ys


def cwnd_series(flow, origin_ns):
    series = flow.get("ccCwnd", [])
    if series:
        xs = [to_ms(p["timeNs"], origin_ns) for p in series]
        ys = [p["cwndByte"] / 1024 for p in series]
        return xs, ys

    series = flow.get("ccStats", {}).get("completeStats", [])
    xs = [to_ms(p["timeNs"], origin_ns) for p in series if "cwnd" in p]
    ys = [p["cwnd"] / 1024 for p in series if "cwnd" in p]
    return xs, ys


def queue_series(data, origin_ns):
    best = []
    for sw in data.get("switchStatistics", []):
        for port in sw.get("portStats", []):
            for queue in port.get("queueStats", []):
                q = queue.get("qLength", [])
                if len(q) > len(best):
                    best = q
    xs = [to_ms(p["timeNs"], origin_ns) for p in best]
    ys = [p["lengthBytes"] / 1024 for p in best]
    return xs, ys


def target_delay_to_kb(target_delay_ns, base_delay_ns):
    queue_delay_ns = max(0.0, target_delay_ns - base_delay_ns)
    return queue_delay_ns * 1e-9 * LINK_RATE_BPS / 8 / 1024


def infer_base_delay_ns(data):
    links = data.get("config", {}).get("topologyConfig", {}).get("linkConfig", [])
    if not links:
        return 0.0
    delay = links[0].get("delay", "0us")
    if delay.endswith("us"):
        return float(delay[:-2]) * 1000
    if delay.endswith("ns"):
        return float(delay[:-2])
    if delay.endswith("ms"):
        return float(delay[:-2]) * 1_000_000
    return 0.0


def plot_one(json_path, out_dir):
    with open(json_path) as f:
        data = json.load(f)

    flows = data["flowStatistics"]
    origin_ns = min(flow["sentPkt"][0]["timeNs"] for flow in flows if flow.get("sentPkt"))
    base_delay_ns = infer_base_delay_ns(data)

    fig, axes = plt.subplots(5, 1, figsize=(7.2, 9.2), sharex=True)
    colors = plt.cm.tab10.colors

    for idx, flow in enumerate(flows):
        label = f"flow {idx}"
        color = colors[idx % len(colors)]

        xs, ys = flow_rate_series(flow, origin_ns)
        axes[0].plot(xs, ys, label=label, color=color, linewidth=1.2)

        xs, ys = cc_series(flow, "completeStats", "delayNs", origin_ns, scale=1 / 1000)
        axes[2].plot(xs, ys, label=label, color=color, linewidth=1.0)

        xs, ys = cwnd_series(flow, origin_ns)
        axes[3].plot(xs, ys, label=label, color=color, linewidth=1.0)

        target = flow.get("ccStats", {}).get("targetDelay", [])
        xs = [to_ms(p["timeNs"], origin_ns) for p in target]
        ys = [target_delay_to_kb(p["targetDelayNs"], base_delay_ns) for p in target]
        axes[4].plot(xs, ys, label=label, color=color, linewidth=1.0)

    xs, ys = queue_series(data, origin_ns)
    axes[1].plot(xs, ys, color="#4E342E", linewidth=1.3)

    axes[0].set_ylabel("Rate\n(Gbps)")
    axes[1].set_ylabel("Queue\n(KB)")
    axes[2].set_ylabel("Delay\n(us)")
    axes[3].set_ylabel("Cwnd\n(KB)")
    axes[4].set_ylabel("Target\n(KB)")
    axes[4].set_xlabel("Time (ms)")

    for ax in axes:
        ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.6)
        ax.set_xlim(0, 3)

    axes[0].set_ylim(bottom=0)
    axes[1].set_ylim(bottom=0)
    axes[2].set_ylim(bottom=0)
    axes[3].set_ylim(bottom=0)
    axes[4].set_ylim(bottom=0)
    axes[0].legend(ncol=min(5, max(1, len(flows))), fontsize=8, frameon=False)

    title = Path(json_path).stem
    fig.suptitle(f"fig10c1 single priority - {title}", y=0.995)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{title}.png"
    fig.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(out_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="+", help="Result JSON file(s) or directories")
    parser.add_argument("--out-dir", default="output/figures/fig10c1-singleprio")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    json_paths = []
    for p in args.paths:
        path = Path(p)
        if path.is_dir():
            json_paths.extend(sorted(path.glob("*.json")))
        else:
            json_paths.append(path)

    for path in json_paths:
        plot_one(path, out_dir)


if __name__ == "__main__":
    main()
