/**
 * MergeBounty deployment config — single source of truth for the network
 * the checked-in frontend targets.
 *
 * Deployed 2026-11-20 to the GenLayer Studio network (chain 61999) via
 * GenLayer Studio, tx 0x9fe4a7d631b934d0e4b3242286e693eea793f80f609971e441ecb0816d664720
 * (FINALIZED, GenVM SUCCESS). Every value below targets that same
 * network: client chain, contract address, explorer, and RPC. Do not
 * mix in another network's values (e.g. Bradbury, chain 4221) — the
 * frontend, the fee profile, and this config must all agree.
 */
export const CONTRACT_ADDRESS = "0xf85c6Db3A886De786BB69078555A653b10254e99";
export const EXPLORER_URL = "https://explorer-studio.genlayer.com";
export const RPC_URL = "https://studio.genlayer.com/api";
export const CHAIN_ID = 61999;
export const CHAIN_NAME = "Genlayer Studio Network";
