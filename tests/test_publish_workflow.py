import os
import sys
import tempfile
import time
import unittest


class PublishWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = os.path.join(cls._tmpdir.name, "test.db")
        os.environ["DB_URL"] = f"sqlite:///{cls._db_path}"

        import importlib

        sys.modules.pop("app", None)
        cls.appmod = importlib.import_module("app")
        cls.app = cls.appmod.app
        cls.db = cls.appmod.db
        try:
            cls.appmod.db.engine.dispose()
        except Exception:
            pass

        cls.app.config["TESTING"] = True

    @classmethod
    def tearDownClass(cls):
        try:
            cls.db.session.remove()
            cls.db.engine.dispose()
        except Exception:
            pass

        try:
            for _ in range(5):
                try:
                    cls._tmpdir.cleanup()
                    break
                except PermissionError:
                    time.sleep(0.05)
        except Exception:
            pass

    def setUp(self):
        with self.app.app_context():
            self.db.drop_all()
            self.db.create_all()
            self.appmod.ensure_schema()

            admin = self.appmod.User(
                username="admin",
                email="admin@example.com",
                full_name="Admin",
                role="admin",
                is_admin=True,
                is_active=True,
            )
            admin.set_password("pw")
            field = self.appmod.User(
                username="field",
                email="field@example.com",
                full_name="Field",
                role="field",
                is_admin=False,
                is_active=True,
            )
            field.set_password("pw")
            self.db.session.add_all([admin, field])
            self.db.session.commit()

            proj = self.appmod.Project(
                region="Istanbul",
                project_code="P1",
                project_name="Proj",
                responsible="Resp",
                is_active=True,
            )
            self.db.session.add(proj)
            self.db.session.commit()

            self.admin_id = admin.id
            self.field_id = field.id
            self.project_id = proj.id

            from datetime import date

            cell = self.appmod.PlanCell(
                project_id=proj.id,
                work_date=date.today(),
                note="Test",
                assigned_user_id=field.id,
            )
            self.db.session.add(cell)
            self.db.session.commit()

    def _login_as(self, client, user_id):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = "x"
            sess["is_admin"] = (user_id == self.admin_id)
            sess["role"] = ("admin" if user_id == self.admin_id else "field")
            sess["_csrf_token"] = "t"

    def test_draft_invisible_then_visible_after_publish(self):
        client = self.app.test_client()

        self._login_as(client, self.field_id)
        res = client.get("/me")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"/me/job/", res.data)

        self._login_as(client, self.admin_id)
        res = client.post("/admin/publish/week", json={"week_start": self.appmod.iso(self.appmod.week_start(self.appmod.date.today())), "csrf_token": "t"})
        self.assertEqual(res.status_code, 200)

        self._login_as(client, self.field_id)
        res = client.get("/me")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"/me/job/", res.data)
