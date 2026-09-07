from .base import LOGGER, BaseNode

import pytz
from datetime import datetime


class EnergyLogDayNode(BaseNode):
    def __init__(self, polyglot, primary, address, name, controller=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(EnergyLogDayNode, self).__init__(polyglot, primary, address, name)
        self.controller = controller

    def start(self):
        self.update_info()

    def update_info(self):
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return

        tz_name = getattr(self.controller, 'tz', 'America/New_York')
        try:
            date_str = datetime.now(pytz.timezone(tz_name)).strftime('%Y-%m-%d')
        except Exception:
            date_str = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')

        energy_used = nuheat_client.get_energy_log_day(self.primary, date_str)
        if energy_used is not None:
            self.setDriver('GV0', energy_used[0], uom=45)
            self.setDriver('ST', energy_used[1], uom=33)
            self.setDriver('GV1', energy_used[2], uom=103)
        else:
            LOGGER.error(f"Energy Log Day returned None for {self.primary}")

    def query(self, command=None):
        self.reportDrivers()

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 45},
        {'driver': 'ST', 'value': 0, 'uom': 33},
        {'driver': 'GV1', 'value': 0, 'uom': 103}
    ]

    id = 'ENERGYLOG'

    commands = {'QUERY': query}

