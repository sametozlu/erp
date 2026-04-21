import os
import sys
import tempfile
import time
import unittest


class OperationalBoardTests(unittest.TestCase):
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

            from datetime import date

            cell = self.appmod.PlanCell(
                project_id=proj.id,
                work_date=date.today(),
                note="Test board",
            )
            self.db.session.add(cell)
            self.db.session.commit()

            self.admin_id = admin.id
            self.field_id = field.id
            self.project_id = proj.id
            self.cell_id = cell.id

    def _login_as(self, client, user_id, *, role):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = "x"
            sess["is_admin"] = (role == "admin")
            sess["role"] = role
            sess["_csrf_token"] = "t"

    def test_field_cannot_access_board(self):
        client = self.app.test_client()
        self._login_as(client, self.field_id, role="field")

        res = client.get("/board", follow_redirects=False)
        self.assertIn(res.status_code, (302, 303))

        res = client.get("/api/board/jobs", follow_redirects=False)
        self.assertIn(res.status_code, (302, 303))

    def test_admin_can_list_and_reassign(self):
        client = self.app.test_client()
        self._login_as(client, self.admin_id, role="admin")

        res = client.get("/api/board/jobs?page=1&page_size=50")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        rows = data.get("rows") or []
        self.assertTrue(len(rows) >= 1)
        job_id = int(rows[0].get("id"))
        self.assertTrue(job_id > 0)

        res = client.post("/api/board/jobs/reassign", json={"job_ids": [job_id], "assigned_user_id": self.field_id, "csrf_token": "t"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))

        detail = client.get(f"/api/board/job/{job_id}/detail")
        self.assertEqual(detail.status_code, 200)
        dj = detail.get_json()
        self.assertTrue(dj.get("ok"))
        self.assertEqual((dj.get("job") or {}).get("assigned_user"), "Field")
