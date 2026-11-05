"""
Keelway Customer Pilot Kit Package
Provides validation tooling, candidate dossier mapping, interview protocols,
and automated pilot simulation harnesses for engineering leads.
"""

from core.pilot.kit import (
    PilotCandidate,
    PilotSimulationEngine,
    PilotReceipt,
    get_pilot_candidates,
    get_pilot_candidate,
)

__all__ = [
    "PilotCandidate",
    "PilotSimulationEngine",
    "PilotReceipt",
    "get_pilot_candidates",
    "get_pilot_candidate",
]
