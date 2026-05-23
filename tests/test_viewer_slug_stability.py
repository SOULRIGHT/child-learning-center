import random
import unittest

from viewer_slug_utils import extract_viewer_slug, generate_viewer_slug


class ViewerSlugStabilityTests(unittest.TestCase):
    def test_generate_slug_format(self):
        slug = generate_viewer_slug()
        self.assertEqual(len(slug), 24)
        self.assertTrue(all(ch in '0123456789abcdef' for ch in slug))

    def test_extract_slug_from_malformed_string(self):
        slug = generate_viewer_slug()
        malformed = f"{slug} 최종 포인트 36000점 입력일수 47일"
        self.assertEqual(extract_viewer_slug(malformed), slug)

    def test_long_horizon_add_delete_simulation(self):
        """수년치 입소/퇴소 흐름을 단순화하여 slug 충돌/복구 안정성 점검"""
        rng = random.Random(20260524)
        active = {}
        retired = set()
        max_child_id = 0

        for _ in range(6000):
            should_add = (not active) or rng.random() < 0.62

            if should_add:
                max_child_id += 1
                new_slug = generate_viewer_slug()
                self.assertNotIn(new_slug, active.values())
                self.assertNotIn(new_slug, retired)
                active[max_child_id] = new_slug
            else:
                removed_child_id = rng.choice(list(active.keys()))
                retired.add(active.pop(removed_child_id))

            if active and rng.random() < 0.25:
                sampled_slug = rng.choice(list(active.values()))
                broken = f"/viewer/report/{sampled_slug}%20최종%20포인트"
                self.assertEqual(extract_viewer_slug(broken), sampled_slug)

        self.assertEqual(len(set(active.values())), len(active))


if __name__ == '__main__':
    unittest.main()
