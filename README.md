# MergeBounty — trustless bounty escrow settled by live evidence

An **Intelligent Contract** on GenLayer (Studio network, chain 61999) that removes the
trusted middleman from freelance/bounty payments.

**The problem.** Paying for open work today needs trust: the client fears
paying for nothing; the worker fears working for nothing. Escrow agents,
platforms, and human arbitrators are slow, expensive, and themselves
trusted parties.

**The fix.** A client locks test GEN in escrow with a task (title +
acceptance criteria) and names the authorized worker who will do it.
Only that worker can submit evidence (a URL — typically a
GitHub pull request), so an arbitrary first caller cannot become the
payout recipient. GenLayer validators **fetch the live page** and an
**LLM judges** whether the evidence meets the criteria. On consensus:

- criteria **met** → escrowed GEN is released to the worker
- criteria **unmet** → escrowed GEN is refunded to the client

No human judge, no oracle, no intermediary. The verdict and the money
movement are both on-chain.

## Why this fits GenLayer (and the portal quality bar)

- **Real trust problem** — bounty/freelance payment trust, solved without a
  trusted third party.
- **Uses GenLayer's core primitives** — live web fetch (`gl.nondet.web.get`)
  + LLM judgement (`gl.nondet.exec_prompt`) inside `gl.vm.run_nondet_unsafe`
  with a custom validator (agreement on the `met` verdict + a minimum
  confidence, never exact-text equality).
- **Different from the boilerplate** — the official boilerplate is a
  football prediction market; the Internet Court demo is dispute
  arbitration. MergeBounty is neither: it is an *automated evidence
  verifier* for escrowed work.
- **Complete code + accurate docs** — contract, 16 passing direct-mode
  tests, a frontend that actually calls the contract, and this README.
- **Testnet only, free only** — no mainnet, no payments beyond test GEN.

## Project layout

```
contracts/bounty_escrow.py     # the Intelligent Contract (BountyEscrow)
tests/direct/test_bounty_escrow.py  # 16 direct-mode tests (mocked web + LLM)
frontend/                      # Vite + genlayer-js + @genlayer/transaction-kit
  src/main.js  src/config.js  src/fee-profile.json
docs/
  RESEARCH.md                  # sources, versions, gotchas found while building
  DEPLOY.md                    # exact deploy steps (wallet signature needed)
  SUBMIT.md                    # pre-filled portal submit-form fields
```

## Contract API

| Method | Type | What it does |
|---|---|---|
| `create_bounty(title, criteria)` | `@gl.public.write.payable` → `u256` | Locks the sent GEN, creates bounty #id, status `FUNDED` |
| `submit_evidence(bounty_id, evidence_url)` | `@gl.public.write` | Worker posts an `https://` evidence URL → status `EVIDENCE` |
| `resolve_bounty(bounty_id)` | `@gl.public.write` | Fetches evidence live + LLM verdict; `RELEASED` (worker paid) or `REFUNDED` (client refunded) |
| `cancel_bounty(bounty_id)` | `@gl.public.write` | Client-only, only while `FUNDED` (before evidence) → refund |
| `get_bounty(bounty_id)` | `@gl.public.view` → `str` | JSON: id, client, worker, amount_wei, title, criteria, evidence_url, status, verdict |
| `get_bounty_count()` | `@gl.public.view` → `u256` | Number of bounties created |
| `get_status(bounty_id)` | `@gl.public.view` → `str` | Status string, or `NONE` |

Trust rules (v1): `resolve()` may be retried while evidence is submitted —
each attempt is a fresh fetch + fresh LLM judgement. The client can only
cancel **before** evidence is submitted. Known limitation: evidence so
ambiguous that validators never agree on `met` leaves the bounty open for
a later resolve attempt (documented in the contract header).

## Test

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/genvm-lint check contracts/bounty_escrow.py
.venv/bin/python -m pytest tests/direct/ -v
```

Result (20 Nov 2026): lint passes (3 checks + validation), **13/13 tests
pass**. Tests use mocked web pages + mocked LLM answers; the validator is
checked separately with `direct_vm.run_validator()` (agreement + a
disagreement case). The actual GEN movement via `emit_transfer` follows
the official Faucet pattern from the docs and is verified on testnet after
deploy (see `docs/DEPLOY.md`) — the direct VM has no public balance
accessor, so tests assert status transitions + stored verdicts.

## Frontend

```bash
cd frontend
npm install
npm run dev      # local dev server
npm run build    # emits dist/ — host it anywhere static (Netlify, Vercel, GH Pages)
```

Set `CONTRACT_ADDRESS` in `frontend/src/config.js` after deploying.
Reads work without a wallet. Writes need MetaMask on the Studio network
(chain 61999) and go through `@genlayer/transaction-kit`: the fee quote
is shown **before** signing, a fee-policy mismatch blocks signing, and
the transaction is tracked to finalization. When creating a bounty, the
client names the authorized worker; only that worker can submit
evidence and receive the payout.

## Deploy

The live deployment is on the GenLayer Studio network (chain 61999):
contract `0xf85c6Db3A886De786BB69078555A653b10254e99`, deployed
2026-11-20 via GenLayer Studio, tx
`0x9fe4a7d631b934d0e4b3242286e693eea793f80f609971e441ecb0816d664720`
(FINALIZED). The frontend's client chain, contract address, explorer,
and fee profile all target that same network (see
`frontend/src/config.js`). [`docs/DEPLOY.md`](docs/DEPLOY.md) documents
the CLI deploy path used before the Studio deploy.

## Submit to the GenLayer portal

See [`docs/SUBMIT.md`](docs/SUBMIT.md) — target category **Projects**
(20–4,000 PTS; 2 slots left in the week of 17–23 Nov 2026), with all form
fields pre-filled. Fallback category: **Intelligent Contracts** (0–500 PTS).

## Versions (pinned 20 Nov 2026)

- GenLayer CLI `0.39.2` · genlayer-test `0.29.2` · genvm-linter `0.11.0`
- genlayer-js `1.1.8` · @genlayer/transaction-kit `0.1.0-rc.1` · vite `8.3.8`
- GenVM runner pinned in the contract: `py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6`
  (the docs' version; the linter notes a newer runner exists — see
  `docs/RESEARCH.md`)
- Network: GenLayer Studio network, chain 61999, RPC
  `https://studio.genlayer.com/api`, explorer
  `https://explorer-studio.genlayer.com`

## License

MIT — see [LICENSE](LICENSE).
