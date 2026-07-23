#!/usr/bin/env python3
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "config/prioplus-eurosys25/experiments/fig10c1.json"
OUT_DIR = ROOT / "config/prioplus-eurosys25/experiments/fig10c1-overlap-debug"


def sender_apps(config):
    return [
        app
        for app in config["applicationConfig"]
        if app.get("applicationConfig", {}).get("SendEnabled", False)
    ]


def apply_channel(app, channel_low, linear_start):
    cc = app.setdefault("congestionConfig", {})
    cc["DynamicTarget"] = True
    cc["ChannelLowBytes"] = channel_low
    cc["ChannelWidthBytes"] = "100KB"
    cc["ChannelTargetWaterline"] = 0.5
    cc["ChannelShim"] = "0KB"
    cc["StartRateRatio"] = linear_start
    cc["RateLinearStart"] = linear_start


def write_config(base, name, linear_start):
    config = copy.deepcopy(base)
    senders = sender_apps(config)
    if len(senders) != 2:
        raise RuntimeError("fig10c1 overlap debug expects exactly two sender applications")

    apply_channel(senders[0], "80KB", linear_start)
    apply_channel(senders[1], "280KB", linear_start)

    out_path = OUT_DIR / f"{name}.json"
    with out_path.open("w") as f:
        json.dump(config, f, indent=4)
        f.write("\n")
    print(out_path)


def main():
    with BASE_CONFIG.open() as f:
        base = json.load(f)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    write_config(base, "wide-default", 0.125)
    write_config(base, "wide-linear005", 0.05)


if __name__ == "__main__":
    main()
