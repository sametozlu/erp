import os
import sys
import tempfile
import time
import unittest


class SubProjectTests(unittest.TestCase):
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

            self.admin_id = admin.id
            self.field_id = field.id

            template = self.appmod.Project(
                region="-",
                project_code="P1",
                project_name="Proj",
                responsible="Resp",
                is_active=True,
            )
            plan_project = self.appmod.Project(
                region="Istanbul",
                project_code="P1",
                project_name="Proj",
                responsible="Resp",
                is_active=True,
            )
            self.db.session.add_all([template, plan_project])
            self.db.session.commit()
            self.template_id = template.id
            self.plan_project_id = plan_project.id

            sp = self.appmod.SubProject(project_id=template.id, name="Alt Proje 1", code="A1", is_active=True)
            self.db.session.add(sp)
            self.db.session.commit()
            self.subproject_id = sp.id

            from datetime import date

            cell = self.appmod.PlanCell(
                project_id=plan_project.id,
                subproject_id=sp.id,
                work_date=date.today(),
                note="Test",
                assigned_user_id=field.id,
            )
            self.db.session.add(cell)
            self.db.session.commit()
            self.cell_id = cell.id

    def _login_as(self, client, user_id, *, role):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = "x"
            sess["is_admin"] = (role == "admin")
            sess["role"] = role
            sess["_csrf_token"] = "t"

    def test_api_subprojects_for_plan_project(self):
        client = self.app.test_client()
        self._login_as(client, self.admin_id, role="admin")

        res = client.get(f"/api/subprojects?project_id={self.plan_project_id}")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        ids = [int(x.get("id")) for x in (data.get("subprojects") or [])]
        self.assertIn(self.subproject_id, ids)

    def test_publish_copies_subproject_to_job(self):
        with self.app.app_context():
            admin = self.appmod.User.query.get(self.admin_id)
            cell = self.appmod.PlanCell.query.get(self.cell_id)
            self.appmod._publish_cell(cell, publisher=admin)
            self.db.session.commit()

            job = self.appmod.Job.query.filter_by(cell_id=self.cell_id).first()
            self.assertIsNotNone(job)
            self.assertEqual(int(getattr(job, "subproject_id") or 0), int(self.subproject_id))

    def test_delete_blocked_when_used(self):
        client = self.app.test_client()
        self._login_as(client, self.admin_id, role="admin")

        res = client.post(
            f"/projects/{self.template_id}/subprojects/{self.subproject_id}/delete",
            data={"csrf_token": "t"},
            follow_redirects=False,
        )
        self.assertIn(res.status_code, (302, 303))
        with self.app.app_context():
            sp = self.appmod.SubProject.query.get(self.subproject_id)
            self.assertIsNotNone(sp)
