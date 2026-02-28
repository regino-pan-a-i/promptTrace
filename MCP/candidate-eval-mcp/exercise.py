from typing import List


def findMin(nums: List[int]) -> int:
    left, right = 0, len(nums) - 1

    while left < right:
        mid = (left + right) // 2
        if nums[mid] > nums[right]:
            left = mid + 1
        else:
            right = mid

    return nums[left]


# ---------------------------------------------------------------------------
# Tests — do not modify
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    test_cases = [
        ([3, 4, 5, 1, 2], 1),
        ([4, 5, 6, 7, 0, 1, 2], 0),
        ([11, 13, 15, 17], 11),
        ([1], 1),
        ([2, 1], 1),
    ]

    all_passed = True
    for i, (nums, expected) in enumerate(test_cases, 1):
        result = findMin(nums)
        status = "✅ PASS" if result == expected else "❌ FAIL"
        print(f"Test {i}: {status} | Input: {nums} | Expected: {expected} | Got: {result}")
        if result != expected:
            all_passed = False

    print("\n✅ All tests passed!" if all_passed else "\n❌ Some tests failed. Keep going!")