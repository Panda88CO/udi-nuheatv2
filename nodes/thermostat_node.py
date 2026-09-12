import time
from .base import LOGGER, BaseNode


class ThermostatNode(BaseNode):
    id = 'THERMOSTAT'

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 17},
        {'driver': 'CLISPH', 'value': 0, 'uom': 17},
        {'driver': 'CLIMD', 'value': 0, 'uom': 67},
        {'driver': 'CLIHCS', 'value': 0, 'uom': 66},
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

    def start(self):
        self.update_info()

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

            mode_val = stat.get('mode', stat.get('operatingMode', 1))
            if mode_val == 1:
                climd = 3  # Auto
            else:
                climd = 1  # Heat / Hold / Manual

            clihcs = 1 if stat.get('isHeating') else 0

            self.setDriver('ST', clitemp, uom=self.temp_uom)
            self.setDriver('CLISPH', clisph, uom=self.temp_uom)
            self.setDriver('CLIMD', climd, uom=67)
            self.setDriver('CLIHCS', clihcs, uom=66)
            self.setDriver('TIME', int(time.time()), uom=151)
        else:
            LOGGER.error(f"Thermostat {self.address} not available or returned None")

    def query(self, command=None):
        self.reportDrivers()

    def setpoint_heat(self, command):
        val = int(command['value'])
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return

        if self.temp_uom == 17:
            new_setpoint = nuheat_client.nuheat_fahrenheit_to_celsius_json(val)
        else:
            new_setpoint = nuheat_client.nuheat_celsius_to_json(val)

        _status = nuheat_client.set_thermostat_setpoint(self.address, new_setpoint)
        if _status is not None:
            self.setDriver('CLISPH', val, uom=self.temp_uom)
            self.setDriver('TIME', int(time.time()), uom=151)
        else:
            LOGGER.error(f"thermostat_node.setpoint_heat failed for {self.address}")

    commands = {
        'QUERY': query,
        'CLISPH': setpoint_heat
    }


# Backwards compatibility aliases
ThermostatNode_F = ThermostatNode
ThermostatNode_C = ThermostatNode
