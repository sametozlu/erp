import os
import sys
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta


class PortalEnhancementsTests(unittest.TestCase):
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

            t1 = self.appmod.Team(name="Team 1", signature="sig_t1")
            t2 = self.appmod.Team(name="Team 2", signature="sig_t2")
            self.db.session.add_all([t1, t2])
            self.db.session.commit()

            admin = self.appmod.User(
                username="admin",
                email="admin@example.com",
                full_name="Admin",
                role="admin",
                is_admin=True,
                is_active=True,
            )
            admin.set_password("pw")
            field1 = self.appmod.User(
                username="field1",
                email="field1@example.com",
                full_name="Field One",
                role="field",
                is_admin=False,
                is_active=True,
                team_id=t1.id,
            )
            field1.set_password("pw")
            field2 = self.appmod.User(
                username="field2",
                email="field2@example.com",
                full_name="Field Two",
                role="field",
                is_admin=False,
                is_active=True,
                team_id=t2.id,
            )
            field2.set_password("pw")
            field1b = self.appmod.User(
                username="field1b",
                email="field1b@example.com",
                full_name="Field One B",
                role="field",
                is_admin=False,
                is_active=True,
                team_id=t1.id,
            )
            field1b.set_password("pw")
            self.db.session.add_all([admin, field1, field1b, field2])
            self.db.session.commit()

            p1 = self.appmod.Project(
                region="Istanbul",
                project_code="P1",
                project_name="Proj1",
                responsible="Resp",
                is_active=True,
            )
            p2 = self.appmod.Project(
                region="Ankara",
                project_code="P2",
                project_name="Proj2",
                responsible="Resp",
                is_active=True,
            )
            self.db.session.add_all([p1, p2])
            self.db.session.commit()

            today = date.today()
            now = datetime.now()

            # Make at least one other user appear online (chat is online-users based)
            field2.last_seen = now
            field2.online_since = now
            self.db.session.add(field2)
            self.db.session.commit()

            c_pending = self.appmod.PlanCell(
                project_id=p1.id,
                work_date=today,
                note="NOTE_PENDING",
                shift="Gunduz",
                team_name="Ekip A",
                assigned_user_id=field1.id,
            )
            c_problem = self.appmod.PlanCell(
                project_id=p1.id,
                work_date=today + timedelta(days=1),
                note="NOTE_PROBLEM",
                shift="Gece",
                team_name="Ekip A",
                assigned_user_id=field1.id,
            )
            c_completed_no_report = self.appmod.PlanCell(
                project_id=p1.id,
                work_date=today + timedelta(days=2),
                note="NOTE_C_NO_REPORT",
                shift="Gunduz",
                team_name="Ekip A",
                assigned_user_id=field1.id,
            )
            c_completed_with_report = self.appmod.PlanCell(
                project_id=p1.id,
                work_date=today + timedelta(days=3),
                note="NOTE_C_WITH_REPORT",
                shift="Gunduz",
                team_name="Ekip A",
                assigned_user_id=field1.id,
            )
            c_other_today = self.appmod.PlanCell(
                project_id=p2.id,
                work_date=today,
                note="NOTE_OTHER_TODAY",
                shift="Gunduz",
                team_name="Ekip B",
                assigned_user_id=field2.id,
            )
            self.db.session.add_all([c_pending, c_problem, c_completed_no_report, c_completed_with_report, c_other_today])
            self.db.session.commit()

            j_pending = self.appmod._publish_cell(c_pending, publisher=admin, now=now)
            j_problem = self.appmod._publish_cell(c_problem, publisher=admin, now=now)
            j_no_report = self.appmod._publish_cell(c_completed_no_report, publisher=admin, now=now)
            j_reported = self.appmod._publish_cell(c_completed_with_report, publisher=admin, now=now)
            j_other = self.appmod._publish_cell(c_other_today, publisher=admin, now=now)

            j_problem.status = "problem"
            j_no_report.status = "completed"
            j_no_report.closed_at = now
            j_reported.status = "completed"
            j_reported.closed_at = now
            self.db.session.add_all([j_pending, j_problem, j_no_report, j_reported, j_other])
            self.db.session.commit()

            fb = self.appmod.JobFeedback(
                job_id=j_reported.id,
                user_id=field1.id,
                submitted_at=now,
                outcome="completed",
            )
            self.db.session.add(fb)
            self.db.session.commit()

            self.admin_id = admin.id
            self.field1_id = field1.id
            self.field1b_id = field1b.id
            self.field2_id = field2.id
            self.team1_id = t1.id
            self.team2_id = t2.id
            self.project1_id = p1.id
            self.project2_id = p2.id
            self.today = today
            self.job_pending_id = j_pending.id
            self.job_problem_id = j_problem.id
            self.job_no_report_id = j_no_report.id
            self.job_reported_id = j_reported.id
            self.cell_pending_id = c_pending.id

    def _login_as(self, client, user_id, *, role):
        with client.session_transaction() as sess:
            sess["user_id"] = user_id
            sess["username"] = "x"
            sess["role"] = role
            sess["is_admin"] = (role == "admin")
            sess["_csrf_token"] = "t"

    def test_presets_filter_correctly(self):
        client = self.app.test_client()
        self._login_as(client, self.field1_id, role="field")

        start = self.appmod.iso(self.today)
        end = self.appmod.iso(self.today + timedelta(days=10))

        res = client.get(f"/me/waiting?start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NOTE_PENDING", res.data)
        self.assertNotIn(b"NOTE_PROBLEM", res.data)
        self.assertNotIn(b"NOTE_C_NO_REPORT", res.data)
        self.assertNotIn(b"NOTE_C_WITH_REPORT", res.data)

        res = client.get(f"/me/current?start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NOTE_PENDING", res.data)
        self.assertIn(b"NOTE_PROBLEM", res.data)
        self.assertNotIn(b"NOTE_C_NO_REPORT", res.data)
        self.assertNotIn(b"NOTE_C_WITH_REPORT", res.data)

        res = client.get(f"/me/completed?start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"NOTE_PENDING", res.data)
        self.assertNotIn(b"NOTE_PROBLEM", res.data)
        self.assertIn(b"NOTE_C_NO_REPORT", res.data)
        self.assertIn(b"NOTE_C_WITH_REPORT", res.data)

        res = client.get(f"/me/reported?start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"NOTE_PENDING", res.data)
        self.assertNotIn(b"NOTE_PROBLEM", res.data)
        self.assertNotIn(b"NOTE_C_NO_REPORT", res.data)
        self.assertIn(b"NOTE_C_WITH_REPORT", res.data)

        res = client.get(f"/me/report-pending?start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"NOTE_PENDING", res.data)
        self.assertNotIn(b"NOTE_PROBLEM", res.data)
        self.assertIn(b"NOTE_C_NO_REPORT", res.data)
        self.assertNotIn(b"NOTE_C_WITH_REPORT", res.data)

    def test_preset_and_dropdown_filters_intersect(self):
        client = self.app.test_client()
        self._login_as(client, self.field1_id, role="field")

        start = self.appmod.iso(self.today)
        end = self.appmod.iso(self.today + timedelta(days=10))

        res = client.get(f"/me/current?status=pending&start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NOTE_PENDING", res.data)
        self.assertNotIn(b"NOTE_PROBLEM", res.data)
        self.assertNotIn(b"NOTE_C_NO_REPORT", res.data)

    def test_card_classes_include_report_flags(self):
        client = self.app.test_client()
        self._login_as(client, self.field1_id, role="field")

        start = self.appmod.iso(self.today)
        end = self.appmod.iso(self.today + timedelta(days=10))
        res = client.get(f"/me/completed?start={start}&end={end}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"status-report-pending", res.data)
        self.assertIn(b"status-reported", res.data)

    def test_chat_permissions_and_persistence(self):
        client = self.app.test_client()

        self._login_as(client, self.field1_id, role="field")
        res = client.get("/api/chat/users")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        items = data.get("items") or []
        self.assertTrue(any(int(u.get("id")) == int(self.field2_id) for u in items))

        # Can send to offline user (message is persisted)
        res = client.post("/api/chat/send", json={"to_user_id": self.admin_id, "text": "x", "csrf_token": "t"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue((res.get_json() or {}).get("ok"))

        res = client.post("/api/chat/send", json={"to_user_id": self.field2_id, "text": "hello", "csrf_token": "t"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual((data.get("message") or {}).get("text"), "hello")

        res = client.get(f"/api/chat/messages?user_id={self.field2_id}&limit=200")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        msgs = data.get("messages") or []
        self.assertTrue(any(m.get("text") == "hello" for m in msgs))

        self._login_as(client, self.admin_id, role="admin")
        res = client.get("/api/chat/users")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        ids = {int(u.get("id")) for u in (data.get("items") or []) if u and u.get("id")}
        self.assertIn(int(self.field2_id), ids)

        res = client.post("/api/chat/send", json={"to_user_id": self.field2_id, "text": "admin-msg", "csrf_token": "t"})
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))

    def test_admin_messages_and_announcements(self):
        client = self.app.test_client()

        self._login_as(client, self.admin_id, role="admin")

        # Admin -> direct user message (chat)
        res = client.post(
            "/admin/messages",
            data={"target_type": "user", "to_user_id": str(self.field2_id), "message": "admin-direct", "csrf_token": "t"},
        )
        self.assertIn(res.status_code, (302, 303))

        # Admin -> team announcement
        res = client.post(
            "/admin/messages",
            data={"target_type": "team", "team_id": str(self.team1_id), "title": "Team", "message": "team-ann", "csrf_token": "t"},
        )
        self.assertIn(res.status_code, (302, 303))

        # Admin -> all announcement
        res = client.post(
            "/admin/messages",
            data={"target_type": "all", "title": "All", "message": "all-ann", "csrf_token": "t"},
        )
        self.assertIn(res.status_code, (302, 303))

        with self.app.app_context():
            ann_all = self.appmod.Announcement.query.filter_by(body="all-ann").first()
            self.assertIsNotNone(ann_all)
            ann_all_id = int(ann_all.id)

        # Field1 (team1) sees team + all announcements
        self._login_as(client, self.field1_id, role="field")
        res = client.get("/announcements")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"team-ann", res.data)
        self.assertIn(b"all-ann", res.data)

        # Field2 (team2) sees only all announcements
        self._login_as(client, self.field2_id, role="field")
        res = client.get("/announcements")
        self.assertEqual(res.status_code, 200)
        self.assertNotIn(b"team-ann", res.data)
        self.assertIn(b"all-ann", res.data)

        # Mark read (API)
        res = client.post(f"/api/announcements/{ann_all_id}/read", json={"csrf_token": "t"})
        self.assertEqual(res.status_code, 200)
        self.assertTrue((res.get_json() or {}).get("ok"))

    def test_where_panel_lists_todays_published_jobs(self):
        client = self.app.test_client()
        self._login_as(client, self.field1_id, role="field")

        d = self.appmod.iso(self.today)
        res = client.get(f"/me/where?date={d}")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"NOTE_PENDING", res.data)
        self.assertIn(b"NOTE_OTHER_TODAY", res.data)

    def test_reschedule_copy_and_move(self):
        client = self.app.test_client()
        self._login_as(client, self.field1_id, role="field")

        # invalid date
        res = client.post(f"/api/jobs/{self.job_pending_id}/reschedule", json={"target_date": "", "mode": "copy", "csrf_token": "t"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual((res.get_json() or {}).get("error"), "target_date_invalid")

        # target date same
        res = client.post(
            f"/api/jobs/{self.job_pending_id}/reschedule",
            json={"target_date": self.appmod.iso(self.today), "mode": "copy", "csrf_token": "t"},
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual((res.get_json() or {}).get("error"), "target_date_same")

        # busy cell (tomorrow has NOTE_PROBLEM in same project)
        res = client.post(
            f"/api/jobs/{self.job_pending_id}/reschedule",
            json={"target_date": self.appmod.iso(self.today + timedelta(days=1)), "mode": "move", "csrf_token": "t"},
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual((res.get_json() or {}).get("error"), "target_cell_busy")

        # move to empty date
        target_move = self.today + timedelta(days=12)
        res = client.post(
            f"/api/jobs/{self.job_pending_id}/reschedule",
            json={"target_date": self.appmod.iso(target_move), "mode": "move", "csrf_token": "t"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("mode"), "move")
        self.assertEqual(data.get("to_date"), self.appmod.iso(target_move))
        self.assertEqual(data.get("from_date"), self.appmod.iso(self.today))

        with self.app.app_context():
            job = self.appmod.Job.query.get(self.job_pending_id)
            self.assertIsNotNone(job)
            self.assertEqual(job.work_date, target_move)

            src_cell = self.appmod.PlanCell.query.get(self.cell_pending_id)
            self.assertIsNotNone(src_cell)
            self.assertIsNone(src_cell.note)

            dst_cell = self.appmod.PlanCell.query.get(job.cell_id)
            self.assertIsNotNone(dst_cell)
            self.assertEqual(dst_cell.note, "NOTE_PENDING")

        # copy completed job to empty date and mark old pending
        target_copy = self.today + timedelta(days=13)
        res = client.post(
            f"/api/jobs/{self.job_no_report_id}/reschedule",
            json={"target_date": self.appmod.iso(target_copy), "mode": "copy", "mark_old_pending": True, "csrf_token": "t"},
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data.get("ok"))
        self.assertEqual(data.get("mode"), "copy")
        new_job_id = int(data.get("new_job_id") or 0)
        self.assertTrue(new_job_id > 0)

        with self.app.app_context():
            old_job = self.appmod.Job.query.get(self.job_no_report_id)
            self.assertIsNotNone(old_job)
            self.assertEqual(old_job.status, "pending")
            self.assertIsNone(old_job.closed_at)

            new_job = self.appmod.Job.query.get(new_job_id)
            self.assertIsNotNone(new_job)
            self.assertEqual(new_job.work_date, target_copy)
            self.assertEqual(new_job.note, "NOTE_C_NO_REPORT")

        # forbidden for other user
        self._login_as(client, self.field2_id, role="field")
        res = client.post(
            f"/api/jobs/{self.job_reported_id}/reschedule",
            json={"target_date": self.appmod.iso(self.today + timedelta(days=20)), "mode": "copy", "csrf_token": "t"},
        )
        self.assertEqual(res.status_code, 403)
