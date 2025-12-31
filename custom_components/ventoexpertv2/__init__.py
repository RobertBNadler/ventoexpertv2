"""VentoExpertV2 integration init."""

from __future__ import annotations
import logging
import os
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from .const import DOMAIN

PLATFORMS: list[str] = ["sensor"]
_LOGGER = logging.getLogger(__name__)

DASHBOARD_FILE = "ventoexpert-dashboard.yaml"

LOVELACE_VIEW = """title: VentoExpert
views:
  - title: VentoExpert Übersicht
    path: ventoexpert
    cards:
      - type: entities
        title: Status
        entities:
          - sensor.ventoexpert_status
          - sensor.ventoexpert_modus
          - sensor.ventoexpert_lueftungsstufe
          - sensor.ventoexpert_boost
      - type: gauge
        entity: sensor.feuchte_istwert
        name: Feuchte Istwert
        min: 0
        max: 100
        unit: "%"
      - type: gauge
        entity: sensor.ventilator_1_drehzahl
        name: Ventilator 1
        min: 0
        max: 3000
        unit: "rpm"
      - type: gauge
        entity: sensor.ventilator_2_drehzahl
        name: Ventilator 2
        min: 0
        max: 3000
        unit: "rpm"
"""


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up VentoExpertV2 from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Sensor-Platform laden
    await hass.config_entries.async_forward_entry_setup(entry, "sensor")

    # Automatisch Lovelace-View hinzufügen (nur wenn Service verfügbar)
    if hass.services.has_service("lovelace", "update_config"):
        try:
            await hass.services.async_call(
                "lovelace",
                "update_config",
                {
                    "config": {
                        "views": [
                            {
                                "title": "VentoExpert",
                                "path": "ventoexpert",
                                "cards": [
                                    {
                                        "type": "entities",
                                        "title": "Status",
                                        "entities": [
                                            "sensor.ventoexpert_status",
                                            "sensor.ventoexpert_modus",
                                            "sensor.ventoexpert_lueftungsstufe",
                                            "sensor.ventoexpert_boost",
                                        ],
                                    },
                                    {
                                        "type": "gauge",
                                        "entity": "sensor.feuchte_istwert",
                                        "name": "Feuchte Istwert",
                                        "min": 0,
                                        "max": 100,
                                        "unit": "%",
                                    },
                                    {
                                        "type": "gauge",
                                        "entity": "sensor.ventilator_1_drehzahl",
                                        "name": "Ventilator 1",
                                        "min": 0,
                                        "max": 3000,
                                        "unit": "rpm",
                                    },
                                    {
                                        "type": "gauge",
                                        "entity": "sensor.ventilator_2_drehzahl",
                                        "name": "Ventilator 2",
                                        "min": 0,
                                        "max": 3000,
                                        "unit": "rpm",
                                    },
                                ],
                            }
                        ]
                    }
                },
                blocking=True,
            )
            _LOGGER.info("VentoExpert Lovelace-View erfolgreich erstellt.")
        except HomeAssistantError as err:
            _LOGGER.error(f"Fehler beim Erstellen der Lovelace-View: {err}")
    else:
        # Fallback: YAML-Datei in /config/www schreiben
        www_path = hass.config.path("www")
        os.makedirs(www_path, exist_ok=True)
        file_path = os.path.join(www_path, DASHBOARD_FILE)

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(LOVELACE_VIEW)
            _LOGGER.warning(
                f"Lovelace-Service nicht verfügbar. Dashboard wurde als YAML-Datei erstellt: {file_path}. "
                "Bitte manuell in Lovelace einbinden."
            )
        except Exception as err:
            _LOGGER.error(f"Fehler beim Schreiben der Dashboard-Datei: {err}")

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload VentoExpertV2 entry."""
    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
