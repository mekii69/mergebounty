# Deploy guide — MergeBounty to Bradbury testnet

> Do NOT deploy from anywhere except this repo (`~/workspace/genlayer/mergebounty`).
> Testnet only. The deploy transaction is signed by the user's wallet
> (the portal account's connected wallet, secondary `0x1b74...28ec`).
> Nothing here signs anything on its own.

## 0. Prerequisites

- Node.js 18+ and Python 3.12 (this repo was built with Node v24.22.1,
  Python 3.12.3).
- GenLayer CLI `0.39.2` (already installed globally on the build machine):
  `genlayer --version` → `0.39.2`. Otherwise `npm install -g genlayer`.
- A wallet with test GEN on Bradbury. The user already topped up test GEN
  via the Wizard of Coin flow ("Your wallet has enough test GEN for a
  message", 20 Nov 2026), so the faucet may not be needed. If more is
  needed: https://testnet-faucet.genlayer.foundation (100 GEN / 24h).
  **Caveat (unverified from official docs):** a third-party guide
  (testnetradar.com) says the faucet requires a GitHub account older than
  3 months **and** 0.01 ETH on Ethereum mainnet. The official docs only
  link the faucet without stating the gate. If the faucet refuses, use the
  GEN already in the wallet.

## 1. Create / select the CLI deployer account

The CLI signs deploys from a local encrypted keystore account. This is a
**new keystore for deployment only** — it is not the user's portal wallet
seed and it must never be pasted anywhere.

```bash
genlayer account create --name mergebounty-deployer   # prompts for a keystore password
genlayer account                                        # shows address, balance, network
```

Fund the deployer address with test GEN (from the faucet, or
`genlayer account send <address> <amount>gen` from another funded CLI
account). Check the balance with `genlayer account`.

> Alternative: deploy from GenLayer Studio (studio.genlayer.com) with the
> browser wallet instead — the Studio signs with its own browser accounts.
> The CLI path below is the reproducible one for this repo.

## 2. Select and verify the network

```bash
genlayer network set testnet-bradbury
genlayer network info
```

Expected (verified 20 Nov 2026):

```
alias: 'testnet-bradbury', name: 'Genlayer Bradbury Testnet',
chainId: '4221', rpc: 'https://rpc-bradbury.genlayer.com',
mainContract: '0x0112Bf6e83497965A5fdD6Dad1E447a6E004271D',
stakingContract: '0x4A4449E617F8D10FDeD0b461CadEf83939E821A5',
explorer: 'https://explorer-bradbury.genlayer.com/'
```

**Check chainId is 4221 before signing anything.** Asimov and Bradbury
share chain ID 4221 in older docs; Bradbury is the production-like testnet
to use (per current docs).

## 3. Lint + test (again, right before deploy)

```bash
.venv/bin/genvm-lint check contracts/bounty_escrow.py
.venv/bin/python -m pytest tests/direct/ -v   # expect 13 passed
```

## 4. Deploy

```bash
genlayer deploy --contract contracts/bounty_escrow.py
```

What happens:

- The CLI resolves the deploy entry in `fee-profile.json`, estimates it
  against current network prices, and submits the required fee fields
  (Consensus v0.6 fee distribution + protocol-fee value).
- **A wallet signature is required** — the CLI prompts for the keystore
  password and signs the deploy transaction from the deployer account.
  Review the network (Bradbury, chain 4221), the contract file, and the
  fee quote the CLI prints before confirming.
- Wait for finalization, then **verify the execution result** before using
  the address (the docs are explicit about this).

Record the output: contract address + transaction hash + explorer link.

## 5. Verify on-chain

1. Open the contract on the explorer:
   `https://explorer-bradbury.genlayer.com/address/<CONTRACT_ADDRESS>`.
2. Read `get_bounty_count()` — expect `0` on a fresh deploy.
3. Do one live end-to-end run with a **small** amount (e.g. 0.01 test GEN):
   - `create_bounty` (payable) → note the bounty id.
   - `submit_evidence` with a real merged GitHub PR URL.
   - `resolve_bounty` → wait for the validator verdict; check the status
     becomes `RELEASED` and the worker's GEN balance increased (explorer),
     or `REFUNDED` with the client refunded. This is the step that
     verifies the `emit_transfer` money flow, which direct-mode tests
     cannot assert (no public balance accessor in the direct VM).
4. Only after the live run succeeds, fill in the fee profile (below) and
   point the frontend at the contract.

## 6. Fee profile (frontend)

`frontend/src/fee-profile.json` currently has **no measured per-method
allocations** — the transaction kit falls back to network defaults, which
is correct for the first deploy. After the live run in step 5, measure the
allocations per method from the successful transactions (deploy,
create_bounty, submit_evidence, resolve_bounty, cancel_bounty), add
headroom, fill them into `fee-profile.json` with `chainId: 4221` and a new
`measuredAt` date, and rebuild the frontend.

## 7. Point the frontend at the contract

```bash
# frontend/src/config.js
export const CONTRACT_ADDRESS = "0x<address from step 4>";
cd frontend && npm run build   # emits dist/
```

Host `dist/` on any static host (Netlify, Vercel, GitHub Pages). That URL
goes in the portal submit form's "website" field.

## 8. Submit to the portal

See [`SUBMIT.md`](SUBMIT.md). Do not submit before steps 5–7 are done:
the portal requires a GitHub repo + a working deployment + a frontend
that actually calls the contract.
