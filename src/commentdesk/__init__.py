# SPDX-License-Identifier: Apache-2.0
"""Comment triage and reply drafting.

Reads comments from a CSV, spends one model call per comment to get a decision
(reply, skip, escalate) plus a drafted reply, and writes the results out as a CSV
and a review page. It never posts anything anywhere.

Everything an operator touches is configuration, knowledge, or voice. This package
holds none of the three: no product, no language, no copy.
"""

__version__ = "0.1.0"

__all__ = ["__version__"]
