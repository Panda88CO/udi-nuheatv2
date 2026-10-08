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
        self.start_time = int(time.time())

    def start(self):
        if not hasattr(self, 'start_time') or self.start_time is None:
            self.start_time = int(time.time())
        self.update_info()

    def update_info(self):
        nuheat_client = getattr(self.controller, 'NuHeat', None)
        if nuheat_client is None:
            LOGGER.error("NuHeat client not available on controller")
            return False

        tz_name = getattr(self.controller, 'tz', 'America/New_York')
        try:
            date_str = datetime.now(pytz.timezone(tz_name)).strftime('%Y-%m-%d')
        except Exception:
            date_str = datetime.now(pytz.timezone('America/New_York')).strftime('%Y-%m-%d')

        stat_id = getattr(self, 'stat_address', self.primary)
        try:
            energy_used = nuheat_client.get_energy_log_day(stat_id, date_str)
        except Exception as e:
            LOGGER.error(f"Error fetching day energy for {stat_id}: {e}")
            energy_used = None

        if energy_used is not None and isinstance(energy_used, (list, tuple)) and len(energy_used) > 1:
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
            self.setDriver('TIME', get_current_timestamp(time_uom, getattr(self, 'start_time', None)), uom=time_uom)
            return True
        else:
            LOGGER.error(f"Energy Log Day returned None for {stat_id}")
            return False

    def query(self, command=None):
        self.reportDrivers()

    commands = {'QUERY': query}
