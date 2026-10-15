import json
import logging
import sys
import time
import requests

try:
    from udi_interface import LOGGER
except ImportError:
    LOGGER = logging.getLogger(__name__)


class NuHeat:
    def __init__(self, token_or_provider, session=None):
        self.api_v2_url = "https://api.mynuheat.com/api/v2"
        self.api_v1_url = "https://api.mynuheat.com/api/v1"
        self.api_url = self.api_v2_url
        self.session = session if session is not None else requests.Session()
        self._day_cache = {}
        self._week_cache = {}
        self._month_cache = {}
        self.timeout = 10

        if callable(token_or_provider):
            self._token_provider = token_or_provider
        else:
            self._token_provider = lambda: str(token_or_provider) if token_or_provider else ""

    def close(self):
        """Close the underlying HTTP session connection pool."""
        if self.session is not None:
            try:
                self.session.close()
            except Exception:
                pass

    def get_token(self, force_refresh: bool = False):
        """Retrieve token from provider, optionally forcing a refresh attempt on 401."""
        if callable(self._token_provider):
            try:
                return self._token_provider(force_refresh=force_refresh)
            except TypeError:
                return self._token_provider()
        return str(self._token_provider) if self._token_provider else ""

    @property
    def headers(self):
        token = self.get_token()
        headers = {'Content-Type': 'application/json'}
        if token:
            headers['Authorization'] = f'Bearer {token}'
        return headers

    def set_access_token(self, token):
        self._token_provider = lambda **kwargs: str(token) if token else ""

    def _request(self, method: str, url: str, max_retries: int = 2, backoff: float = 2.0, **kwargs):
        """
        Executes HTTP requests with session reuse, timeout, logging, and automatic retry for:
        - HTTP 5xx (transient server errors)
        - HTTP 429 (rate limiting, respecting Retry-After header)
        - HTTP 401 (token refresh attempt via _token_provider)
        - Network timeouts and connection drops
        """
        kwargs.setdefault('timeout', self.timeout)

        requester = self.session.request if self.session is not None else requests.request
        last_resp = None
        for attempt in range(max_retries + 1):
            req_headers = dict(self.headers)
            if 'headers' in kwargs and kwargs['headers']:
                req_headers.update(kwargs['headers'])
            call_kwargs = dict(kwargs)
            call_kwargs['headers'] = req_headers

            try:
                r = requester(method, url, **call_kwargs)
                self._log_response(method, url, r)
                last_resp = r

                # Rate Limiting (429)
                if r.status_code == 429 and attempt < max_retries:
                    retry_after = r.headers.get('Retry-After')
                    try:
                        wait_time = float(retry_after) if retry_after else (backoff * (2 ** attempt))
                    except (ValueError, TypeError):
                        wait_time = backoff * (2 ** attempt)
                    LOGGER.warning(
                        f"NuHeat API [{method}] {url} rate limited (HTTP 429). "
                        f"Backing off for {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue

                # Unauthorized / Token Expiration (401)
                if r.status_code == 401 and attempt < max_retries:
                    LOGGER.warning(
                        f"NuHeat API [{method}] {url} returned 401 Unauthorized. "
                        f"Attempting token refresh (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(0.5)
                    fresh_token = self.get_token(force_refresh=True)
                    if not fresh_token:
                        LOGGER.error(f"NuHeat API [{method}] {url}: Token refresh failed or re-authentication required.")
                        return r
                    continue

                # Server Errors (5xx)
                if r.status_code >= 500 and attempt < max_retries:
                    wait_time = backoff * (attempt + 1)
                    LOGGER.warning(
                        f"NuHeat API [{method}] {url} returned {r.status_code}. "
                        f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                    continue

                return r

            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
                if attempt < max_retries:
                    wait_time = backoff * (attempt + 1)
                    LOGGER.warning(
                        f"NuHeat API [{method}] {url} failed with {exc.__class__.__name__}. "
                        f"Retrying in {wait_time:.1f}s (attempt {attempt + 1}/{max_retries})..."
                    )
                    time.sleep(wait_time)
                else:
                    LOGGER.error(f"NuHeat API [{method}] {url} failed after {max_retries + 1} attempts: {exc}")
                    raise
            except requests.exceptions.RequestException as exc:
                LOGGER.error(f"NuHeat API [{method}] {url} request error: {exc}")
                raise

        return last_resp

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
        json_celsius = round(float(celsius) * 100)
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
            r = self._request("GET", url)
            if r is not None and r.status_code == requests.codes.ok:
                return r.json()
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"get_account Error: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_account Error: {e}")
            return None

    def get_thermostat(self, serial_number=None):
        url = self.api_v2_url + "/Thermostat"
        if serial_number:
            url += "/" + str(serial_number)

        try:
            r = self._request("GET", url)
            if r is not None and r.status_code == requests.codes.ok:
                resp = r.json()
                if isinstance(resp, list):
                    return [self._normalize_thermostat(stat) for stat in resp]
                elif isinstance(resp, dict):
                    return self._normalize_thermostat(resp)
                return resp
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"get_thermostat Error: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_thermostat Error: {e}")
            return None

    def set_mode_auto(self, serial_number):
        url = self.api_v2_url + "/Mode/Auto"
        payload = {'serialNumber': str(serial_number)}
        LOGGER.info(f"Setting thermostat {serial_number} to Auto mode (URL: {url}, payload: {payload})")
        try:
            r = self._request("PUT", url, json=payload)
            if r is not None and r.status_code in (requests.codes.ok, requests.codes.no_content):
                LOGGER.info(f"Successfully set thermostat {serial_number} to Auto mode (HTTP {r.status_code})")
                return True
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"set_mode_auto Error for {serial_number}: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.set_mode_auto RequestException for {serial_number}: {e}")
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

        LOGGER.info(f"Setting thermostat {serial_number} to Hold mode (URL: {url}, temp: {temperature}, hold_until: {hold_until}, payload: {payload})")
        try:
            r = self._request("PUT", url, json=payload)
            if r is not None and r.status_code in (requests.codes.ok, requests.codes.no_content):
                LOGGER.info(f"Successfully set thermostat {serial_number} to Hold mode (HTTP {r.status_code})")
                return True
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"set_mode_hold Error for {serial_number}: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.set_mode_hold RequestException for {serial_number}: {e}")
            return None

    def set_mode_manual(self, serial_number, temperature, temperature_type=0):
        url = self.api_v2_url + "/Mode/Manual"
        payload = {
            'serialNumber': str(serial_number),
            'temperature': int(temperature),
            'temperatureType': int(temperature_type)
        }

        LOGGER.info(f"Setting thermostat {serial_number} to Permanent Hold / Manual mode (URL: {url}, temp: {temperature}, payload: {payload})")
        try:
            r = self._request("PUT", url, json=payload)
            if r is not None and r.status_code in (requests.codes.ok, requests.codes.no_content):
                LOGGER.info(f"Successfully set thermostat {serial_number} to Permanent Hold / Manual mode (HTTP {r.status_code})")
                return True
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"set_mode_manual Error for {serial_number}: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.set_mode_manual RequestException for {serial_number}: {e}")
            return None

    def set_thermostat_setpoint(self, serial_number, setpoint, mode="hold"):
        """
        Backwards-compatible setter for thermostat setpoint.
        Routes to v2 Mode endpoints:
        - "hold" (default, corresponds to v1 scheduleMode=2): set_mode_hold
        - "manual": set_mode_manual
        - "auto": set_mode_auto
        """
        LOGGER.info(f"set_thermostat_setpoint called for {serial_number} (setpoint: {setpoint}, mode: '{mode}')")
        if mode == "auto":
            return self.set_mode_auto(serial_number)
        elif mode == "manual":
            return self.set_mode_manual(serial_number, setpoint)
        else:
            return self.set_mode_hold(serial_number, setpoint)

    def _parse_energy_usage(self, resp):
        if not resp or 'energyUsage' not in resp:
            return None

        entries = resp.get('energyUsage')
        if isinstance(entries, dict):
            entries = [entries]
        elif not isinstance(entries, list):
            return None

        minutes = 0
        raw_energy_kw_hour = 0.0
        raw_charge_kw_hour = 0.0
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            minutes += int(entry.get('minutes') or 0)
            raw_energy_kw_hour += float(entry.get('energyKWattHour') or 0.0)
            raw_charge_kw_hour += float(entry.get('chargeKWattHour') or 0.0)

        energy_kw_hour = round(raw_energy_kw_hour, 2)
        cents_charge_kw_hour = round(raw_charge_kw_hour, 2)
        usd_charge_kw_hour = self.nuheat_cents_to_dollars(cents_charge_kw_hour)
        return [minutes, energy_kw_hour, usd_charge_kw_hour]

    def get_energy_log_day(self, serial_number, date, force: bool = False):
        cache_key = (str(serial_number), str(date))
        now = time.time()
        if not force and hasattr(self, '_day_cache') and cache_key in self._day_cache:
            cached_time, cached_result = self._day_cache[cache_key]
            if now - cached_time < 300:
                return cached_result

        energy_log_url = f"{self.api_v1_url}/EnergyLog/Day/{serial_number}/{date}"
        try:
            r = self._request("GET", energy_log_url)
            if r is not None and r.status_code == requests.codes.ok:
                result = self._parse_energy_usage(r.json())
                if result:
                    LOGGER.info(f"NuHeat Day Energy for {serial_number} on {date}: {result[1]} kWh ({result[0]} mins)")
                if not hasattr(self, '_day_cache'):
                    self._day_cache = {}
                self._day_cache[cache_key] = (now, result)
                return result
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"get_energy_log_day Error: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_energy_log_day Error: {e}")
            return None

    def get_energy_log_week(self, serial_number, date, force: bool = False):
        cache_key = (str(serial_number), str(date))
        now = time.time()
        if not force and hasattr(self, '_week_cache') and cache_key in self._week_cache:
            cached_time, cached_result = self._week_cache[cache_key]
            if now - cached_time < 300:
                return cached_result

        energy_log_url = f"{self.api_v1_url}/EnergyLog/Week/{serial_number}/{date}"
        try:
            r = self._request("GET", energy_log_url)
            if r is not None and r.status_code == requests.codes.ok:
                result = self._parse_energy_usage(r.json())
                if result:
                    LOGGER.info(f"NuHeat Week Energy for {serial_number} up to {date}: {result[1]} kWh ({result[0]} mins)")
                if not hasattr(self, '_week_cache'):
                    self._week_cache = {}
                self._week_cache[cache_key] = (now, result)
                return result
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"get_energy_log_week Error: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat.get_energy_log_week Error: {e}")
            return None

    def _fetch_energy_log_month(self, serial_number, year, force: bool = False):
        cache_key = (str(serial_number), str(year))
        now = time.time()
        if not force and hasattr(self, '_month_cache') and cache_key in self._month_cache:
            cached_time, cached_json = self._month_cache[cache_key]
            if now - cached_time < 300:
                return cached_json

        energy_log_url = f"{self.api_v1_url}/EnergyLog/Month/{serial_number}/{year}"
        try:
            r = self._request("GET", energy_log_url)
            if r is not None and r.status_code == requests.codes.ok:
                data = r.json()
                if not hasattr(self, '_month_cache'):
                    self._month_cache = {}
                self._month_cache[cache_key] = (now, data)
                return data
            else:
                code = getattr(r, 'status_code', 'unknown')
                content = getattr(r, 'content', b'')
                LOGGER.error(f"EnergyLog Month Error: {code} - {content}")
                return None
        except requests.exceptions.RequestException as e:
            LOGGER.error(f"NuHeat EnergyLog Month Error: {e}")
            return None

    def get_energy_log_month(self, serial_number, year, month, force: bool = False):
        resp = self._fetch_energy_log_month(serial_number, year, force=force)
        if not resp or 'energyUsage' not in resp:
            return None

        try:
            m_int = int(month)
        except (TypeError, ValueError):
            m_int = 1

        target_1based = {str(m_int), f"{m_int:02d}"}
        target_0based = {str(m_int - 1), f"{(m_int - 1):02d}"}

        entries = resp.get('energyUsage')
        if isinstance(entries, dict):
            entries = [entries]
        elif not isinstance(entries, list):
            entries = []

        # 1-based matching (e.g. "9" for September)
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            e_str = str(entry.get('entry', '')).strip()
            if e_str in target_1based:
                minutes = int(entry.get('minutes') or 0)
                raw_kwh = float(entry.get('energyKWattHour') or 0.0)
                raw_charge = float(entry.get('chargeKWattHour') or 0.0)
                energy_kw_hour = round(raw_kwh, 2)
                cents_charge = round(raw_charge, 2)
                usd_charge = self.nuheat_cents_to_dollars(cents_charge)
                LOGGER.info(f"NuHeat Month Energy for {serial_number} (Month {month}/{year}): {energy_kw_hour} kWh")
                return [minutes, energy_kw_hour, usd_charge]

        # Fallback 0-based matching
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            e_str = str(entry.get('entry', '')).strip()
            if e_str in target_0based:
                minutes = int(entry.get('minutes') or 0)
                raw_kwh = float(entry.get('energyKWattHour') or 0.0)
                raw_charge = float(entry.get('chargeKWattHour') or 0.0)
                energy_kw_hour = round(raw_kwh, 2)
                cents_charge = round(raw_charge, 2)
                usd_charge = self.nuheat_cents_to_dollars(cents_charge)
                LOGGER.info(f"NuHeat Month Energy for {serial_number} (Month {month}/{year}, 0-based): {energy_kw_hour} kWh")
                return [minutes, energy_kw_hour, usd_charge]

        LOGGER.warning(f"NuHeat Month {month} not found for {serial_number} in year {year}")
        return [0, 0.0, 0.0]

    def get_energy_log_year(self, serial_number, year, force: bool = False):
        resp = self._fetch_energy_log_month(serial_number, year, force=force)
        if resp is not None:
            result = self._parse_energy_usage(resp)
            if result:
                LOGGER.info(f"NuHeat Year Energy for {serial_number} for {year}: {result[1]} kWh ({result[0]} mins)")
            return result
        return None

    def get_energy_summary(self, serial_number, date_str, year_str, month_num, force: bool = False):
        """
        Retrieves Day, Week, Month, and Year energy usage and returns a convenient summary dictionary.
        """
        day_used = self.get_energy_log_day(serial_number, date_str, force=force)
        week_used = self.get_energy_log_week(serial_number, date_str, force=force)
        month_used = self.get_energy_log_month(serial_number, year_str, month_num, force=force)
        year_used = self.get_energy_log_year(serial_number, year_str, force=force)

        return {
            'day': day_used[1] if day_used else 0.0,
            'week': week_used[1] if week_used else 0.0,
            'month': month_used[1] if month_used else 0.0,
            'year': year_used[1] if year_used else 0.0,
            'day_data': day_used,
            'week_data': week_used,
            'month_data': month_used,
            'year_data': year_used,
        }
