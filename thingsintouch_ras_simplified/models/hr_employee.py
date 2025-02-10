# Copyright 2022 thingsintouch.com
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from odoo import api, models

from datetime import datetime

import freezegun


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    @api.model
    def register_attendance_async(self, card_code, timestamp):
        with freezegun.freeze_time(datetime.fromtimestamp(int(timestamp), tz=None)):
            result = self.register_attendance(card_code)
        return result
