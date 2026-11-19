"""Motion-assisted per-face tracks and independent name confirmation.

Optical flow bridges AI updates, but is not identity verification. Unreliable
motion, ambiguous associations and expired tracks are discarded.
"""
from dataclasses import dataclass
import time
import numpy as np
import cv2


def gray_frame(rgb):
    h,w = rgb.shape[:2]
    return cv2.cvtColor(cv2.resize(rgb,(320,max(32,round(h*320/w)))),cv2.COLOR_RGB2GRAY)


def iou(a,b):
    area = max(0,min(a[2],b[2])-max(a[0],b[0])) * max(0,min(a[3],b[3])-max(a[1],b[1]))
    total = (a[2]-a[0])*(a[3]-a[1])+(b[2]-b[0])*(b[3]-b[1])-area
    return area/max(total,1e-8)


def move_box(old,new,box):
    if old.shape != new.shape:
        return None
    h,w = old.shape
    x1,y1,x2,y2 = np.rint(np.asarray(box)*[w,h,w,h]).astype(int)
    mask = np.zeros_like(old)
    mask[max(0,y1):min(h,y2),max(0,x1):min(w,x2)] = 255
    points = cv2.goodFeaturesToTrack(old,maxCorners=40,qualityLevel=0.015,minDistance=4,mask=mask)
    if points is None or len(points)<5:
        return None
    next_points,status,_ = cv2.calcOpticalFlowPyrLK(old,new,points,None,winSize=(21,21),maxLevel=3)
    if next_points is None:
        return None
    back,reverse,_ = cv2.calcOpticalFlowPyrLK(new,old,next_points,None,winSize=(21,21),maxLevel=3)
    if back is None:
        return None
    valid = ((status.ravel()==1)&(reverse.ravel()==1)&
             (np.linalg.norm(back-points,axis=2).ravel()<1.5))
    if np.count_nonzero(valid)<5 or valid.mean()<0.45:
        return None
    shifts = (next_points-points).reshape(-1,2)[valid]
    delta = np.median(shifts,axis=0)
    if np.median(np.linalg.norm(shifts-delta,axis=1))>4 or np.linalg.norm(delta)>w*0.4:
        return None
    moved = np.asarray(box,dtype=float)+np.tile(delta/[w,h],2)
    if moved[2]<=0 or moved[3]<=0 or moved[0]>=1 or moved[1]>=1:
        return None
    return np.clip(moved,0,1)


@dataclass
class NameState:
    identity: str | None = None
    pending: str | None = None
    count: int = 0
    last_positive: float = -1e9

    def observe(self,candidate,stamp,required=3):
        if candidate is None:
            self.pending,self.count = None,0
            return
        if self.identity is not None and self.identity != candidate:
            self.identity = None  # Never retain a contradicted name during confirmation.
        self.count = self.count+1 if self.pending==candidate else 1
        self.pending = candidate
        if self.count>=required or self.identity==candidate:
            self.identity,self.last_positive = candidate,stamp

    def visible(self,now,hold):
        if self.identity is not None and now-self.last_positive>hold:
            self.identity = None
            self.pending,self.count = None,0
        return self.identity


class FaceTracker:
    def __init__(self,config):
        self.config = config
        self.clear()

    def clear(self):
        self.tracks = {}
        self.gray = None
        self.shape = None
        self.last_sequence = -1
        self.next_id = 1

    def advance(self,rgb,stamp):
        current = gray_frame(rgb)
        for key,track in list(self.tracks.items()):
            if stamp-track['seen']>self.config.get('track_timeout',3.0):
                del self.tracks[key]
                continue
            moved = move_box(self.gray,current,track['box']) if self.gray is not None else track['box']
            if moved is None:
                del self.tracks[key]
            else:
                track['box'] = moved
        self.gray,self.shape = current,rgb.shape[:2]

    def ingest(self,item,candidates):
        if item['sequence']<=self.last_sequence:
            return
        self.last_sequence = item['sequence']
        if self.gray is None or time.monotonic()-item['time']>self.config.get('max_result_age',3.0):
            return
        old = gray_frame(item['rgb'])
        h,w = item['rgb'].shape[:2]
        observations = []
        for face,candidate in zip(item['faces'],candidates):
            box = np.asarray(face['box'],float)/[w,h,w,h]
            projected = move_box(old,self.gray,box)
            if projected is None:
                continue
            emb = np.asarray(face['embedding'],dtype=np.float32)
            observations.append((projected,emb,candidate))
        # Associate all detections together, not by the detector's output order.
        pairs = []
        for index,(box,emb,_) in enumerate(observations):
            options = []
            for key,track in self.tracks.items():
                overlap = iou(box,track['box'])
                appearance = float(emb@track['embedding'])
                if overlap>0.12 and appearance>0.35:
                    options.append((0.55*overlap+0.45*appearance,index,key))
            options.sort(reverse=True)
            if len(options)>1 and options[0][0]-options[1][0]<0.06:
                # Crossing faces: clear competing identities rather than transfer names.
                for _,_,key in options:
                    self.tracks[key]['name'] = NameState()
                continue
            pairs.extend(options[:1])
        used_tracks,used_obs = set(),set()
        for _,index,key in sorted(pairs,reverse=True):
            if key in used_tracks or index in used_obs:
                continue
            box,emb,candidate = observations[index]
            track = self.tracks[key]
            track['box'] = 0.65*track['box']+0.35*box
            track['embedding'],track['seen'] = emb,item['time']
            track['name'].observe(candidate,item['time'],self.config.get('confirm_frames',3))
            used_tracks.add(key)
            used_obs.add(index)
        for index,(box,emb,candidate) in enumerate(observations):
            if index in used_obs:
                continue
            # Remove overlapping unmatched tracks to avoid duplicate boxes/names.
            for key,track in list(self.tracks.items()):
                if key not in used_tracks and iou(box,track['box'])>0.35:
                    del self.tracks[key]
            state = NameState()
            state.observe(candidate,item['time'],self.config.get('confirm_frames',3))
            self.tracks[self.next_id] = {'box':box,'embedding':emb,'seen':item['time'],'name':state}
            self.next_id += 1

    def visible(self,now):
        result = []
        for key,track in self.tracks.items():
            if now-track['seen']<=self.config.get('track_timeout',3.0):
                result.append((key,track['box'],track['name'].visible(now,self.config.get('name_hold_seconds',2.5))))
        return result
