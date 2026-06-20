"""Presets de geolocalización (lat, lon, zona horaria IANA)."""

# clave visible -> (latitud, longitud, tz)
CITIES = {
    "Temixco, MX (IER-UNAM)": (18.85, -99.23, "America/Mexico_City"),
    "Mérida, MX": (20.97, -89.62, "America/Merida"),
    "Ciudad de México, MX": (19.43, -99.13, "America/Mexico_City"),
    "Monterrey, MX": (25.67, -100.31, "America/Monterrey"),
    "La Paz, BCS, MX": (24.14, -110.31, "America/Mazatlan"),
    "Tuxtla Gutiérrez, MX": (16.75, -93.12, "America/Mexico_City"),
    "Quito, EC": (-0.18, -78.47, "America/Guayaquil"),
    "Madrid, ES": (40.42, -3.70, "Europe/Madrid"),
    "Tromsø, NO": (69.65, 18.96, "Europe/Oslo"),
}

DEFAULT_CITY = "Temixco, MX (IER-UNAM)"

# Zonas horarias ofrecidas en el selector manual (cuando se editan lat/lon a mano).
TIMEZONES = [
    "America/Mexico_City",
    "America/Merida",
    "America/Monterrey",
    "America/Mazatlan",
    "America/Tijuana",
    "America/Guayaquil",
    "America/Bogota",
    "America/Lima",
    "America/Argentina/Buenos_Aires",
    "Europe/Madrid",
    "Europe/Oslo",
    "UTC",
]
