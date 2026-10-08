import time
import unittest
import cv2
import numpy as np
from tracking import FaceTracker, NameState, move_box, gray_frame


class TrackingTests(unittest.TestCase):
    def test_name_survives_short_unknown_without_blinking(self):
        state = NameState()
        for stamp in [10,10.2,10.4]:
            state.observe('a',stamp)
        state.observe(None,10.6)
        self.assertEqual(state.visible(11,2.5),'a')
        self.assertIsNone(state.visible(13,2.5))
        state.observe('a',13.1)
        self.assertIsNone(state.visible(13.1,2.5))

    def test_conflicting_identity_never_retains_old_name(self):
        state = NameState()
        for stamp in [10,10.2,10.4]:
            state.observe('a',stamp)
        state.observe('b',10.5)
        self.assertIsNone(state.visible(10.5,2.5))

    def test_two_people_remain_separate_when_detector_order_changes(self):
        now = time.monotonic()
        rgb = np.random.default_rng(9).integers(30,220,(240,320,3),dtype=np.uint8)
        first = np.zeros(512,np.float32); first[0]=1
        second = np.zeros(512,np.float32); second[1]=1
        a = {'box':(20,40,130,180),'embedding':first}
        b = {'box':(185,40,295,180),'embedding':second}
        tracker = FaceTracker({'confirm_frames':3})
        tracker.advance(rgb,now)
        for sequence in range(1,4):
            faces = [a,b] if sequence%2 else [b,a]
            names = ['a','b'] if sequence%2 else ['b','a']
            tracker.ingest({'sequence':sequence,'time':now,'rgb':rgb,'faces':faces},names)
        tracks = sorted(tracker.visible(now),key=lambda row:row[1][0])
        self.assertEqual(len(tracks),2)
        self.assertEqual([row[2] for row in tracks],['a','b'])
        self.assertEqual(tracker.visible(now+4),[])

    def test_box_follows_motion_between_ai_results(self):
        gray = np.random.default_rng(6).integers(30,220,(180,320),dtype=np.uint8)
        moved = cv2.warpAffine(gray,np.float32([[1,0,7],[0,1,4]]),(320,180))
        box = np.array([0.2,0.2,0.6,0.8])
        result = move_box(gray,moved,box)
        self.assertIsNotNone(result)
        np.testing.assert_allclose(result,box+np.array([7/320,4/180,7/320,4/180]),atol=0.01)

    def test_unreliable_motion_drops_track(self):
        blank = np.zeros((180,320),np.uint8)
        self.assertIsNone(move_box(blank,blank,[.2,.2,.6,.8]))


if __name__=='__main__':
    unittest.main()
