from .base import LOGGER, BaseNode


class ThermostatNode_F(BaseNode):
    def __init__(self, polyglot, primary, address, name, controller=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(ThermostatNode_F, self).__init__(polyglot, primary, address, name)
        self.controller = controller
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

            self.setDriver('ST', clitemp)
            self.setDriver('CLISPH', clisph)
            self.setDriver('CLIMD', climd)
            self.setDriver('CLIHCS', clihcs)
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
            self.setDriver('CLISPH', val)
        else:
            LOGGER.error(f"thermostat_node.setpoint_heat failed for {self.address}")

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 17},
        {'driver': 'CLISPH', 'value': 0, 'uom': 17},
        {'driver': 'CLIMD', 'value': 0, 'uom': 67},
        {'driver': 'CLIHCS', 'value': 0, 'uom': 66}
    ]

    id = 'THERMOSTAT_F'

    commands = {
        'QUERY': query,
        'CLISPH': setpoint_heat
    }


class ThermostatNode_C(BaseNode):
    def __init__(self, polyglot, primary, address, name, controller=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(ThermostatNode_C, self).__init__(polyglot, primary, address, name)
        self.controller = controller
        self.temp_uom = 4

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

            self.setDriver('ST', clitemp)
            self.setDriver('CLISPH', clisph)
            self.setDriver('CLIMD', climd)
            self.setDriver('CLIHCS', clihcs)
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
            self.setDriver('CLISPH', val)
        else:
            LOGGER.error(f"thermostat_node.setpoint_heat failed for {self.address}")

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 4},
        {'driver': 'CLISPH', 'value': 0, 'uom': 4},
        {'driver': 'CLIMD', 'value': 0, 'uom': 67},
        {'driver': 'CLIHCS', 'value': 0, 'uom': 66}
    ]

    id = 'THERMOSTAT_C'

    commands = {
        'QUERY': query,
        'CLISPH': setpoint_heat
    }

