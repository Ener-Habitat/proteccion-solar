"""Núcleo de cálculo solar (numpy puro)."""

from .position import solar_position, to_julian_day

__all__ = ["solar_position", "to_julian_day"]
