# §8 — Serving-Layer System

The §4 model logic is research-iterated in Python and re-validated against the §6 OOS panel after every change, while the production hot path is a Solana program reading bands at consumer-facing latency. The stack reconciles these as a contract between three audiences (§8.1) under a byte-for-byte parity guarantee (§8.5); crate-level internals and the on-chain wire format are in Appendix D.

## 8.1 Split-by-function architecture

The serving stack is a contract between the **researcher** iterating against the Python OOS panel, the **protocol integrator** building against on-chain `PriceUpdate` accounts, and the **third-party auditor** verifying a served band against the published artefact. The Python `Oracle` (`src/soothsayer/oracle.py`) is the canonical specification: a methodology change — a new $c(\tau)$ schedule, a σ̂ rule swap — is implemented and OOS-validated in Python first, then ported to Rust under the parity contract below. No model logic is duplicated: the training pipeline materialises the per-Friday lookup rows and deployment scalars once, offline; the serving stack reads them. This split is the operational instantiation of the auditability property $P_1$.

## 8.5 Byte-for-byte parity verification

`scripts/verify_rust_oracle.py` runs the Python `Oracle` and the Rust serving CLI on the same `(symbol, fri_ts, target)` triples and asserts byte-exact agreement on numeric output (point, lower, upper, sharpness, claimed-served, buffer) plus exact string-field agreement (regime, forecaster). **180/180 cases pass** (90 on the M5 path, 90 on the M6 LWC path). The harness re-runs after every methodology change; it is the contract that lets a consumer verify a served `PricePoint` against the published artefact without trusting either implementation in isolation. The on-chain `PriceUpdate` Borsh layout — informed by the Pyth-Network September-2021 flash-crash post-mortem — uses absolute prices, a single shared exponent, and integer basis points, so cross-field comparisons are exact and deterministic across Rust, Anchor, TypeScript, and Python (Appendix D).

## 8.7 Practitioner integration — a worked $\tau \to$ reserve example

To make the consumer contract concrete we walk one illustrative mapping from served coverage to a reserve decision; it is an *example of the mechanics*, not a recommended policy (the decision-theoretic optimum is out of scope, §9). Consider a market holding SPYx with liquidation-LTV threshold $\theta$ and a position at LTV $\ell < \theta$, whose adverse-move buffer — the fractional collateral drawdown that exhausts headroom — is $b = 1 - \ell/\theta$. The protocol reads the served lower bound $L_\tau = \hat P(1 - d_\tau)$ and treats $d_\tau = q_\text{eff}(\tau)\,\hat\sigma_s$ as the closed-market shock it must survive with probability $\tau$.

- **$\tau$ selection.** Choosing $\tau$ sets the per-name closed-market breach budget to $1-\tau$ ($\sim 5\%$ at $\tau = 0.95$, $\sim 1\%$ at $\tau = 0.99$); a protocol picks $\tau$ so its tolerated bad-debt frequency matches.
- **Reserve headroom.** A position survives the $\tau$-band shock iff $b \ge d_\tau$. For SPYx at $\tau = 0.95$, $d_\tau \approx 178$ bps (§7.6); against the production origination-to-liquidation buffer of $\sim 2.7\%$ on SPYx/QQQx, a typical position clears with $\sim 0.9\%$ to spare, but one opened near the threshold ($b < 1.78\%$) does not and should be pre-emptively de-risked. This is the narrow-buffer class where the band has decision-flipping headroom; wide-buffer names ($14$–$25\%$) bind only at $\tau = 0.99$ or under the joint tail.
- **Portfolio reserve.** For $m$ correlated names the single-name $d_\tau$ does not aggregate independently; the protocol sizes its reserve against the joint breach-count $k_w$ distribution (§6.4), with $k^\ast = 3$ as the circuit-breaker trigger (§9).

Every quantity is on the served receipt ($\hat P$, $d_\tau$, $\tau$) plus the public $k_w$ CDF; no incumbent oracle exposes the inputs this mapping needs.
