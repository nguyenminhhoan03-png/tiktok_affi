import re

with open('src/gemini_generator.py', 'rb') as f:
    content = f.read()

# We want to replace from:
# b'        words = product_name.split()\n        if len(words) > 5:\n            return " ".            if prod_type == "clothing":'
# all the way to:
# the 'else:' block ending right before '# ─── SEGMENT GIỮA: DEMO BỔ SUNG ───'

# Let's find the start of words = product_name.split()
start_marker = b'        words = product_name.split()\n        if len(words) > 5:\n            return " ".            if prod_type == "clothing":'

# Let's find the end marker:
end_marker = b'        # \xe2\x94\x80\xe2\x94\x80\xe2\x94\x80 SEGMENT GI\xe1\xbb\xaeA: DEMO B\xe1\xbb\x94 SUNG \xe2\x94\x80\xe2\x94\x80\xe2\x94\x80'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker)

if start_idx == -1:
    print("Error: start marker not found!")
    # Let's try finding a shorter start marker just in case
    start_marker_alt = b'        words = product_name.split()\n        if len(words) > 5:\n            return " ".'
    start_idx = content.find(start_marker_alt)
    if start_idx == -1:
        raise ValueError("Could not find start marker")
    else:
        print("Found alternative start marker!")

if end_idx == -1:
    raise ValueError("Could not find end marker")

print(f"Start index: {start_idx}, End index: {end_idx}")

# The replacement content:
replacement_text = """        words = product_name.split()
        if len(words) > 5:
            return " ".join(words[:5]).rstrip(",.-/ ")
        return product_name

    def _build_segment_prompt(self, base_prompt: str, product_name: str, segment_index: int, total_segments: int, product_description: str | None = None) -> str:
        \"\"\"
        Tạo prompt chi tiết cho từng phân đoạn video để tránh trùng lặp nội dung.
        - Segment 0 (Intro): Cận cảnh (close-up) chi tiết sản phẩm.
        - Segment 1 (Demo): Demo bổ sung / người dùng thực tế.
        - Segment cuối (Outro): Người mẫu trình diễn thực tế / kết thúc.
        \"\"\"
        prod_type = self._determine_product_type(product_name)
        cleaned_name = self._clean_product_name(product_name)
        duration = 10
        
        # Thêm thông tin mô tả chi tiết nếu có để bổ sung ngữ cảnh cho Gemini sinh voiceover chính xác hơn
        desc_hint = ""
        if product_description:
            desc_hint = f"Thông tin mô tả sản phẩm: {product_description}\\n"

        # ─── SEGMENT ĐẦU: CẬN CẢNH CHI TIẾT (CLOSE-UP) ───
        if segment_index == 0:
            if prod_type == "clothing":
                return (
                    f"Render video cận cảnh (close-up) sản phẩm thời trang '{cleaned_name}' chất lượng cao, tỉ lệ dọc 9:16. "
                    f"{desc_hint}"
                    "Nội dung hình ảnh: Camera quay chi tiết chất liệu vải mềm mại, "
                    "đường chỉ may sắc nét, hoạ tiết, ren, cổ áo, gấu váy... Camera di chuyển chậm và mượt từ điểm này sang điểm khác trên trang phục. "
                    "QUAN TRỌNG: Video phải có giọng thuyết minh tiếng Việt tự nhiên, ấm áp đọc review sản phẩm "
                    "dựa trên thông tin sản phẩm thực tế phía trên — nhận xét về chất liệu, điểm nổi bật, ưu điểm của sản phẩm. "
                    "KHÔNG cần có người mẫu đứng toàn thân. Chỉ tập trung close-up sản phẩm. "
                    "Không chữ, không watermark. "
                    f"Thời lượng {duration} giây."
                )
            elif prod_type == "footwear":
                return (
                    f"Render video cận cảnh (close-up) đôi giày/dép '{cleaned_name}' chất lượng cao, tỉ lệ dọc 9:16. "
                    f"{desc_hint}"
                    "Nội dung hình ảnh: Camera quay từng chi tiết — mũi giày, đế chống trượt, phần da/vải, đường khâu tinh tế, logo thương hiệu... "
                    "Camera xoay nhẹ và di chuyển chậm để thấy sản phẩm từ nhiều góc. "
                    "QUAN TRỌNG: Video phải có giọng thuyết minh tiếng Việt tự nhiên đọc review "
                    "dựa trên thông tin thực tế của sản phẩm phía trên — nhận xét về chất liệu, độ bền, sự thoải mái. "
                    "KHÔNG cần người mẫu đứng toàn thân. Chỉ tập trung close-up sản phẩm. "
                    "Không chữ, không watermark. "
                    f"Thời lượng {duration} giây."
                )
            else:
                return (
                    f"Render video cận cảnh (close-up) sản phẩm '{cleaned_name}' chất lượng cao, tỉ lệ dọc 9:16. "
                    f"{desc_hint}"
                    "Nội dung hình ảnh: Camera quay từng chi tiết sản phẩm — nút bấm, cổng kết nối, chất liệu vỏ máy, màn hình, logo... "
                    "Camera di chuyển chậm và xoay nhẹ quanh sản phẩm để thấy các góc cạnh. "
                    "QUAN TRỌNG: Video phải có giọng thuyết minh tiếng Việt tự nhiên đọc review "
                    "dựa trên thông tin thực tế của sản phẩm phía trên — nhận xét về tính năng, chất lượng, điểm nổi bật. "
                    "KHÔNG cần có người review đứng toàn thân. Chỉ tập trung close-up sản phẩm. "
                    "Không chữ, không watermark. "
                    f"Thời lượng {duration} giây."
                )

        # ─── SEGMENT CUỐI: NGƯỜI MẶC/DÙNG THỰC TẾ ───
        elif segment_index == total_segments - 1:
            if prod_type == "clothing":
                return (
                    f"Render video người mẫu mặc sản phẩm thời trang '{cleaned_name}' trình diễn tự nhiên, tỉ lệ dọc 9:16, phong cách review thời trang. "
                    "Nội dung hình ảnh: Người mẫu thời trang mặc trang phục này giới thiệu trước camera trong studio thời trang sáng sủa. "
                    "Người mẫu di chuyển đi lại nhẹ nhàng chuyên nghiệp để thể hiện phom dáng, màu sắc và thiết kế của trang phục. "
                    "Camera di chuyển mượt mà lấy toàn cảnh trang phục tôn dáng. "
                    "QUAN TRỌNG: Video phải có giọng thuyết minh tiếng Việt giới thiệu sản phẩm tự nhiên, hào hứng: "
                    "'Mặc lên người rất đẹp, phom chuẩn, tôn dáng cực kỳ, chất vải mặc lên rất thoải mái và sang trọng...'. "
                    "KHÔNG lặp lại phần close-up chi tiết đã có ở video trước. "
                    "Không chữ, không watermark. "
                    f"Thời lượng {duration} giây."
                )
            elif prod_type == "footwear":
                return (
                    f"Render video người đi thực tế đôi giày/dép '{cleaned_name}', tỉ lệ dọc 9:16, phong cách TikTok. "
                    "Nội dung: Một người mẫu xỏ chân vào đôi giày/dép và bước đi tự tin trước camera. "
                    "Quay cảnh chân đi trên nền đẹp, người mẫu bước đi nhẹ nhàng uyển chuyển, thỉnh thoảng nhấc chân lên cho thấy đế giày. "
                    "Camera quay cả cảnh toàn thân đi lại lẫn cảnh gần đôi chân để thấy giày vừa vặn và đẹp như thế nào. "
                    "Người mẫu mỉm cười hài lòng thể hiện sự thoải mái và phong cách khi đi sản phẩm. "
                    "QUAN TRỌNG: Video phải có giọng thuyết minh tiếng Việt hào hứng: "
                    "'Đi vào êm siêu, ôm chân cực chuẩn, trông phong cách lắm, ai cũng nên có đôi này...'. "
                    "Không chữ, không watermark. "
                    f"Thời lượng {duration} giây."
                )
            else:
                return (
                    f"Render video người dùng thực tế sản phẩm '{cleaned_name}', tỉ lệ dọc 9:16, phong cách TikTok. "
                    "Nội dung: Một người reviewer trẻ trung cầm và sử dụng sản phẩm trực tiếp trước camera. "
                    "Họ bật/mở sản phẩm, thao tác các tính năng thực tế, biểu cảm rõ rệt sự hài lòng và thích thú. "
                    "Camera ghi lại cả cảnh toàn thân dùng sản phẩm lẫn cảnh gần mặt cười tươi thể hiện cảm xúc thực. "
                    "Người dùng chỉ tay giới thiệu các tính năng nổi bật một cách tự nhiên sinh động. "
                    "QUAN TRỌNG: Video phải có giọng thuyết minh tiếng Việt hào hứng: "
                    "'Dùng rồi mê luôn, tính năng xịn, chất lượng vượt mong đợi, giá lại hợp lý, mua ngay nhé...'. "
                    "Không chữ, không watermark. "
                    f"Thời lượng {duration} giây."
                )

"""

new_content = content[:start_idx] + replacement_text.encode('utf-8') + content[end_idx:]

with open('src/gemini_generator.py', 'wb') as f:
    f.write(new_content)

print("Replacement done successfully!")
