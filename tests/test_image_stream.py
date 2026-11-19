from bullet_view.image_stream import FrameMatcher, image_frame_from_shm
from bullet_view.model import Bbox, ImageFrame


def frame(fid, session='a'):
    return ImageFrame(8, 8, 'rgb8', bytes(8 * 8 * 3), fid, 1, fid, session)


def test_matches_out_of_order_bbox_to_exact_frame():
    matcher = FrameMatcher()
    box = Bbox(True, 1, 2, 3, 4, fid=7)
    assert matcher.add_bbox(box, 1.) is None
    assert matcher.add_frame(frame(6), 1.01) is None
    assert matcher.add_frame(frame(7), 1.02) == (frame(7), box)


def test_no_target_and_stale_bbox_clear_overlay():
    matcher = FrameMatcher()
    matcher.add_frame(frame(7), 1.)
    assert matcher.add_bbox(Bbox(False, fid=7), 1.01) == (frame(7), None)
    assert matcher.add_bbox(Bbox(True, 1, 1, 2, 2, fid=7), 1.02)[1].valid
    assert matcher.fallback(1.6) == (frame(7), None)


def test_renderer_session_change_drops_old_pending_box():
    matcher = FrameMatcher()
    matcher.add_frame(frame(1, 'old'), 1.)
    matcher.add_bbox(Bbox(True, 1, 1, 2, 2, fid=2), 1.01)
    assert matcher.add_frame(frame(2, 'new'), 1.02) == (frame(2, 'new'), None)


def test_shm_frame_uses_header_fid_and_removes_row_padding():
    metadata = {'width': 2, 'height': 2, 'step': 8, 'encoding': 'rgb8',
                'sequence': 9, 'capture_ns': 10, 'session': 'a', 'header': {'fid': 80}}
    result = image_frame_from_shm(metadata, b'abcdef..ghijkl..')
    assert result.fid == 80 and result.session == 'a'
    assert result.pixels == b'abcdefghijkl'
