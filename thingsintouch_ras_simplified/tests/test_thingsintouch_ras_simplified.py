import time
from odoo.tests.common import HttpCase
from odoo.tests import new_test_user

from odoo.addons.base.tests.common import DISABLED_MAIL_CONTEXT


class TestThingsintouchRasSimplified(HttpCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(context=dict(cls.env.context, **DISABLED_MAIL_CONTEXT))
        user = new_test_user(
            cls.env,
            login="ras_rfid-user",
            groups="hr_attendance_rfid.group_hr_attendance_rfid,base.group_user",
        )
        cls.rfid_card_code = "5b3f5"
        cls.device_serial_number = "ABC00001"
        cls.env["hr.employee"].create(
            {"user_id": user.id, "rfid_card_code": cls.rfid_card_code}
        )
        cls.employee_model = cls.env["hr.employee"]
        cls.device_modal = cls.env["iot.device"]
        cls.template = cls.env.ref(
            "thingsintouch_ras_simplified.ras_simplified_template"
        )

    def action_request(self, device_input):
        url = f"/iot/{device_input.serial}/action"
        data = {
            "passphrase": device_input.passphrase,
            "card_code": self.rfid_card_code,
            "timestamp": round(time.time()),
        }
        return self.url_open(url, data).json()

    def test_01_device_register_with_template_and_action(self):
        wizard = self.env["iot.device.configure"].create(
            {"serial": self.device_serial_number}
        )
        device_config = self.url_open(
            wizard.url,
            data={"template": self.template.name},
        ).json()
        device = self.device_modal.search([("name", "=", device_config["name"])])
        self.assertTrue(device)
        self.assertEqual(1, len(device))
        self.assertEqual(1, len(device.input_ids))
        self.assertEqual(0, len(device.output_ids))
        device_input = device.input_ids
        # action login
        res = self.action_request(device_input)
        self.assertTrue("action" in res and res["action"] == "check_in")
        self.assertTrue("logged" in res and res["logged"])
        self.assertTrue(
            "rfid_card_code" in res and res["rfid_card_code"] == self.rfid_card_code
        )
        # action login
        res = self.action_request(device_input)
        self.assertTrue("action" in res and res["action"] == "check_out")
        self.assertTrue("logged" in res and res["logged"])
