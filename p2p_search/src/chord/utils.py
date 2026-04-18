import hashlib

def deterministic_hash(keyword: str, m: int) -> int:
    """
    Hàm băm cung cấp kết quả nhất quán trên mọi phiên làm việc Python (thay thế cho hash() mặc định).
    Sử dụng SHA-1 chuẩn DHT để tạo ra một số định danh cho keyword trên không gian 2^m.
    """
    h = hashlib.sha1(keyword.encode('utf-8')).hexdigest()
    return int(h, 16) % (2 ** m)

def in_range(val: int, start: int, end: int, inclusive_left: bool = False, inclusive_right: bool = False) -> bool:
    """
    Toán tử khoảng cách trên vòng tròn (Circular Interval) chuẩn Chord.
    Khoảng được định nghĩa là quãng đường di chuyển theo chiều kim đồng hồ từ start đến end.
    
    Nếu start == end: Khoảng rỗng (hoặc chỉ chứa điểm đó nếu có tính cả hai đầu).
    """
    if start == end:
        is_same = (val == start)
        if is_same:
            # [n, n], [n, n), (n, n] đều chứa n. Chỉ (n, n) là rỗng.
            return inclusive_left or inclusive_right
        return False

    if start < end:
        # Khoảng bình thường không vắt qua 0
        left_ok = (val > start) or (inclusive_left and val == start)
        right_ok = (val < end) or (inclusive_right and val == end)
        return left_ok and right_ok
    else:
        # Khoảng vắt qua giá trị 0 (start > end)
        left_ok = (val > start) or (inclusive_left and val == start)
        right_ok = (val < end) or (inclusive_right and val == end)
        return left_ok or right_ok
