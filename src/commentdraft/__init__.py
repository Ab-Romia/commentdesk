# SPDX-License-Identifier: Apache-2.0
"""Comment triage and reply drafting.

Reads comments from a CSV, spends one model call per comment to get a decision
(reply, skip, escalate) plus a drafted reply, and writes the results out as a CSV
and a review page. Nothing is published that a person has not approved, one reply
at a time, through the gate in commentdraft.approve.

Everything an operator touches is configuration, knowledge, or voice. This package
holds none of the three: no product, no language, no copy.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
