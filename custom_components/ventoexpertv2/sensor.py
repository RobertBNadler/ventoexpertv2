from __future__ import annotations
import asyncio
import socket
import logging
from datetime import timedelta

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

ALL_PARAMS = [
    0x0001,  # Anlage
    0x0002,  # Lüfterstufe
    0x0006,  # Boost
    0x0019,  # Feuchtesollwert
    0x0025,  # Feuchteistwert
    0x004A,  # Lüfterstufe Ventilator 1
    0x004B,  # Lüfterstufe Ventilator 2
    0x00B7,  # Betriebsart
]


# ---------------------------------------------------------
# Hilfsfunktionen für UDP-Kommunikation
# ---------------------------------------------------------
def calc_checksum(packet: bytes) -> bytes:
    checksum = sum(packet) & 0xFFFF
    return bytes([checksum & 0xFF, (checksum >> 8) & 0xFF])


def build_read_packet(device_id: str, password: str, params: list[int]) -> bytes:
    start = bytes([0xFD, 0xFD])
    type_byte = bytes([0x02])
    size_id = bytes([0x10])
    id_bytes = device_id.encode("ascii").ljust(16, b"\x00")
    size_pwd = bytes([0x04])
    pwd_bytes = password.encode("ascii").ljust(4, b"\x00")
    func = bytes([0x01])
    data_block = b""
    for param in params:
        high = (param >> 8) & 0xFF
        low = param & 0xFF
        if high > 0:
            data_block += bytes([0xFF, high])
        data_block += bytes([low])
    body = type_byte + size_id + id_bytes + size_pwd + pwd_bytes + func + data_block
    checksum = calc_checksum(body)
    return start + body + checksum


async def udp_request(host: str, port: int, packet: bytes, retries: int = 3) -> bytes:
    for attempt in range(retries):
        data = await asyncio.to_thread(_send_udp, host, port, packet)
        if data:
            _LOGGER.debug("Antwort erhalten nach %d Versuch(en)", attempt + 1)
            return data
        else:
            _LOGGER.warning("Keine Antwort, Retry %d von %d", attempt + 1, retries)
            await asyncio.sleep(0.5)
    _LOGGER.error("Alle %d Versuche fehlgeschlagen.", retries)
    return b""


def _send_udp(host: str, port: int, packet: bytes) -> bytes:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    try:
        sock.sendto(packet, (host, port))
        data, _ = sock.recvfrom(1024)
        return data
    except socket.timeout:
        _LOGGER.warning("UDP request to %s:%d timed out.", host, port)
        return b""
    except Exception as e:
        _LOGGER.error("UDP error: %s", e)
        return b""
    finally:
        sock.close()


def parse_ventoexpert_response(data: bytes) -> dict:
    if not data or len(data) < 20:
        _LOGGER.warning(
            "UDP response too short or empty: %s", data.hex() if data else "None"
        )
        return {}
    try:
        func_index = data.index(0x06)
    except ValueError:
        _LOGGER.warning("FUNC 0x06 nicht in Antwort gefunden: %s", data.hex())
        return {}
    pos = func_index + 1
    result = {}
    while pos < len(data) - 2:
        param = data[pos]
        pos += 1
        if param == 0x64:  # Filtertimer (3 Bytes)
            if pos + 3 > len(data):
                break
            value = tuple(data[pos : pos + 3])
            result[param] = value
            pos += 3
        elif param in (0x4A, 0x4B):  # Lüfterdrehzahl (2 Bytes)
            if pos + 2 > len(data):
                break
            value = data[pos] | (data[pos + 1] << 8)
            result[param] = value
            pos += 2
        else:  # 1-Byte-Parameter
            if pos >= len(data):
                break
            value = data[pos]
            result[param] = value
            pos += 1
    return result


# ---------------------------------------------------------
# DataUpdateCoordinator
# ---------------------------------------------------------
class VentoExpertCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, host, port, device_id, password, params, update_interval):
        self.host = host
        self.port = port
        self.device_id = device_id
        self.password = password
        self.params = params

        super().__init__(
            hass,
            _LOGGER,
            name="VentoExpert",
            update_interval=timedelta(seconds=update_interval),
        )

    async def _async_update_data(self):
        try:
            packet = build_read_packet(self.device_id, self.password, self.params)
            data = await udp_request(self.host, self.port, packet)
            if not data:
                raise UpdateFailed("Keine Antwort vom Gerät")
            parsed = parse_ventoexpert_response(data)
            return parsed
        except Exception as err:
            raise UpdateFailed(f"Fehler beim Abrufen der Daten: {err}")


# ---------------------------------------------------------
# Basis-Sensor-Klasse
# ---------------------------------------------------------
class VentoExpertBaseSensor(SensorEntity):
    def __init__(self, name, coordinator, param):
        self._attr_name = name
        self.coordinator = coordinator
        self.param = param

    async def async_added_to_hass(self):
        self.async_on_remove(
            self.coordinator.async_add_listener(self.async_write_ha_state)
        )

    @property
    def available(self):
        return self.param in self.coordinator.data

    @property
    def native_value(self):
        return self._format_value(self.coordinator.data.get(self.param))

    def _format_value(self, raw):
        return raw


# ---------------------------------------------------------
# Spezialisierte Sensoren
# ---------------------------------------------------------
class VentoExpertPowerSensor(VentoExpertBaseSensor):
    _attr_icon = "mdi:power"
    # Kein state_class, kein unit (Textwert)

    def _format_value(self, raw):
        mapping = {0: "Aus", 1: "Ein", 2: "Invertieren"}
        return mapping.get(raw, "Unbekannt")


class VentoExpertModeSensor(VentoExpertBaseSensor):
    _attr_icon = "mdi:cog"
    # Kein state_class, kein unit (Textwert)

    def _format_value(self, raw):
        mapping = {0: "Lüftung", 1: "Wärmerückgewinnung", 2: "Zuluft"}
        return mapping.get(raw, "Unbekannt")


class VentoExpertHumiditySensor(VentoExpertBaseSensor):
    _attr_icon = "mdi:water-percent"
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT


class VentoExpertFanSensor(VentoExpertBaseSensor):
    _attr_icon = "mdi:fan"
    _attr_native_unit_of_measurement = "rpm"
    _attr_state_class = SensorStateClass.MEASUREMENT


class VentoExpertStageSensor(VentoExpertBaseSensor):
    _attr_icon = "mdi:air-filter"

    def _format_value(self, raw):
        mapping = {
            1: "Lüftungsstufe 1",
            2: "Lüftungsstufe 2",
            3: "Lüftungsstufe 3",
            255: "Manuell",
        }
        return mapping.get(raw, "Unbekannt")


class VentoExpertBoostSensor(VentoExpertBaseSensor):
    _attr_icon = "mdi:rocket-launch"

    def _format_value(self, raw):
        mapping = {0: "Aus", 1: "Ein"}
        return mapping.get(raw, "Unbekannt")


# ---------------------------------------------------------
# Setup
# ---------------------------------------------------------
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    coordinator = VentoExpertCoordinator(
        hass,
        entry.data["host"],
        entry.data["port"],
        entry.data.get("device_id", "DEFAULT_DEVICEID"),
        entry.data.get("password", "1111"),
        ALL_PARAMS,
        entry.data.get("update_interval", 10),
    )

    await coordinator.async_config_entry_first_refresh()

    sensors = [
        VentoExpertPowerSensor("VentoExpert Betrieb", coordinator, 0x0001),
        VentoExpertStageSensor("VentoExpert Lüftungsstufe", coordinator, 0x0002),
        VentoExpertBoostSensor("VentoExpert Boost", coordinator, 0x0006),
        VentoExpertModeSensor("VentoExpert Betriebsart", coordinator, 0x00B7),
        VentoExpertHumiditySensor("VentoExpert Feuchte Sollwert", coordinator, 0x0019),
        VentoExpertHumiditySensor("VentoExpert Feuchte Istwert", coordinator, 0x0025),
        VentoExpertFanSensor("VentoExpert Ventilator 1", coordinator, 0x004A),
        VentoExpertFanSensor("VentoExpert Ventilator 2", coordinator, 0x004B),
    ]
    async_add_entities(sensors)
