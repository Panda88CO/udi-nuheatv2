import sys
import requests


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
        try:
            r = requests.get(self.api_v2_url + "/Account", headers=self.headers)
            if r.status_code == requests.codes.ok:
                return r.json()
            else:
                print("get_account Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.get_account Error: " + str(e))
            return None

    def get_thermostat(self, serial_number=None):
        url = self.api_v2_url + "/Thermostat"
        if serial_number:
            url += "/" + str(serial_number)

        try:
            r = requests.get(url, headers=self.headers)
            if r.status_code == requests.codes.ok:
                resp = r.json()
                if isinstance(resp, list):
                    return [self._normalize_thermostat(stat) for stat in resp]
                elif isinstance(resp, dict):
                    return self._normalize_thermostat(resp)
                return resp
            else:
                print("get_thermostat Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.get_thermostat Error: " + str(e))
            return None

    def set_mode_auto(self, serial_number):
        url = self.api_v2_url + "/Mode/Auto"
        payload = {'serialNumber': str(serial_number)}
        try:
            r = requests.put(url, headers=self.headers, json=payload)
            if r.status_code in (requests.codes.ok, requests.codes.no_content):
                return True
            else:
                print("set_mode_auto Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.set_mode_auto Error: " + str(e))
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
            if r.status_code in (requests.codes.ok, requests.codes.no_content):
                return True
            else:
                print("set_mode_hold Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.set_mode_hold Error: " + str(e))
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
            if r.status_code in (requests.codes.ok, requests.codes.no_content):
                return True
            else:
                print("set_mode_manual Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.set_mode_manual Error: " + str(e))
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
            if r.status_code == requests.codes.ok:
                return self._parse_energy_usage(r.json())
            else:
                print("get_energy_log_day Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.get_energy_log_day Error: " + str(e))
            return None

    def get_energy_log_week(self, serial_number, date):
        energy_log_url = self.api_v1_url + "/EnergyLog/Week/" + str(serial_number) + "/" + str(date)
        try:
            r = requests.get(energy_log_url, headers=self.headers)
            if r.status_code == requests.codes.ok:
                return self._parse_energy_usage(r.json())
            else:
                print("get_energy_log_week Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.get_energy_log_week Error: " + str(e))
            return None

    def get_energy_log_year(self, serial_number, date):
        energy_log_url = self.api_v1_url + "/EnergyLog/Month/" + str(serial_number) + "/" + str(date)
        try:
            r = requests.get(energy_log_url, headers=self.headers)
            if r.status_code == requests.codes.ok:
                return self._parse_energy_usage(r.json())
            else:
                print("get_energy_log_year Error: " + str(r.status_code) + " - " + str(r.content))
                return None
        except requests.exceptions.RequestException as e:
            print("NuHeat.get_energy_log_year Error: " + str(e))
            return None
