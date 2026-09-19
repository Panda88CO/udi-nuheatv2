import time
from datetime import datetime, timezone, timedelta
import pytz

from .base import LOGGER, BaseNode


def _get_param(command, param_name, default=None):
    if not isinstance(command, dict):
        return default
    query = command.get("query")
    if isinstance(query, dict):
        if param_name in query:
            return query[param_name]
        # When command parameter id in nodedefs.xml is empty (id=""), PG3 passes query keys like '' or '.uom17'
        if "" in query:
            return query[""]
        for k, v in query.items():
            if k == "uom":
                continue
            if k.startswith(".uom"):
                return v
            if k.startswith(f"{param_name}."):
                return v
            if param_name == "temp" and "temp" in k.lower():
                return v
    if param_name in command:
        return command[param_name]
    if "" in command:
        return command[""]
    # Single-parameter commands (like SET_PERM_HOLD with id="") deliver their parameter in command['value']
    if param_name == "temp" and "value" in command and command["value"] is not None:
        if str(command.get("uom")) != "25" and command.get("cmd") != "CLIMD":
            return command["value"]
    for k, v in command.items():
        if k in ("address", "cmd", "uom", "query", "value"):
            continue
        if k.startswith(".uom"):
            return v
        if k.startswith(f"{param_name}."):
            return v
        if param_name == "temp" and "temp" in k.lower():
            return v
    return default


class ThermostatNode(BaseNode):
    id = 'THERMOSTAT_F'

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 17},
        {'driver': 'CLISPH', 'value': 0, 'uom': 17},
        {'driver': 'CLIMD', 'value': 1, 'uom': 25},
        {'driver': 'CLIHCS', 'value': 0, 'uom': 66},
        {'driver': 'GV0', 'value': 0, 'uom': 33},
        {'driver': 'GV1', 'value': 0, 'uom': 33},
        {'driver': 'GV2', 'value': 0, 'uom': 33},
        {'driver': 'GV3', 'value': 0, 'uom': 33},
        {'driver': 'GV4', 'value': 0, 'uom': 25},
        {'driver': 'GV5', 'value': 1, 'uom': 2},
        {'driver': 'TIME', 'value': 0, 'uom': 151}
    ]

    def __init__(self, polyglot, primary, address, name, controller=None, temp_uom=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(ThermostatNode, self).__init__(polyglot, primary, address, name)
        self.controller = controller

        if temp_uom is not None:
            self.temp_uom = int(temp_uom)
        elif controller and hasattr(controller, 'temp_uom'):
            self.temp_uom = int(controller.temp_uom)
        else:
            self.temp_uom = 17

        if self.temp_uom == 4 and getattr(self, 'id', None) == 'THERMOSTAT_F':
            self.id = 'THERMOSTAT_C'
            self.drivers = [
                {'driver': 'ST', 'value': 0, 'uom': 4},
                {'driver': 'CLISPH', 'value': 0, 'uom': 4},
                {'driver': 'CLIMD', 'value': 1, 'uom': 25},
                {'driver': 'CLIHCS', 'value': 0, 'uom': 66},
                {'driver': 'GV0', 'value': 0, 'uom': 33},
                {'driver': 'GV1', 'value': 0, 'uom': 33},
                {'driver': 'GV2', 'value': 0, 'uom': 33},
                {'driver': 'GV3', 'value': 0, 'uom': 33},
                {'driver': 'GV4', 'value': 0, 'uom': 25},
                {'driver': 'GV5', 'value': 1, 'uom': 2},
                {'driver': 'TIME', 'value': 0, 'uom': 151}
            ]

    def start(self):
        self.update_info()
        self.update_energy()

    def update_info(self):
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return

        stat = nuheat_client.get_thermostat(self.address)
        if isinstance(stat, list):
            found = None
            for s in stat:
                if str(s.get('serialNumber')) == str(self.address):
                    found = s
                    break
            stat = found

        if stat is not None:
            raw_cur = stat.get('currentTemperature', 0)
            raw_sp = stat.get('setPointTemperature', stat.get('setPointTemp', 0))

            if self.temp_uom == 17:
                clitemp = nuheat_client.nuheat_celsius_to_fahrenheit(raw_cur)
                clisph = nuheat_client.nuheat_celsius_to_fahrenheit(raw_sp)
            else:
                clitemp = nuheat_client.nuheat_celsius_to_normal(raw_cur)
                clisph = nuheat_client.nuheat_celsius_to_normal(raw_sp)

            clihcs = 1 if stat.get('isHeating') else 0
            self.setDriver('ST', clitemp, uom=self.temp_uom)
            self.setDriver('CLIHCS', clihcs, uom=66)

            mode_val = stat.get('mode', stat.get('operatingMode', 1))
            hold_until = stat.get('holdUntil') or stat.get('holdSetPointDateTime')

            if mode_val == 1:
                # Auto (Follow Schedule)
                self.setDriver('CLIMD', 1, uom=25)
                self.setDriver('CLISPH', clisph, uom=self.temp_uom)
                self.setDriver('GV4', 0, uom=25)
            elif mode_val == 2:
                # Temporary Hold
                self.setDriver('CLIMD', 2, uom=25)
                self.setDriver('CLISPH', clisph, uom=self.temp_uom)
                hold_end_ts = None
                if hold_until:
                    try:
                        clean_str = str(hold_until).replace('Z', '+00:00')
                        target_dt = datetime.fromisoformat(clean_str)
                        hold_end_ts = int(target_dt.timestamp())
                    except Exception as e:
                        LOGGER.warning(f"Could not parse holdUntil '{hold_until}': {e}")
                if hold_end_ts is not None and hold_end_ts > 0:
                    self.setDriver('GV4', hold_end_ts, uom=151)
                else:
                    self.setDriver('GV4', 0, uom=25)
            else:
                # 3 = Permanent Hold (Manual) - hold duration is permanent
                self.setDriver('CLIMD', 3, uom=25)
                self.setDriver('CLISPH', clisph, uom=self.temp_uom)
                self.setDriver('GV4', 1, uom=25)

            online_val = 1 if stat.get('online', True) else 0
            self.setDriver('GV5', online_val, uom=2)

            self.setDriver('TIME', int(time.time()), uom=151)
        else:
            LOGGER.error(f"Thermostat {self.address} not available or returned None")
            self.setDriver('GV5', 0, uom=2)
            self.setDriver('TIME', int(time.time()), uom=151)

    def update_energy(self, force: bool = False):
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return

        tz_name = getattr(self.controller, 'tz', 'America/New_York')
        try:
            now = datetime.now(pytz.timezone(tz_name))
        except Exception:
            now = datetime.now(pytz.timezone('America/New_York'))

        date_str = now.strftime('%Y-%m-%d')
        year_str = str(now.year)
        month_num = now.month

        LOGGER.info(
            f"Retrieving energy data for thermostat {self.address} ({self.name}): "
            f"Date={date_str}, Month={month_num}, Year={year_str} (tz={tz_name})"
        )

        # Daily Energy (GV0)
        day_used = nuheat_client.get_energy_log_day(self.address, date_str)
        day_val = day_used[1] if day_used is not None else 0.0
        self.setDriver('GV0', day_val, uom=33)

        # Last 7 Days Energy (GV1)
        week_used = nuheat_client.get_energy_log_week(self.address, date_str)
        week_val = week_used[1] if week_used is not None else 0.0
        self.setDriver('GV1', week_val, uom=33)

        # Monthly Energy (GV2)
        month_used = nuheat_client.get_energy_log_month(self.address, year_str, month_num, force=force)
        month_val = month_used[1] if month_used is not None else 0.0
        self.setDriver('GV2', month_val, uom=33)

        # Yearly Energy (GV3)
        year_used = nuheat_client.get_energy_log_year(self.address, year_str, force=force)
        year_val = year_used[1] if year_used is not None else 0.0
        self.setDriver('GV3', year_val, uom=33)

        self.setDriver('TIME', int(time.time()), uom=151)

        LOGGER.info(
            f"Thermostat {self.address} ({self.name}) Energy Updated -> "
            f"Daily (GV0): {day_val} kWh, 7-Day (GV1): {week_val} kWh, "
            f"Monthly (GV2): {month_val} kWh, Yearly (GV3): {year_val} kWh"
        )

    def force_update(self, command=None):
        LOGGER.info(f"Updating thermostat {self.address} ({self.name})...")
        self.update_info()
        self.update_energy(force=True)
        self.reportDrivers()

    def set_auto(self, command=None):
        """Set thermostat to Auto mode (Follow Schedule). Takes no parameters."""
        LOGGER.info(f"ThermostatNode.set_auto called for {self.address}")
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return False

        ok = nuheat_client.set_mode_auto(self.address)
        if ok:
            self.setDriver('CLIMD', 1, uom=25)
            self.setDriver('GV4', 0, uom=25)
            self.setDriver('TIME', int(time.time()), uom=151)
            return True
        else:
            LOGGER.error(f"set_mode_auto failed for {self.address}")
            return False

    def set_permanent_hold(self, command=None):
        """Set thermostat to Permanent Hold (Manual). Takes target temperature."""
        LOGGER.info(f"ThermostatNode.set_permanent_hold called for {self.address} with {command}")
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return False

        raw_temp = _get_param(command, "temp", command.get("value") if isinstance(command, dict) else None)
        if raw_temp is not None:
            try:
                temp = float(raw_temp)
            except (TypeError, ValueError):
                temp = 72 if self.temp_uom == 17 else 22
        else:
            curr_sp = self.getDriver('CLISPH')
            curr_val = curr_sp.get('value') if isinstance(curr_sp, dict) else None
            try:
                temp = float(curr_val) if curr_val not in (None, 97, '97', -1, '-1', 0, '0') else (72 if self.temp_uom == 17 else 22)
            except (TypeError, ValueError):
                temp = 72 if self.temp_uom == 17 else 22

        if self.temp_uom == 17:
            new_setpoint = nuheat_client.nuheat_fahrenheit_to_celsius_json(temp)
        else:
            new_setpoint = nuheat_client.nuheat_celsius_to_json(temp)

        ok = nuheat_client.set_mode_manual(self.address, new_setpoint)
        if ok:
            self.setDriver('CLIMD', 3, uom=25)
            self.setDriver('CLISPH', temp, uom=self.temp_uom)
            self.setDriver('GV4', 1, uom=25)
            self.setDriver('TIME', int(time.time()), uom=151)
            return True
        else:
            LOGGER.error(f"set_mode_manual failed for {self.address}")
            return False

    def set_hold(self, command=None):
        """Set thermostat to Temporary Hold. Takes target temperature and hold duration in minutes."""
        LOGGER.info(f"ThermostatNode.set_hold called for {self.address} with {command}")
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return False

        raw_temp = _get_param(command, "temp", command.get("value") if isinstance(command, dict) else None)
        raw_hold = _get_param(command, "hold")

        if raw_temp is not None:
            try:
                temp = float(raw_temp)
            except (TypeError, ValueError):
                temp = 72 if self.temp_uom == 17 else 22
        else:
            curr_sp = self.getDriver('CLISPH')
            curr_val = curr_sp.get('value') if isinstance(curr_sp, dict) else None
            try:
                temp = float(curr_val) if curr_val not in (None, 97, '97', -1, '-1', 0, '0') else (72 if self.temp_uom == 17 else 22)
            except (TypeError, ValueError):
                temp = 72 if self.temp_uom == 17 else 22

        try:
            hold_val = int(raw_hold) if raw_hold is not None else 60
        except (TypeError, ValueError):
            hold_val = 60

        now_utc = datetime.now(timezone.utc)
        if hold_val > 100000:
            stop_utc = datetime.fromtimestamp(hold_val, timezone.utc)
        else:
            if hold_val <= 0:
                hold_val = 60
            stop_utc = now_utc + timedelta(minutes=hold_val)

        hold_until_str = stop_utc.strftime('%Y-%m-%dT%H:%M:%SZ')
        hold_end_ts = int(stop_utc.timestamp())

        if self.temp_uom == 17:
            new_setpoint = nuheat_client.nuheat_fahrenheit_to_celsius_json(temp)
        else:
            new_setpoint = nuheat_client.nuheat_celsius_to_json(temp)

        ok = nuheat_client.set_mode_hold(self.address, new_setpoint, hold_until=hold_until_str)
        if ok:
            self.setDriver('CLIMD', 2, uom=25)
            self.setDriver('CLISPH', temp, uom=self.temp_uom)
            self.setDriver('GV4', hold_end_ts, uom=151)
            self.setDriver('TIME', int(time.time()), uom=151)
            return True
        else:
            LOGGER.error(f"set_mode_hold failed for {self.address}")
            return False

    commands = {
        'UPDATE': force_update,
        'SET_AUTO': set_auto,
        'SET_HOLD': set_hold,
        'SET_PERM_HOLD': set_permanent_hold,
    }


class ThermostatNode_F(ThermostatNode):
    id = 'THERMOSTAT_F'
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 17},
        {'driver': 'CLISPH', 'value': 0, 'uom': 17},
        {'driver': 'CLIMD', 'value': 1, 'uom': 25},
        {'driver': 'CLIHCS', 'value': 0, 'uom': 66},
        {'driver': 'GV0', 'value': 0, 'uom': 33},
        {'driver': 'GV1', 'value': 0, 'uom': 33},
        {'driver': 'GV2', 'value': 0, 'uom': 33},
        {'driver': 'GV3', 'value': 0, 'uom': 33},
        {'driver': 'GV4', 'value': 0, 'uom': 25},
        {'driver': 'GV5', 'value': 1, 'uom': 2},
        {'driver': 'TIME', 'value': 0, 'uom': 151}
    ]

    def __init__(self, polyglot, primary, address, name, controller=None, temp_uom=17):
        super(ThermostatNode_F, self).__init__(polyglot, primary, address, name, controller=controller, temp_uom=17)


class ThermostatNode_C(ThermostatNode):
    id = 'THERMOSTAT_C'
    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 4},
        {'driver': 'CLISPH', 'value': 0, 'uom': 4},
        {'driver': 'CLIMD', 'value': 1, 'uom': 25},
        {'driver': 'CLIHCS', 'value': 0, 'uom': 66},
        {'driver': 'GV0', 'value': 0, 'uom': 33},
        {'driver': 'GV1', 'value': 0, 'uom': 33},
        {'driver': 'GV2', 'value': 0, 'uom': 33},
        {'driver': 'GV3', 'value': 0, 'uom': 33},
        {'driver': 'GV4', 'value': 0, 'uom': 25},
        {'driver': 'GV5', 'value': 1, 'uom': 2},
        {'driver': 'TIME', 'value': 0, 'uom': 151}
    ]

    def __init__(self, polyglot, primary, address, name, controller=None, temp_uom=4):
        super(ThermostatNode_C, self).__init__(polyglot, primary, address, name, controller=controller, temp_uom=4)

