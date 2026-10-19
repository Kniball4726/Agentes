import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path

from src.user_store import UserStore, UserStoreError


class UserStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        database = Path(self.temp_dir.name) / "users.sqlite3"
        self.store = UserStore(database)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_first_admin_is_persisted_and_password_is_hashed(self):
        admin = self.store.create_initial_admin("owner", "A-Strong-Password")

        self.assertEqual(admin.role, "administrador")
        self.assertEqual(self.store.authenticate("OWNER", "A-Strong-Password"), admin)
        self.assertIsNone(self.store.authenticate("owner", "incorrect-password"))
        self.assertIsNone(self.store.authenticate("missing", "incorrect-password"))
        with closing(sqlite3.connect(self.store.database_path)) as connection:
            stored_hash = connection.execute(
                "SELECT password_hash FROM users WHERE id = ?", (admin.id,)
            ).fetchone()[0]
        self.assertNotIn("A-Strong-Password", stored_hash)
        with self.assertRaises(UserStoreError):
            self.store.create_initial_admin("second", "Another-Strong-Password")

    def test_roles_and_account_activation_are_persisted(self):
        admin = self.store.create_initial_admin("owner", "A-Strong-Password")
        operator = self.store.create_user(
            "operator", "Another-Strong-Password", "operador"
        )

        self.store.update_role(operator.id, "consulta")
        updated_operator = self.store.get_user(operator.id)
        self.assertIsNotNone(updated_operator)
        assert updated_operator is not None
        self.assertEqual(updated_operator.role, "consulta")
        self.store.set_active(operator.id, False)
        self.assertIsNone(
            self.store.authenticate("operator", "Another-Strong-Password")
        )
        self.store.set_active(operator.id, True)
        authenticated_operator = self.store.authenticate(
            "operator", "Another-Strong-Password"
        )
        self.assertIsNotNone(authenticated_operator)
        assert authenticated_operator is not None
        self.assertEqual(authenticated_operator.role, "consulta")
        persisted_admin = self.store.get_user(admin.id)
        self.assertIsNotNone(persisted_admin)
        assert persisted_admin is not None
        self.assertEqual(persisted_admin.role, "administrador")

    def test_cannot_remove_or_disable_the_last_active_admin(self):
        admin = self.store.create_initial_admin("owner", "A-Strong-Password")

        with self.assertRaises(UserStoreError):
            self.store.update_role(admin.id, "operador")
        with self.assertRaises(UserStoreError):
            self.store.set_active(admin.id, False)
        persisted_admin = self.store.get_user(admin.id)
        self.assertIsNotNone(persisted_admin)
        assert persisted_admin is not None
        self.assertTrue(persisted_admin.active)

    def test_rejects_invalid_users_and_roles(self):
        self.store.create_initial_admin("owner", "A-Strong-Password")

        with self.assertRaises(ValueError):
            self.store.create_user("ab", "Another-Strong-Password", "operador")
        with self.assertRaises(ValueError):
            self.store.create_user("new-user", "short", "operador")
        with self.assertRaises(ValueError):
            self.store.create_user("new-user", "Another-Strong-Password", "root")
        with self.assertRaises(ValueError):
            self.store.create_user("owner", "Another-Strong-Password", "consulta")


if __name__ == "__main__":
    unittest.main()
