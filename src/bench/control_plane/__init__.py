"""Bench control plane — module 8.

A Django + DRF service over modules 1-6: an agent/task/machine registry, policy
decisions, the audit trail (DB-backed), spend, and a ``/live`` view. Submitting
a goal runs it through the hand-wired flow in :mod:`bench.control_plane.runner`
until module 7 (LangGraph orchestration) replaces that internals.
"""
