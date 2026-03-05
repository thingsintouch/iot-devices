# Copyright 2022 thingsintouch.com
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html
from odoo import api, models
from datetime import datetime, timezone
import freezegun

class HrEmployee(models.Model):
    _inherit = "hr.employee"
    @api.model
    def register_attendance_async(self, card_code, timestamp):
        frozen_dt = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).replace(tzinfo=None)
        with freezegun.freeze_time(frozen_dt):
            result = self.register_attendance(card_code)
        return result
