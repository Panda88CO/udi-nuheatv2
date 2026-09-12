import json
import logging
import sys
import requests

try:
    from udi_interface import LOGGER
except ImportError:
    LOGGER = logging.getLogger(__name__)


class NuHeat:
    def __init__(self, token_or_provider):
        self.api_v2_url = "https://api.mynuheat.com/api/v2"
        self.api_v1_url = "https://api.mynuheat.com/api/v1"
        self.api_url = self.api_v2_url

        if callable(token_or_provider):
            self._token_provider = token_or_provider
        else:
            self._token_provider = lambda: str(token_or_provider) if token_or_provider else ""

    @property
    def headers(self):
        token = self._token_provider()
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def set_access_token(self, token):
        self._token_provider = lambda: str(token) if token else ""

    def _log_response(self, method: str, url: str, r: requests.Response):
        """Log HTTP response details and nicely formatted JSON using LOGGER.debug."""
        status_code = getattr(r, 'status_code', 'unknown')
        try:
            body = r.json()
            if isinstance(body, (dict, list)):
                formatted = json.dumps(body, indent=2)
                LOGGER.debug(f"NuHeat API [{method}] {url} -> HTTP {status_code}:\n{formatted}")
                return
        except Exception:
            pass

        text = getattr(r, 'text', '') or "(empty body)"
        LOGGER.debug(f"NuHeat API [{method}] {url} -> HTTP {status_code}:\n{text}")

    def _normalize_thermostat(self, stat):
        """
        Normalize v2 ThermostatModel keys to maintain backwards compatibility
        with existing node code expecting v1 property names.
        """
        if not isinstance(stat, dict):
            return stat

        normalized = dict(stat)
        if 'setPointTemperature' in normalized and 'setPointTemp' not in normalized:
            normalized['setPointTemp'] = normalized['setPointTemperature']
        elif 'setPointTemp' in normalized and 'setPointTemperature' not in normalized:
            normalized['setPointTemperature'] = normalized['setPointTemp']

        if 'mode' in normalized and 'operatingMode' not in normalized:
            normalized['operatingMode'] = normalized['mode']

        if 'holdUntil' in normalized and 'holdSetPointDateTime' not in normalized:
            normalized['holdSetPointDateTime'] = normalized['holdUntil']

        if 'errorState' in normalized and 'error' not in normalized:
            normalized['error'] = normalized['errorState']

        return normalized

    def nuheat_celsius_to_fahrenheit(self, json_celsius):
        celsius = json_celsius / 100
        fahrenheit = round((celsius * 9/5) + 32, 0)
        return fahrenheit

    def nuheat_fahrenheit_to_celsius_json(self, fahrenheit):
        celsius = (int(fahrenheit) - 32) * 5/9
        json_celsius = round(celsius * 100)
        return json_celsius

    def nuheat_celsius_to_json(self, celsius):
        json_celsius = int(celsius) * 100
        return json_celsius

    def nuheat_celsius_to_normal(self, json_celsius):
        celsius = round(json_celsius / 100, 0)
        return celsius

    def nuheat_cents_to_dollars(self, cents):
        usd = round(cents / 100, 2)
        return usd

    def get_account(self):
        url = self.api_v2_url + "/Account"
        try:
            r = requests.get(url, headers=self.headers)
            self._log_response("GET", url, r)
            if r.status_code == requests.codes.ok:
                return r.json()
            else:
                LOGGER.error(f"get_account Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_account Error: {e}")
            return None

    def get_thermostat(self, serial_number=None):
        url = self.api_v2_url + "/Thermostat"
        if serial_number:
            url += "/" + str(serial_number)

        try:
            r = requests.get(url, headers=self.headers)
            self._log_response("GET", url, r)
            if r.status_code == requests.codes.ok:
                resp = r.json()
                if isinstance(resp, list):
                    return [self._normalize_thermostat(stat) for stat in resp]
                elif isinstance(resp, dict):
                    return self._normalize_thermostat(resp)
                return resp
            else:
                LOGGER.error(f"get_thermostat Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_thermostat Error: {e}")
            return None

    def set_mode_auto(self, serial_number):
        url = self.api_v2_url + "/Mode/Auto"
        payload = {'serialNumber': str(serial_number)}
        try:
            r = requests.put(url, headers=self.headers, json=payload)
            self._log_response("PUT", url, r)
            if r.status_code in (requests.codes.ok, requests.codes.no_content):
                return True
            else:
                LOGGER.error(f"set_mode_auto Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.set_mode_auto Error: {e}")
            return None

    def set_mode_hold(self, serial_number, temperature, hold_until=None, temperature_type=0):
        url = self.api_v2_url + "/Mode/Hold"
        payload = {
            'serialNumber': str(serial_number),
            'temperature': int(temperature),
            'temperatureType': int(temperature_type)
        }
        if hold_until:
            payload['holdUntil'] = hold_until

        try:
            r = requests.put(url, headers=self.headers, json=payload)
            self._log_response("PUT", url, r)
            if r.status_code in (requests.codes.ok, requests.codes.no_content):
                return True
            else:
                LOGGER.error(f"set_mode_hold Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.set_mode_hold Error: {e}")
            return None

    def set_mode_manual(self, serial_number, temperature, temperature_type=0):
        url = self.api_v2_url + "/Mode/Manual"
        payload = {
            'serialNumber': str(serial_number),
            'temperature': int(temperature),
            'temperatureType': int(temperature_type)
        }

        try:
            r = requests.put(url, headers=self.headers, json=payload)
            self._log_response("PUT", url, r)
            if r.status_code in (requests.codes.ok, requests.codes.no_content):
                return True
            else:
                LOGGER.error(f"set_mode_manual Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.set_mode_manual Error: {e}")
            return None

    def set_thermostat_setpoint(self, serial_number, setpoint, mode="hold"):
        """
        Backwards-compatible setter for thermostat setpoint.
        Routes to v2 Mode endpoints:
        - "hold" (default, corresponds to v1 scheduleMode=2): set_mode_hold
        - "manual": set_mode_manual
        - "auto": set_mode_auto
        """
        if mode == "auto":
            return self.set_mode_auto(serial_number)
        elif mode == "manual":
            return self.set_mode_manual(serial_number, setpoint)
        else:
            return self.set_mode_hold(serial_number, setpoint)

    def _parse_energy_usage(self, resp):
        if not resp or 'energyUsage' not in resp:
            return None

        minutes = 0
        raw_energy_kw_hour = 0
        raw_charge_kw_hour = 0
        for entry in resp['energyUsage']:
            minutes += entry.get('minutes', 0)
            raw_energy_kw_hour += entry.get('energyKWattHour', 0)
            raw_charge_kw_hour += entry.get('chargeKWattHour', 0)

        energy_kw_hour = round(raw_energy_kw_hour, 2)
        cents_charge_kw_hour = round(raw_charge_kw_hour, 2)
        usd_charge_kw_hour = self.nuheat_cents_to_dollars(cents_charge_kw_hour)
        return [minutes, energy_kw_hour, usd_charge_kw_hour]

    def get_energy_log_day(self, serial_number, date):
        energy_log_url = self.api_v1_url + "/EnergyLog/Day/" + str(serial_number) + "/" + str(date)
        try:
            r = requests.get(energy_log_url, headers=self.headers)
            self._log_response("GET", energy_log_url, r)
            if r.status_code == requests.codes.ok:
                return self._parse_energy_usage(r.json())
            else:
                LOGGER.error(f"get_energy_log_day Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_energy_log_day Error: {e}")
            return None

    def get_energy_log_week(self, serial_number, date):
        energy_log_url = self.api_v1_url + "/EnergyLog/Week/" + str(serial_number) + "/" + str(date)
        try:
            r = requests.get(energy_log_url, headers=self.headers)
            self._log_response("GET", energy_log_url, r)
            if r.status_code == requests.codes.ok:
                return self._parse_energy_usage(r.json())
            else:
                LOGGER.error(f"get_energy_log_week Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_energy_log_week Error: {e}")
            return None

    def get_energy_log_year(self, serial_number, date):
        energy_log_url = self.api_v1_url + "/EnergyLog/Month/" + str(serial_number) + "/" + str(date)
        try:
            r = requests.get(energy_log_url, headers=self.headers)
            self._log_response("GET", energy_log_url, r)
            if r.status_code == requests.codes.ok:
                return self._parse_energy_usage(r.json())
            else:
                LOGGER.error(f"get_energy_log_year Error: {r.status_code} - {r.content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_energy_log_year Error: {e}")
            return None
