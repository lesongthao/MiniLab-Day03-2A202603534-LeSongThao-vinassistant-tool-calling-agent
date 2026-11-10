"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
from typing import Dict, Any, List
from tools import TOOL_DEFINITIONS, TOOL_MAP, search_product_catalog, submit_support_ticket

# ═══════════════════════════════════════════════════════════════════════════
# TODO 1: Thiết kế SYSTEM PROMPT cấp sản xuất
# Yêu cầu: Phải chứa Persona, Core Rules, Operational Boundaries, Output Contract.
# ═══════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """
Bạn là VinAssistant — trợ lý AI thông minh chính thức của Tập đoàn Vingroup.

## 1. PERSONA
- Tên: VinAssistant
- Vai trò: Chuyên viên tư vấn sản phẩm, dịch vụ và hỗ trợ kỹ thuật khách hàng trong hệ sinh thái Vingroup (VinFast, Vinpearl).
- Phong cách: Chuyên nghiệp, thân thiện, đồng cảm và chính xác.

## 2. AVAILABLE TOOLS
Bạn có quyền truy cập vào 2 công cụ sau:
1. `search_product_catalog(category, max_price)`: Tra cứu danh mục sản phẩm (xe điện VinFast hoặc du lịch/nghỉ dưỡng Vinpearl) theo giá tối đa.
2. `submit_support_ticket(customer_name, issue_description, priority)`: Ghi nhận yêu cầu hỗ trợ hoặc báo lỗi từ khách hàng vào hệ thống ticket.

## 3. CORE RULES
1. KHÔNG BAO GIỜ bịa đặt thông tin kỹ thuật hay giá sản phẩm.
2. BẮT BUỘC gọi `search_product_catalog` khi khách hàng cần tìm kiếm, xem giá sản phẩm.
3. BẮT BUỘC gọi `submit_support_ticket` khi khách hàng cung cấp họ tên và yêu cầu hỗ trợ sự cố.
4. Khi không tìm thấy sản phẩm phù hợp, phải thông báo rõ ràng cho khách hàng thay vì tự sáng tạo dữ liệu.

## 4. OPERATIONAL BOUNDARIES
- Chỉ trả lời các câu hỏi và vấn đề liên quan đến hệ sinh thái Vingroup.
- Từ chối lịch sự nếu nhận được các yêu cầu ngoài phạm vi Vingroup.

## 5. OUTPUT CONTRACT
- Phản hồi bằng tiếng Việt lịch sự, định dạng có cấu trúc rõ ràng.
- Với ticket: Phải hiển thị rõ mã ticket ID (TK-...), tên khách hàng và mức độ ưu tiên.
- Với FAQ: Trả lời ngắn gọn, chuẩn xác theo chính sách của hãng.
"""


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ChatbotBaseline
# ═══════════════════════════════════════════════════════════════════════════

class ChatbotBaseline:
    """Baseline LLM Chatbot — Không sử dụng Tool Calling hay ReAct Loop."""

    def query(self, user_input: str) -> Dict[str, Any]:
        return {
            "answer": f"[Chatbot Baseline] Trả lời cho: {user_input}",
            "tool_calls": [],
            "status": "success",
            "mode": "mock_baseline"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CLASS: ToolCallingAgent
# ═══════════════════════════════════════════════════════════════════════════

class ToolCallingAgent:
    """Agent với System Prompt Engineering & Tool Calling."""

    def __init__(self, max_iterations: int = 5):
        self.max_iterations = max_iterations
        self.trace: List[Dict[str, Any]] = []

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []

        # Skeleton return
        self.trace.append({"step": "init", "user_input": user_input})
        return {
            "answer": "TODO: Implement ToolCallingAgent loop",
            "trace": self.trace,
            "iterations": 0,
            "status": "not_implemented"
        }


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh
# ═══════════════════════════════════════════════════════════════════════════

def main():
    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()
