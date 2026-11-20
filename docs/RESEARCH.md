# Research notes — MergeBounty (20 Nov 2026)

Sources actually read (not just searched):

- https://docs.genlayer.com (full docs text, downloaded 20 Nov 2026 as
  `full-documentation.txt`, 1.1 MB) — protocol, first contract,
  non-determinism, calling LLMs, value transfers, tooling setup, testing,
  deploying, network configuration, transaction kit.
- https://docs.genlayer.com/developers/intelligent-contracts/first-contract
- https://docs.genlayer.com/developers/intelligent-contracts/deploying/network-configuration
- Official boilerplate contract (reference for storage init):
  https://github.com/genlayerlabs/genlayer-project-boilerplate/blob/main/contracts/football_bets.py
- https://testnetradar.com/guides/genlayer-intelligent-contract (third-party
  guide; faucet-gate claim is from here, NOT from official docs)
- Installed toolchain (verified by running): GenLayer CLI `0.39.2`,
  genlayer-test `0.29.2`, genvm-linter `0.11.0`, genlayer-js `1.1.8`,
  @genlayer/transaction-kit `0.1.0-rc.1`, vite `8.3.8`.

## Key facts (verified)

- Intelligent Contracts are Python; class extends `gl.Contract`; public
  methods use `@gl.public.view` / `@gl.public.write` /
  `@gl.public.write.payable`; persisted fields use `TreeMap[K, V]` /
  `DynArray[T]` (never `dict`/`list`); `int` is not a storage type
  (use `u256`/`i32`/`bigint`).
- Version comment (first line, like a pragma):
  `# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }`
  — from the official docs' first-contract page (updated 11 Jun 2026).
- Nondet calls (`gl.nondet.web.get`, `gl.nondet.exec_prompt`) must run
  inside nondet blocks; consensus via `gl.vm.run_nondet_unsafe(leader_fn,
  validator_fn)`. For LLM calls, NEVER use `strict_eq` (LLM output is
  non-deterministic); validate structure/validity instead.
- `gl.nondet.web.get(url)` returns a Response with `.status` and `.body`
  (bytes). `gl.nondet.exec_prompt(prompt, response_format="json")`
  returns a parsed JSON object.
- Value: `@gl.public.write.payable` + `gl.message.value` (u256, GEN wei).
  Sending to an EOA uses the Faucet pattern:
  `@gl.evm.contract_interface class _Recipient: ...` then
  `_Recipient(Address(addr)).emit_transfer(value=amount)`.
  `self.balance` reads the contract balance.
- Tests: `genlayer-test` direct mode (`pytest tests/direct/`), fixtures
  `direct_vm` / `direct_deploy` / `direct_alice` / `direct_bob`;
  `direct_vm.value = <wei>` sets the sent value; `direct_vm.mock_web`
  / `mock_llm` take regex patterns; `direct_vm.run_validator()` checks
  the captured validator (swap mocks first to simulate disagreement);
  `direct_vm.expect_revert("...")` for error paths.
- Deploy: `genlayer network set testnet-bradbury` → `genlayer network info`
  → `genlayer deploy --contract <path>`. CLI accounts are encrypted
  keystores: `genlayer account create --name <name>`.
- Bradbury: chain 4221, RPC https://rpc-bradbury.genlayer.com, explorer
  https://explorer-bradbury.genlayer.com, faucet
  https://testnet-faucet.genlayer.foundation (100 GEN / 24h per the Studio
  PR; the 0.01-ETH-mainnet + GitHub-age gate is third-party-reported only).
- Frontend writes on Bradbury (fee-charging, Consensus v0.6) need a fee
  quote: `@genlayer/transaction-kit` (`estimate` → check
  `quote.verification.status` → `submit` → `track` until finalized).
  `genlayer-js` 1.1.8 does NOT have `estimateTransactionFeesForWrite`
  (that name appears in v2-RC docs); the kit is the documented path.
  Reads: `createClient({ chain: testnetBradbury })` +
  `readContract({ address, functionName, args })`.

## Gotchas found while building (all hit live, all resolved)

1. **TreeMap fields must NOT be assigned in `__init__`.** The docs'
   `self.data = TreeMap()` example fails on the current runner with
   `AssertionError: Is right the same storage type? TreeMap <- TreeMap`
   (bare instance desc ≠ parameterised field desc). The official
   boilerplate (`football_bets.py`) declares TreeMap fields and leaves
   `__init__` as `pass` — storage props are lazily materialised by the
   property getter. Fix applied: only the scalar `next_id` is assigned
   in `__init__`.
2. **Newer runner advisory.** `genvm-lint` notes a newer runner exists
   (`py-genlayer:1zr6nqk597d97kg0dyxg0shhrykx5v02zjgnyrajapy4wlqvfvwh`).
   Switching the version comment to it made validation fail
   ("Failed to load SDK: No module named 'genlayer.py'") with the
   installed genvm-linter 0.11.0 — so the contract pins the docs'
   version, which lints + validates clean. Re-check with a newer
   linter before a future upgrade.
3. **Test-runner download 404.** The first direct-mode run tried to
   download `genvm-universal-v0.3.0-rc7.tar.xz` from GitHub releases and
   got HTTP 404. The linter had already downloaded the identical tarball
   to `~/.cache/genvm-linter/`; copying it to `~/.cache/gltest-direct/`
   fixed it (the runner skips download when the file is cached).
4. **Direct-mode consensus semantics.** A contract call runs the leader
   and applies state changes; `run_validator()` is a separate check
   afterwards. On-chain, consensus gates the state change itself. Tests
   assert both sides explicitly.
5. **Direct VM has no public balance accessor**, so the `emit_transfer`
   money flow cannot be asserted in tests — it must be verified live on
   testnet after deploy (see DEPLOY.md step 5).
6. **Test addresses are raw bytes** in direct mode; the contract stores
   checksummed `0x…` hex. Tests compare case-insensitively.
