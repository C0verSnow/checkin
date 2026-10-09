"""Browser setup shared by the Douyin login tools."""

import argparse
import importlib
import math


def ensure_cloakbrowser():
    return importlib.import_module("cloakbrowser")


def positive_seconds(value):
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError("秒数必须是大于 0 的有限数字") from None
    if not math.isfinite(seconds) or seconds <= 0:
        raise argparse.ArgumentTypeError("秒数必须是大于 0 的有限数字")
    return seconds
