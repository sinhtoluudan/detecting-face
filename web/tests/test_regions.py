import sqlite3
import tempfile
from pathlib import Path
import unittest
import numpy as np
from core import Store
from region_match import DIMENSION, LABELS, check_regions, support_identity
from regions import descriptor, eye_transform, extract_regions


def region_vector(axis=0):
    vector = np.zeros(DIMENSION,dtype=np.float32)
    vector[axis] = 1
    return vector


def upper():
    return {key:region_vector() for key in ["eye_left","eye_right","forehead"]}


class RegionDecisionTests(unittest.TestCase):
    def test_matching_regions_support_candidate(self):
        query = upper()
        passed,score,_,_ = check_regions(query,[query]*3,query.keys())
        self.assertTrue(passed)
        self.assertAlmostEqual(score,1)

    def test_covered_nose_is_excluded(self):
        template = {**upper(),"nose":region_vector()}
        query = {**upper(),"nose":region_vector(1)}
        _,score,details,_ = check_regions(query,[template]*3,upper().keys())
        self.assertNotIn("nose",details)
        self.assertAlmostEqual(score,1)

    def test_wrong_regions_reject_identity(self):
        query = {key:region_vector(1) for key in upper()}
        self.assertFalse(check_regions(query,[upper()]*3,query.keys())[0])

    def test_too_few_regional_enrollments_reject(self):
        self.assertFalse(check_regions(upper(),[upper()]*2,upper().keys())[0])

    def test_missing_query_regions_reject(self):
        self.assertFalse(check_regions({"forehead":region_vector()},[upper()]*3,LABELS)[0])

    def test_no_eyes_rejects_even_if_three_other_regions_match(self):
        query = {key:region_vector() for key in ["brow_left","forehead","nose"]}
        self.assertFalse(check_regions(query,[query]*3,query)[0])

    def test_texture_cannot_override_failed_global_identity(self):
        gallery = {"person": {"regions": [upper()]*3}}
        self.assertIsNone(support_identity(None,upper(),gallery,upper())[0])


class RegionExtractionTests(unittest.TestCase):
    def test_descriptor_dimensions_finite_normalized(self):
        patch = np.random.default_rng(5).integers(20,230,(40,70),dtype=np.uint8)
        vector = descriptor(patch)
        self.assertEqual(vector.shape,(DIMENSION,))
        self.assertTrue(np.isfinite(vector).all())
        self.assertAlmostEqual(float(np.linalg.norm(vector)),1,places=5)

    def test_eye_alignment_and_small_face_rejection(self):
        keypoints = np.array([[88,120],[168,120],[128,170],[98,210],[158,210]],np.float32)
        np.testing.assert_allclose(eye_transform(keypoints),[[1,0,0],[0,1,0]],atol=1e-6)
        with self.assertRaises(ValueError):
            eye_transform(keypoints/4)

    def test_lower_occlusion_does_not_change_upper_features(self):
        keypoints = np.array([[88,120],[168,120],[128,170],[98,210],[158,210]],np.float32)
        image = np.random.default_rng(5).integers(20,230,(256,256,3),dtype=np.uint8)
        masked = image.copy()
        masked[142:] = 200
        before, after = extract_regions(image,keypoints),extract_regions(masked,keypoints)
        self.assertIn("nose",before["vectors"])
        self.assertNotIn("nose",after["vectors"])
        for key in upper():
            np.testing.assert_allclose(before["vectors"][key],after["vectors"][key])

    def test_border_padding_not_used_as_region_evidence(self):
        image = np.random.default_rng(9).integers(20,230,(256,256,3),dtype=np.uint8)
        keypoints = np.array([[88,20],[168,20],[128,70],[98,110],[158,110]],np.float32)
        self.assertNotIn("forehead",extract_regions(image,keypoints)["vectors"])


class RegionStorageTests(unittest.TestCase):
    def test_legacy_database_migration_and_duplicate_upgrade(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder)/"legacy.db"
            embedding = np.zeros(512,np.float32)
            embedding[0] = 1
            db = sqlite3.connect(path)
            db.executescript('''CREATE TABLE people(id TEXT PRIMARY KEY,name TEXT NOT NULL);
                CREATE TABLE samples(id INTEGER PRIMARY KEY,person_id TEXT NOT NULL,
                embedding BLOB NOT NULL,model TEXT NOT NULL DEFAULT 'buffalo_l',
                FOREIGN KEY(person_id) REFERENCES people(id) ON DELETE CASCADE);''')
            db.execute("INSERT INTO people VALUES (?,?)",("old","Khang"))
            db.execute("INSERT INTO samples(person_id,embedding) VALUES (?,?)",("old",embedding.tobytes()))
            db.commit()
            db.close()
            store = Store(path)
            self.assertEqual(store.people(),[("old","Khang",1)])
            self.assertEqual(store.gallery()["old"]["regions"],[])
            self.assertEqual(store.add_sample("old",embedding,upper()),"updated")
            reopened = Store(path)
            self.assertEqual(reopened.people(),[("old","Khang",1)])
            self.assertEqual(set(reopened.gallery()["old"]["regions"][0]),set(upper()))
            with self.assertRaises(ValueError):
                reopened.add_sample("old",embedding,upper())


if __name__ == "__main__":
    unittest.main()
