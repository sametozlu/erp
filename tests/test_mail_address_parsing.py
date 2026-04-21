import unittest


class MailAddressParsingTests(unittest.TestCase):
    def test_split_email_list_accepts_sequence(self):
        import utils

        self.assertEqual(utils._split_email_list(["a@b.com"]), ["a@b.com"])
        self.assertEqual(utils._split_email_list(("a@b.com", "c@d.com")), ["a@b.com", "c@d.com"])

    def test_split_email_list_accepts_csv(self):
        import utils

        self.assertEqual(utils._split_email_list("a@b.com, c@d.com"), ["a@b.com", "c@d.com"])
        self.assertEqual(utils._split_email_list("a@b.com; c@d.com"), ["a@b.com", "c@d.com"])
        self.assertEqual(utils._split_email_list("a@b.com c@d.com"), ["a@b.com", "c@d.com"])

    def test_split_email_list_accepts_json_list_string(self):
        import utils

        self.assertEqual(utils._split_email_list('["a@b.com","c@d.com"]'), ["a@b.com", "c@d.com"])

    def test_split_email_list_accepts_python_list_string_legacy(self):
        import utils

        self.assertEqual(utils._split_email_list("['a@b.com']"), ["a@b.com"])

    def test_canonical_email_extracts_addr(self):
        import utils

        self.assertEqual(utils._canonical_email("Name <a@b.com>"), "a@b.com")
        self.assertEqual(utils._canonical_email("a@b.com"), "a@b.com")

