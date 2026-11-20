# Portal submit — pre-filled fields for MergeBounty

> Target category: **Projects** (20–4,000 PTS — 2 slots left in the week
> of 17–23 Nov 2026; weekly window Mon 00:00–Sun 23:59 UTC).
> Fallback category: **Intelligent Contracts** (0–500 PTS).
> Do NOT submit until `docs/DEPLOY.md` steps 5–7 are done (live deploy +
> verified money flow + hosted frontend). Fill in the bracketed items
> after deploy.

## Form fields

- **Name:** MergeBounty
- **Tags:** escrow, bounties, LLM, oracle, freelance, payments
- **One-liner (max 180 chars):**
  > Trustless bounty escrow on GenLayer: lock GEN, submit a PR link as evidence, and let validators + an LLM decide if the work is done — paid or refunded, no judge.
- **Description (max 1000 chars):**
  > MergeBounty removes the trusted middleman from bounty payments. A client locks test GEN in escrow with a task and acceptance criteria. A worker submits evidence as a URL — typically a GitHub pull request. GenLayer validators fetch the live page and an LLM judges whether the evidence meets the criteria. On consensus the escrow pays the worker if the criteria are met, or refunds the client if not. No human judge, no oracle, no intermediary. The contract is a full Intelligent Contract (payable escrow, live web fetch, LLM verdict with a custom equivalence rule, on-chain fund release), covered by 13 passing direct-mode tests, with a Vite frontend that actually calls the contract (create / submit evidence / resolve / cancel) via genlayer-js and the transaction kit. Testnet only, free only.
- **How-to (for the verifier):**
  > 1. Open the website and connect MetaMask on GenLayer Bradbury testnet (chain 4221). 2. Create a bounty: title, acceptance criteria, amount in test GEN — the fee quote is shown before you sign. 3. Submit evidence: paste a merged GitHub PR URL. 4. Click Resolve: validators fetch the PR live and the LLM returns a verdict; watch the bounty flip to RELEASED (worker paid) or REFUNDED (client refunded). 5. Check the verdict and the fund movement on the Bradbury explorer via the contract link. The README documents every step and the full test run.
- **Expected verification outcome:**
  > A bounty created from the frontend appears on-chain with status FUNDED and the locked amount; evidence submission moves it to EVIDENCE; resolving it stores the LLM verdict on-chain and moves the escrowed GEN to the worker (RELEASED) or back to the client (REFUNDED), visible in the explorer and in the frontend's bounty list. All contract methods are also covered by the 13 direct-mode tests in the repo (lint + validation pass).
- **GitHub:** https://github.com/mekii69/mergebounty *(repo to be created by the parent — do not submit before it exists and is public)*
- **Website:** <URL of the hosted frontend dist/ — fill in after hosting>
- **Contract explorer link:** https://explorer-bradbury.genlayer.com/address/<CONTRACT_ADDRESS> *(fill in after deploy)*
- **Demo video (optional):** not recorded yet — optional field; a short screen recording of the create → evidence → resolve flow can be added before submitting.

## Pre-submit checklist

- [ ] Contract deployed to Bradbury; address + tx hash recorded
- [ ] Live end-to-end run done (create → evidence → resolve) with a small
      amount; fund movement verified on the explorer
- [ ] Fee profile filled with measured allocations; frontend rebuilt
- [ ] Frontend hosted; website URL works without a wallet (reads load)
- [ ] GitHub repo public at github.com/mekii69/mergebounty with README +
      contract + tests + frontend + docs (no secrets, no private keys)
- [ ] Weekly slot still available (Projects: 2 left as of 20 Nov 2026;
      re-check before submitting — the window ends Sun 23 Nov 23:59 UTC)
