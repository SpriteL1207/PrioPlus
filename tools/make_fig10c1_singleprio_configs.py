#!/usr/bin/env python3
import copy
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_CONFIG = ROOT / "config/prioplus-eurosys25/experiments/fig10c1.json"
OUT_DIR = ROOT / "config/prioplus-eurosys25/experiments/fig10c1-singleprio"
FLOW_COUNTS = [2, 4, 6, 8, 10]


def main():
    with BASE_CONFIG.open() as f:
        base = json.load(f)

    sender_apps = [
        app
        for app in base["applicationConfig"]
        if app.get("applicationConfig", {}).get("SendEnabled", False)
    ]
    receiver_apps = [
        app
        for app in base["applicationConfig"]
        if not app.get("applicationConfig", {}).get("SendEnabled", True)
    ]
    if not sender_apps or not receiver_apps:
        raise RuntimeError("Cannot find sender and receiver applications in fig10c1.json")

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    for flow_count in FLOW_COUNTS:
        conf = copy.deepcopy(base)
        sender = copy.deepcopy(sender_apps[0])
        receiver = copy.deepcopy(receiver_apps[0])

        sender["NOTE"] = f"Single priority {flow_count} flows"
        sender["nodes"] = f"[0:{flow_count}]"
        sender.setdefault("socketConfig", {})["InnerPriority"] = 0

        cc = sender.setdefault("congestionConfig", {})
        cc["DynamicTarget"] = True
        cc.setdefault("ChannelWidthBytes", "50KB")
        cc.setdefault("ChannelTargetWaterline", 0.4)
        cc.setdefault("ChannelShim", "5KB")
        cc.setdefault("PriorityNum", 8)
        cc.setdefault("PriorityIndex", 6)

        conf["applicationConfig"] = [sender, receiver]
        conf["outputFile"]["resultFile"] = "output/*.json"

        out_path = OUT_DIR / f"flow{flow_count}.json"
        with out_path.open("w") as f:
            json.dump(conf, f, indent=4)
            f.write("\n")
        print(out_path)


if __name__ == "__main__":
    main()
