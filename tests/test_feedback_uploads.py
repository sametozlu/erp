import io
import os
import sys
import tempfile
import time
import unittest


class FeedbackUploadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = os.path.join(cls._tmpdir.name, "test.db")
        os.environ["DB_URL"] = f"sqlite:///{cls._db_path}"

        import importlib

        sys.modules.pop("app", None)
        sys.modules.pop("utils", None)
        cls.appmod = importlib.import_module("app")
        cls.utilsmod = importlib.import_module("utils")
        cls.app = cls.appmod.app
        cls.db = cls.appmod.db
        try:
            cls.appmod.db.engine.dispose()
        except Exception:
            pass
        cls.app.config["TESTING"] = True
        cls.app.config["UPLOAD_FOLDER"] = os.path.join(cls._tmpdir.name, "uploads")
        os.makedirs(cls.app.config["UPLOAD_FOLDER"], exist_ok=True)

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
                note="Test",
                assigned_user_id=field.id,
            )
            self.db.session.add(cell)
            self.db.session.commit()

            self.admin_id = admin.id
            self.field_id = field.id
            self.project_id = proj.id
            self.cell_id = cell.id

            self.utilsmod._publish_cell(cell, publisher=admin)
            self.db.session.commit()

            self.job = self.appmod.Job.query.filter_by(cell_id=cell.id).first()
            assert self.job is not None

    def _login_as(self, client, user_id, *, role):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = "x"
            sess["is_admin"] = (role == "admin")
            sess["role"] = role
            sess["_csrf_token"] = "t"

    def test_field_submit_with_attachment_visible_to_admin(self):
        client = self.app.test_client()

        self._login_as(client, self.field_id, role="field")

        with self.app.app_context():
            j = self.appmod.Job.query.get(self.job.id)
            self.assertEqual(j.kanban_status, "PUBLISHED")

        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
        def make_form():
            return {
                "csrf_token": "t",
                "q1_completed": "yes",
                "q2_isdp": "yes",
                "extra_work_note": "ok",
                "issue_note": "",
                "media_files": (io.BytesIO(png), "test.png"),
            }

        res = client.post(f"/me/job/{self.job.id}/report", data=make_form(), content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            fb = (
                self.appmod.JobFeedback.query
                .filter_by(job_id=self.job.id, user_id=self.field_id)
                .order_by(self.appmod.JobFeedback.id.desc())
                .first()
            )
            self.assertIsNotNone(fb)
            media = self.appmod.JobFeedbackMedia.query.filter_by(feedback_id=fb.id).all()
            self.assertEqual(len(media), 1)
            j = self.appmod.Job.query.get(self.job.id)
            self.assertEqual(j.kanban_status, "REPORTED")

        self._login_as(client, self.admin_id, role="admin")
        detail = client.get(f"/admin/reports/{fb.id}")
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"/files/view/feedback/", detail.data)

        res = client.post(f"/admin/reports/{fb.id}", data={"csrf_token": "t", "action": "reject", "review_note": "nope"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            j = self.appmod.Job.query.get(self.job.id)
            self.assertEqual(j.kanban_status, "REPORTED")

        self._login_as(client, self.field_id, role="field")
        res = client.post(f"/me/job/{self.job.id}/report", data=make_form(), content_type="multipart/form-data", follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        with self.app.app_context():
            fb2 = (
                self.appmod.JobFeedback.query
                .filter_by(job_id=self.job.id, user_id=self.field_id)
                .order_by(self.appmod.JobFeedback.id.desc())
                .first()
            )
            self.assertIsNotNone(fb2)
            self.assertEqual(getattr(fb2, "review_status", None), "pending")

        self._login_as(client, self.admin_id, role="admin")
        res = client.post(f"/admin/reports/{fb2.id}", data={"csrf_token": "t", "action": "approve", "review_note": "ok"}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        with self.app.app_context():
            j = self.appmod.Job.query.get(self.job.id)
            self.assertEqual(j.kanban_status, "CLOSED")
