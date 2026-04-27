"""
Auction Failure Research Module — MANTIS

Primitive event classes built on auction mechanics.
No connection to existing detector system.
Shadow mode only. No production integration.

Event classes:
  1. failed_aggressive_sell — sell aggression fails to move price lower
  2. failed_aggressive_buy  — buy aggression fails to move price higher
  3. breakout_acceptance    — price breaks level, holds, flow supports
  4. breakout_rejection     — price breaks level, returns, flow fails
"""
