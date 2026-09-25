import time
from datetime import datetime
import pytz

from .base import LOGGER, BaseNode, get_current_timestamp


class EnergyLogDayNode(BaseNode):
    id = 'ENERGYLOG'

    drivers = [
        {'driver': 'GV0', 'value': 0, 'uom': 45},
        {'driver': 'ST', 'value': 0, 'uom': 33},
        {'driver': 'TIME', 'value': 0, 'uom': 151}
    ]

    def __init__(self, polyglot, primary, address, name, controller=None):
        if controller is None and hasattr(polyglot, 'poly'):
            controller = polyglot
            polyglot = polyglot.poly
        super(EnergyLogDayNode, self).__init__(polyglot, primary, address, name)
        self.controller = controller
        self.stat_address = address[3:] if address.startswith('eld') else primary

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

        stat_id = getattr(self, 'stat_address', self.primary)
        energy_used = nuheat_client.get_energy_log_day(stat_id, date_str)
        if energy_used is not None:
            self.setDriver('GV0', energy_used[0], uom=45)
            self.setDriver('ST', energy_used[1], uom=33)
            time_uom = 151
            if self.controller and hasattr(self.controller, 'time_uom'):
                val = getattr(self.controller, 'time_uom', None)
                if isinstance(val, (int, str)):
                    try:
                        time_uom = int(val)
                    except (ValueError, TypeError):
                        time_uom = 151
            self.setDriver('TIME', get_current_timestamp(time_uom), uom=time_uom)
        else:
            LOGGER.error(f"Energy Log Day returned None for {stat_id}")

    def query(self, command=None):
        self.reportDrivers()

    commands = {'QUERY': query}
