import tempfile
from pathlib import Path
import unittest
import numpy as np
from core import Store, match, normalize, Confirmation


def vector(axis=0):
    result = np.zeros(512, dtype=np.float32)
    result[axis] = 1
    return result


class MatchingTests(unittest.TestCase):
    def test_registered_identity(self):
        gallery = {"khang": {"name": "Khang", "vectors": [vector()] * 5},
                   "long": {"name": "Long", "vectors": [vector(1)] * 5}}
        self.assertEqual(match(vector(), gallery)[0], "khang")

    def test_unknown_is_not_forced_to_nearest_person(self):
        gallery = {"khang": {"name": "Khang", "vectors": [vector()] * 5}}
        self.assertIsNone(match(vector(2), gallery)[0])

    def test_ambiguous_candidates_are_rejected(self):
        gallery = {x: {"name": x, "vectors": [vector()] * 5} for x in ["a", "b"]}
        self.assertIsNone(match(vector(), gallery)[0])

    def test_not_enough_samples(self):
        self.assertIsNone(match(vector(), {"a": {"name": "A", "vectors": [vector()] * 4}})[0])

    def test_invalid_vector(self):
        for value in [np.zeros(512), np.full(512, np.nan), np.ones(128)]:
            with self.assertRaises(ValueError):
                normalize(value)

    def test_confirmation_resets_when_person_disappears_or_changes(self):
        state = Confirmation(3)
        self.assertIsNone(state.update("a"))
        self.assertIsNone(state.update("a"))
        self.assertEqual(state.update("a"), "a")
        self.assertIsNone(state.update(None))
        self.assertIsNone(state.update("a"))
        self.assertIsNone(state.update("b"))
        self.assertIsNone(state.update("b"))
        self.assertEqual(state.update("b"), "b")


class StorageTests(unittest.TestCase):
    def test_roundtrip_unicode_and_cascade_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "faces.db")
            name = "Đăng Khang ' Nguyễn"
            pid = store.create_person(name)
            store.add_sample(pid, vector())
            reopened = Store(store.path)
            self.assertEqual(reopened.people(), [(pid, name, 1)])
            np.testing.assert_allclose(reopened.gallery()[pid]["vectors"][0], vector())
            reopened.delete_person(pid)
            self.assertEqual(reopened.people(), [])
            with reopened.connect() as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM samples").fetchone()[0], 0)

    def test_duplicate_sample_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / "faces.db")
            pid = store.create_person("Khang")
            store.add_sample(pid, vector())
            with self.assertRaises(ValueError):
                store.add_sample(pid, vector())


if __name__ == "__main__":
    unittest.main()
