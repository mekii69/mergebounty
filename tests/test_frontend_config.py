"""Frontend network-consistency tests for MergeBounty.

The checked-in frontend must target ONE network: the GenLayer Studio
network (chain 61999) where the contract is deployed. These tests pin
the client chain, contract address, explorer, RPC, and fee profile to
that network, and fail if any of them drifts to another network
(e.g. Bradbury, chain 4221).

Plain pytest — no GenVM fixtures needed.
"""

import glob
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ADDRESS = "0xf85c6Db3A886De786BB69078555A653b10254e99"
EXPLORER_URL = "https://explorer-studio.genlayer.com"
RPC_URL = "https://studio.genlayer.com/api"
CHAIN_ID = 61999


def _read(relpath: str) -> str:
    return (ROOT / relpath).read_text(encoding="utf-8")


def test_config_targets_studio():
    config = _read("frontend/src/config.js")
    assert f'"{CONTRACT_ADDRESS}"' in config
    assert f'"{EXPLORER_URL}"' in config
    assert f'"{RPC_URL}"' in config
    assert re.search(r"CHAIN_ID\s*=\s*61999", config) is not None


def test_fee_profile_targets_studio():
    profile = json.loads(_read("frontend/src/fee-profile.json"))
    assert profile["chainId"] == CHAIN_ID
    assert profile["network"] == "studio"


def test_main_uses_studionet_chain():
    main = _read("frontend/src/main.js")
    assert "studionet" in main
    assert "testnetBradbury" not in main
    assert "4221" not in main
    assert "rpc-bradbury" not in main
    assert "explorer-bradbury" not in main
    assert "Bradbury" not in main
    # The wallet chain-switch must enforce the configured chain, using the
    # configured RPC + explorer — never hardcoded values from another net.
    assert "CHAIN_ID" in main
    assert "RPC_URL" in main
    assert "EXPLORER_URL" in main


def test_create_bounty_passes_worker():
    main = _read("frontend/src/main.js")
    assert 'args: [title, criteria, worker]' in main
    assert "f-worker" in main


def test_index_shell_targets_studio():
    html = _read("frontend/index.html")
    assert "61999" in html
    assert "4221" not in html
    assert "Bradbury" not in html
    assert 'id="f-worker"' in html


def test_built_bundle_targets_studio():
    assets = glob.glob(str(ROOT / "frontend" / "dist" / "assets" / "*.js"))
    assert assets, "checked-in frontend/dist bundle is missing"
    bundle = "".join(Path(a).read_text(encoding="utf-8", errors="ignore") for a in assets)
    assert CONTRACT_ADDRESS in bundle
    assert "explorer-studio.genlayer.com" in bundle
