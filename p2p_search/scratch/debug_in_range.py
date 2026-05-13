from src.chord.utils import in_range

print(f"(50, 10, 10): {in_range(50, 10, 10)}")
print(f"(10, 10, 10): {in_range(10, 10, 10)}")
print(f"(50, 10, 10, inclusive_right=True): {in_range(50, 10, 10, inclusive_right=True)}")
print(f"(10, 10, 10, inclusive_right=True): {in_range(10, 10, 10, inclusive_right=True)}")
