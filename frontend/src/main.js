/**
 * MergeBounty frontend — GenLayer Bradbury testnet (chain 4221).
 *
 * Reads use a wallet-free genlayer-js client. Writes go through
 * @genlayer/transaction-kit: estimate -> verify fee policy -> submit ->
 * track to decided/finalized. The wallet (MetaMask) signs; the user
 * approves the fee quote + value in their wallet before anything is sent.
 *
 * Set CONTRACT_ADDRESS in src/config.js after deploying (see README).
 */
import { createClient } from "genlayer-js";
import { testnetBradbury } from "genlayer-js/chains";
import { createTransactionKit } from "@genlayer/transaction-kit";
import { CONTRACT_ADDRESS, EXPLORER_URL } from "./config.js";
import feeProfile from "./fee-profile.json";

const ZERO_ADDRESS = "0x0000000000000000000000000000000000000000";
const GEN_DECIMALS = 18n;

const $ = (id) => document.getElementById(id);
const logEl = $("log");
const bountyListEl = $("bounty-list");

function log(msg) {
  const line = `[${new Date().toLocaleTimeString()}] ${msg}`;
  logEl.textContent = logEl.textContent === "—" ? line : logEl.textContent + "\n" + line;
}

function toWei(genStr) {
  const [whole, frac = ""] = String(genStr).trim().split(".");
  const fracPadded = (frac + "0".repeat(18)).slice(0, 18);
  return BigInt(whole || "0") * 10n ** GEN_DECIMALS + BigInt(fracPadded || "0");
}

function fromWei(wei) {
  const w = BigInt(wei);
  const whole = w / 10n ** GEN_DECIMALS;
  const frac = (w % 10n ** GEN_DECIMALS).toString().padStart(18, "0").replace(/0+$/, "");
  return frac ? `${whole}.${frac}` : `${whole}`;
}

function shortAddr(addr) {
  return addr ? `${addr.slice(0, 6)}…${addr.slice(-4)}` : "—";
}

// Read-only client (no wallet needed).
const readClient = createClient({ chain: testnetBradbury });

let account = null; // checksummed address string once connected
let kit = null;

function getKit() {
  if (!window.ethereum) throw new Error("No injected wallet found (install MetaMask).");
  if (!account) throw new Error("Connect your wallet first.");
  if (!kit) {
    kit = createTransactionKit({
      chain: testnetBradbury,
      provider: window.ethereum,
      account,
      suggestions: feeProfile,
    });
  }
  return kit;
}

async function ensureBradbury() {
  const chainIdHex = await window.ethereum.request({ method: "eth_chainId" });
  if (parseInt(chainIdHex, 16) !== 4221) {
    await window.ethereum.request({
      method: "wallet_addEthereumChain",
      params: [
        {
          chainId: "0x107D",
          chainName: "GenLayer Bradbury Testnet",
          nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
          rpcUrls: ["https://rpc-bradbury.genlayer.com"],
          blockExplorerUrls: [EXPLORER_URL],
        },
      ],
    });
  }
}

async function connectWallet() {
  try {
    if (!window.ethereum) {
      $("wallet-status").textContent = "No injected wallet found. Install MetaMask to write.";
      return;
    }
    await ensureBradbury();
    const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
    account = accounts[0];
    kit = null; // rebuild the kit for this account
    const read = createClient({ chain: testnetBradbury });
    const balance = await read.getBalance({ address: account });
    $("wallet-status").textContent = `Connected on Bradbury (chain 4221).`;
    $("account-line").textContent = `${account} · balance ${fromWei(balance)} GEN`;
    $("connect-btn").textContent = "Connected";
    $("connect-btn").disabled = true;
    log(`Wallet connected: ${account}`);
    await refreshBounties();
  } catch (err) {
    log(`Connect failed: ${err?.message || err}`);
  }
}

/** Run a write through the kit: estimate, fail closed on fee mismatch, submit, track. */
async function writeViaKit(method, args, userValue = 0n) {
  const k = getKit();
  const tx = { kind: "write", address: CONTRACT_ADDRESS, method, args };
  const quote = await k.estimate({ preset: "standard", userValue }, tx);
  if (quote.verification.status === "mismatch") {
    throw new Error("Fee policy changed since the quote; re-estimate before signing.");
  }
  log(
    `${method}: fee ${fromWei(quote.feeValue)} GEN + value ${fromWei(quote.userValue)} GEN = total ${fromWei(quote.total)} GEN`
  );
  const { genlayerTxId } = await k.submit(quote, tx);
  log(`${method}: submitted, tx ${genlayerTxId}`);
  const final = await k.track(genlayerTxId, (s) => {
    log(`${method}: ${s.phase}${s.statusName ? ` (${s.statusName})` : ""}`);
  }, { until: "finalized" });
  if (final.successful === false) {
    throw new Error(`${method}: transaction finished unsuccessfully (${final.executionResultName || "unknown"})`);
  }
  return final;
}

async function readBounty(id) {
  const raw = await readClient.readContract({
    address: CONTRACT_ADDRESS,
    functionName: "get_bounty",
    args: [id],
  });
  return JSON.parse(raw);
}

function bountyCard(b) {
  const div = document.createElement("div");
  div.className = "card";
  const verdict = b.verdict ? JSON.parse(b.verdict) : null;
  div.innerHTML = `
    <div><span class="status ${b.status}">#${b.id} · ${b.status}</span> — <strong></strong></div>
    <p class="muted mono">client ${shortAddr(b.client)} · worker ${shortAddr(b.worker)} · locked ${fromWei(b.amount_wei)} GEN</p>
    <p><strong>Criteria:</strong> <span></span></p>
    <p><strong>Evidence:</strong> <span class="mono"></span></p>
    ${verdict ? `<p><strong>Verdict:</strong> met=${verdict.met} · confidence ${verdict.confidence} — <span></span></p>` : ""}
    <div class="actions"></div>
  `;
  div.querySelector("strong").textContent = b.title;
  div.querySelectorAll("p")[1].querySelector("span").textContent = b.criteria;
  div.querySelectorAll("p")[2].querySelector("span").textContent = b.evidence_url || "—";
  if (verdict) div.querySelectorAll("p")[3].querySelector("span").textContent = verdict.reason;
  const actions = div.querySelector(".actions");

  if (b.status === "FUNDED") {
    const urlInput = document.createElement("input");
    urlInput.placeholder = "Evidence URL (https://…), e.g. GitHub PR";
    urlInput.style.flex = "1";
    const btn = document.createElement("button");
    btn.textContent = "Submit evidence";
    btn.onclick = async () => {
      const url = urlInput.value.trim();
      if (!url.startsWith("https://")) return alert("Evidence URL must start with https://");
      btn.disabled = true;
      try {
        await writeViaKit("submit_evidence", [b.id, url]);
        log(`Evidence submitted for bounty #${b.id}`);
        await refreshBounties();
      } catch (err) {
        alert(err?.message || err);
        btn.disabled = false;
      }
    };
    actions.append(urlInput, btn);
    if (account && account.toLowerCase() === String(b.client).toLowerCase()) {
      const cancelBtn = document.createElement("button");
      cancelBtn.textContent = "Cancel bounty (refund)";
      cancelBtn.className = "secondary";
      cancelBtn.onclick = async () => {
        cancelBtn.disabled = true;
        try {
          await writeViaKit("cancel_bounty", [b.id]);
          log(`Bounty #${b.id} cancelled, refunded to client`);
          await refreshBounties();
        } catch (err) {
          alert(err?.message || err);
          cancelBtn.disabled = false;
        }
      };
      actions.append(cancelBtn);
    }
  }

  if (b.status === "EVIDENCE") {
    const btn = document.createElement("button");
    btn.textContent = "Resolve (fetch evidence + LLM verdict)";
    btn.onclick = async () => {
      btn.disabled = true;
      try {
        await writeViaKit("resolve_bounty", [b.id]);
        log(`Bounty #${b.id} resolved`);
        await refreshBounties();
      } catch (err) {
        alert(err?.message || err);
        btn.disabled = false;
      }
    };
    actions.append(btn);
  }

  const link = document.createElement("a");
  link.href = `${EXPLORER_URL}/address/${CONTRACT_ADDRESS}`;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = "View contract on explorer";
  link.className = "muted";
  actions.append(link);
  return div;
}

async function refreshBounties() {
  if (CONTRACT_ADDRESS === ZERO_ADDRESS) {
    $("config-warning").hidden = false;
    bountyListEl.innerHTML = `<p class="muted">Contract not deployed yet.</p>`;
    return;
  }
  $("config-warning").hidden = true;
  bountyListEl.innerHTML = `<p class="muted">Loading…</p>`;
  try {
    const count = Number(
      await readClient.readContract({
        address: CONTRACT_ADDRESS,
        functionName: "get_bounty_count",
        args: [],
      })
    );
    bountyListEl.innerHTML = "";
    if (count === 0) {
      bountyListEl.innerHTML = `<p class="muted">No bounties yet — create the first one above.</p>`;
      return;
    }
    for (let id = count; id >= 1; id--) {
      bountyListEl.appendChild(bountyCard(await readBounty(id)));
    }
    log(`Loaded ${count} bounties`);
  } catch (err) {
    bountyListEl.innerHTML = `<p class="muted">Failed to load bounties: ${err?.message || err}</p>`;
  }
}

async function createBounty() {
  const title = $("f-title").value.trim();
  const criteria = $("f-criteria").value.trim();
  const amountStr = $("f-amount").value.trim();
  if (!title || !criteria) return alert("Title and criteria are required.");
  let amount;
  try {
    amount = toWei(amountStr);
  } catch {
    return alert("Invalid amount.");
  }
  if (amount <= 0n) return alert("Amount must be greater than 0.");
  const btn = $("create-btn");
  btn.disabled = true;
  $("create-quote").textContent = "Estimating fee…";
  try {
    // Quote first so the user sees the fee before signing anything.
    const k = getKit();
    const tx = { kind: "write", address: CONTRACT_ADDRESS, method: "create_bounty", args: [title, criteria] };
    const quote = await k.estimate({ preset: "standard", userValue: amount }, tx);
    if (quote.verification.status === "mismatch") {
      throw new Error("Fee policy changed since the quote; re-estimate before signing.");
    }
    $("create-quote").textContent =
      `Fee ${fromWei(quote.feeValue)} GEN + escrow ${fromWei(amount)} GEN = total ${fromWei(quote.total)} GEN. Confirm in your wallet.`;
    const { genlayerTxId } = await k.submit(quote, tx);
    log(`create_bounty submitted, tx ${genlayerTxId}`);
    const final = await k.track(genlayerTxId, (s) => {
      log(`create_bounty: ${s.phase}${s.statusName ? ` (${s.statusName})` : ""}`);
    }, { until: "finalized" });
    if (final.successful === false) throw new Error("create_bounty finished unsuccessfully");
    $("create-quote").textContent = "Bounty created.";
    $("f-title").value = "";
    $("f-criteria").value = "";
    await refreshBounties();
  } catch (err) {
    $("create-quote").textContent = `Failed: ${err?.message || err}`;
  } finally {
    btn.disabled = false;
  }
}

$("connect-btn").addEventListener("click", connectWallet);
$("refresh-btn").addEventListener("click", refreshBounties);
$("create-btn").addEventListener("click", createBounty);
if (window.ethereum) {
  window.ethereum.on?.("accountsChanged", () => window.location.reload());
  window.ethereum.on?.("chainChanged", () => window.location.reload());
}
refreshBounties();
