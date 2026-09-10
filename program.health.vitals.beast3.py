# program.health.vitals.beast3.py
# Beast System 3.0 — Deterministic Vitals Engine

from dataclasses import dataclass, field
import time
import hashlib

# Thresholds for risk detection
VITAL_THRESHOLDS = {
    "heart_rate": {"low": 50, "high": 120},
    "blood_pressure_systolic": {"low": 90, "high": 140},
    "blood_pressure_diastolic": {"low": 60, "high": 90},
    "oxygen": {"low": 92, "high": 100},
    "temperature": {"low": 97.0, "high": 100.4}
}

@dataclass
class VitalsPacket:
    family_id: str
    vitals: dict
    stability_score: float
    risk_flags: list
    emergency: bool
    ts: float = field(default_factory=time.time)
    hash: str = ""

    def finalize(self):
        serialized = f"{self.family_id}{self.vitals}{self.stability_score}{self.risk_flags}{self.emergency}{self.ts}".encode("utf-8")
        self.hash = hashlib.sha256(serialized).hexdigest()

@dataclass
class VitalsProfile:
    family_id: str
    packets: list = field(default_factory=list)
    last_update: float = field(default_factory=time.time)

    def add_packet(self, packet: VitalsPacket):
        packet.finalize()
        self.packets.append(packet)
        self.last_update = packet.ts

class VitalsEngine:
    def __init__(self, kernel):
        self.kernel = kernel
        self.vitals_profiles = {}

    def create_profile(self, family_id: str):
        profile = VitalsProfile(family_id)
        self.vitals_profiles[family_id] = profile

        return self.kernel.dispatch(
            module="health.vitals",
            action="create_profile",
            payload={"family_id": family_id}
        )

    def submit_vitals(self, family_id: str, vitals: dict):
        if family_id not in self.vitals_profiles:
            raise ValueError("Vitals profile not found")

        risk_flags = []
        emergency = False
        stability_components = []

        # Evaluate each vital against thresholds
        for key, value in vitals.items():
            if key in VITAL_THRESHOLDS:
                low = VITAL_THRESHOLDS[key]["low"]
                high = VITAL_THRESHOLDS[key]["high"]

                # Stability score contribution
                if isinstance(value, (int, float)):
                    if low <= value <= high:
                        stability_components.append(1.0)
                    else:
                        stability_components.append(0.0)

                # Risk detection
                if value < low:
                    risk_flags.append(f"low_{key}")
                if value > high:
                    risk_flags.append(f"high_{key}")

        # Stability score (0.0 to 1.0)
        stability_score = (
            sum(stability_components) / len(stability_components)
            if stability_components else 0.0
        )

        # Emergency flag if multiple vitals are out of range
        emergency = len(risk_flags) >= 3

        packet = VitalsPacket(
            family_id=family_id,
            vitals=vitals,
            stability_score=round(stability_score, 4),
            risk_flags=risk_flags,
            emergency=emergency
        )

        profile = self.vitals_profiles[family_id]
        profile.add_packet(packet)

        return self.kernel.dispatch(
            module="health.vitals",
            action="submit_vitals",
            payload={
                "family_id": family_id,
                "vitals": vitals,
                "stability_score": stability_score,
                "risk_flags": risk_flags,
                "emergency": emergency
            }
        )

    def get_packets(self, family_id: str):
        return self.vitals_profiles.get(family_id, None)
