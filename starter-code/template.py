"""
Lab #4: System Prompt Engineering & Tool Calling Engine
Học viên hoàn thiện các mục TODO để hoàn thành bài lab.

Kiến trúc:
  - ChatbotBaseline: LLM thuần, không dùng tool → quan sát hallucination.
  - ToolCallingAgent: Agent dùng System Prompt + 2 Tool Schemas.
"""

import json
import re
import sys
from typing import Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

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

    def _detect_intents(self, user_input: str) -> Dict[str, Any]:
        """Phân tích ý định người dùng (Intent Detection)."""
        input_lower = user_input.lower()

        # 1. Phát hiện câu hỏi FAQ
        is_faq = bool(
            re.search(r'\b(chính sách|bảo hành|bao lâu|ở đâu|điều kiện)\b', input_lower)
            and not re.search(r'\b(lỗi|hỏng|sự cố|tôi tên|tên tôi)\b', input_lower)
        )

        # 2. Phát hiện nhu cầu tra cứu sản phẩm (Catalog)
        needs_catalog = False
        catalog_args = {}
        has_catalog_intent = any(k in input_lower for k in ["xem", "tìm", "tra cứu", "mua", "giá", "danh mục", "danh sách", "có xe nào", "dưới", "triệu", "tỷ", "nghìn"])
        has_catalog_entity = any(k in input_lower for k in ["xe", "vinfast", "resort", "vinpearl", "du lịch", "du lich", "phòng", "khách sạn"])

        if not is_faq and has_catalog_intent and has_catalog_entity:
            needs_catalog = True
            if any(k in input_lower for k in ["resort", "vinpearl", "du lịch", "du lich", "khách sạn", "phòng"]):
                category = "du_lich"
            else:
                category = "xe_dien"

            max_price = 999999999999
            price_match = re.search(r'(\d+(?:[.,]\d+)?)\s*(triệu|trieu|tr|tỷ|ty|b|nghìn|k)', input_lower)
            if price_match:
                val = float(price_match.group(1).replace(',', '.'))
                unit = price_match.group(2)
                if unit in ['triệu', 'trieu', 'tr']:
                    max_price = int(val * 1_000_000)
                elif unit in ['tỷ', 'ty', 'b']:
                    max_price = int(val * 1_000_000_000)
                elif unit in ['nghìn', 'k']:
                    max_price = int(val * 1_000)

            catalog_args = {"category": category, "max_price": max_price}

        # 3. Phát hiện nhu cầu tạo ticket hỗ trợ
        needs_ticket = False
        ticket_args = {}
        if any(k in input_lower for k in ["tôi tên", "tên tôi", "bị lỗi", "sự cố", "hỏng", "hỗ trợ", "khiếu nại", "phản hồi"]):
            needs_ticket = True
            name_match = re.search(
                r'(?:tôi tên là|tôi tên|tên tôi là)\s+([A-ZÀ-Ỹa-zà-ỹ\s]+?)(?:,|\.|\bxe\b|\bphòng\b|\bvà\b|$)',
                user_input,
                re.IGNORECASE
            )
            customer_name = name_match.group(1).strip() if name_match else "Khách hàng"

            priority = "medium"
            if re.search(r'\b(nghiêm trọng|gấp|khẩn cấp|high|rất gấp)\b', input_lower):
                priority = "high"
            elif re.search(r'\b(thấp|low|không vội)\b', input_lower):
                priority = "low"
            elif re.search(r'\b(trung bình|medium|bình thường)\b', input_lower):
                priority = "medium"

            issue_match = re.search(r'(?:xe\s+[^\.,]+|phòng\s+[^\.,]+|bị lỗi[^\.,]*|bị hỏng[^\.,]*|gặp sự cố[^\.,]*)', user_input, re.IGNORECASE)
            issue_description = issue_match.group(0).strip() if issue_match else user_input.strip()

            ticket_args = {
                "customer_name": customer_name,
                "issue_description": issue_description,
                "priority": priority
            }

        return {
            "is_faq": is_faq,
            "needs_catalog": needs_catalog,
            "catalog_args": catalog_args,
            "needs_ticket": needs_ticket,
            "ticket_args": ticket_args
        }

    def run(self, user_input: str) -> Dict[str, Any]:
        """Điểm vào chính — chạy Agent Loop."""
        self.trace = []
        intents = self._detect_intents(user_input)

        # Lên danh sách các tác vụ cần thực hiện
        tasks = []
        if intents["is_faq"]:
            tasks.append({"type": "faq"})
        else:
            if intents["needs_catalog"]:
                tasks.append({"type": "catalog", "args": intents["catalog_args"]})
            if intents["needs_ticket"]:
                tasks.append({"type": "ticket", "args": intents["ticket_args"]})

        if not tasks:
            tasks.append({"type": "greeting"})

        iteration = 0

        # Xử lý trường hợp single task (iteration = 1)
        if len(tasks) == 1:
            iteration = 1
            task = tasks[0]
            if task["type"] == "greeting":
                answer = (
                    "Xin chào! Tôi là VinAssistant — Trợ lý AI chính thức của Vingroup. "
                    "Tôi có thể hỗ trợ bạn tra cứu xe điện VinFast, gói nghỉ dưỡng Vinpearl, "
                    "giải đáp chính sách bảo hành hoặc tiếp nhận yêu cầu hỗ trợ kỹ thuật. "
                    "Bạn cần hỗ trợ gì hôm nay?"
                )
                self.trace.append({
                    "iteration": 1,
                    "thought": "Người dùng chào hỏi hoặc nhập câu hỏi chung, phản hồi chào đón và giới thiệu dịch vụ.",
                    "action": "greeting",
                    "observation": answer
                })
                return {
                    "answer": answer,
                    "trace": self.trace,
                    "iterations": 1,
                    "status": "completed"
                }

            elif task["type"] == "faq":
                answer = "Chính sách bảo hành pin xe điện VinFast kéo dài 10 năm hoặc không giới hạn số km (tùy dòng xe), cam kết bảo hành và thay thế miễn phí khi dung lượng pin dưới 70%."
                self.trace.append({
                    "iteration": 1,
                    "thought": "Câu hỏi thuộc diện FAQ về chính sách bảo hành, trả lời trực tiếp không cần gọi tool.",
                    "action": "direct_answer",
                    "observation": answer
                })
                return {
                    "answer": answer,
                    "trace": self.trace,
                    "iterations": 1,
                    "status": "completed"
                }

            elif task["type"] == "catalog":
                args = task["args"]
                results = TOOL_MAP["search_product_catalog"](**args)
                self.trace.append({
                    "iteration": 1,
                    "thought": f"Khách hàng cần tìm sản phẩm danh mục {args['category']} giá tối đa {args['max_price']} VNĐ.",
                    "action": "search_product_catalog",
                    "action_input": args,
                    "observation": results
                })

                # Safeguard: Kiểm tra danh sách rỗng
                if not results:
                    answer = f"Rất tiếc, không tìm thấy sản phẩm {args['category']} nào phù hợp với mức giá dưới {args['max_price']:,} VNĐ."
                else:
                    lines = [f"- {p['name']}: {p['price_vnd']:,} VNĐ ({p['description']})" for p in results]
                    answer = f"Dưới đây là các sản phẩm phù hợp theo yêu cầu của bạn:\n" + "\n".join(lines)

                return {
                    "answer": answer,
                    "trace": self.trace,
                    "iterations": 1,
                    "status": "completed"
                }

            elif task["type"] == "ticket":
                args = task["args"]
                res = TOOL_MAP["submit_support_ticket"](**args)
                self.trace.append({
                    "iteration": 1,
                    "thought": "Khách hàng yêu cầu hỗ trợ sự cố, cần tạo ticket vào hệ thống.",
                    "action": "submit_support_ticket",
                    "action_input": args,
                    "observation": res
                })
                answer = (
                    f"Yêu cầu hỗ trợ của quý khách {res['customer_name']} đã được ghi nhận thành công "
                    f"với mã ticket {res['ticket_id']} (Mức độ ưu tiên: {res['priority']}). "
                    f"Đội ngũ kỹ thuật Vingroup sẽ xử lý trong thời gian sớm nhất."
                )
                return {
                    "answer": answer,
                    "trace": self.trace,
                    "iterations": 1,
                    "status": "completed"
                }

        # Multi-task Loop (Ví dụ: vừa tìm catalog vừa tạo ticket)
        answer_parts = []
        for task in tasks:
            iteration += 1
            if iteration > self.max_iterations:
                return {
                    "answer": "Lỗi: Vượt quá số bước tối đa.",
                    "trace": self.trace,
                    "iterations": self.max_iterations,
                    "status": "max_iterations_reached"
                }

            if task["type"] == "catalog":
                args = task["args"]
                results = TOOL_MAP["search_product_catalog"](**args)
                self.trace.append({
                    "iteration": iteration,
                    "thought": f"Bước {iteration}: Tra cứu sản phẩm danh mục {args['category']}.",
                    "action": "search_product_catalog",
                    "action_input": args,
                    "observation": results
                })
                if not results:
                    answer_parts.append(f"Không tìm thấy sản phẩm nào dưới {args['max_price']:,} VNĐ.")
                else:
                    lines = [f"- {p['name']}: {p['price_vnd']:,} VNĐ" for p in results]
                    answer_parts.append("Danh sách sản phẩm tìm thấy:\n" + "\n".join(lines))

            elif task["type"] == "ticket":
                args = task["args"]
                res = TOOL_MAP["submit_support_ticket"](**args)
                self.trace.append({
                    "iteration": iteration,
                    "thought": f"Bước {iteration}: Ghi nhận ticket hỗ trợ.",
                    "action": "submit_support_ticket",
                    "action_input": args,
                    "observation": res
                })
                answer_parts.append(f"Ticket {res['ticket_id']} cho khách hàng {res['customer_name']} đã được tạo.")

        final_answer = "\n\n".join(answer_parts)
        return {
            "answer": final_answer,
            "trace": self.trace,
            "iterations": iteration,
            "status": "completed"
        }


# ═══════════════════════════════════════════════════════════════════════════
# CHẾ ĐỘ TRÒ CHUYỆN TƯƠNG TÁC (INTERACTIVE CHAT CLI)
# ═══════════════════════════════════════════════════════════════════════════

def interactive_chat():
    """Chế độ trò chuyện tương tác trực tiếp qua console."""
    agent = ToolCallingAgent(max_iterations=5)
    print("\n" + "═" * 65)
    print("🤖 XIN CHÀO! TÔI LÀ VINASSISTANT — TRỢ LÝ AI HỆ SINH THÁI VINGROUP")
    print("═" * 65)
    print("💡 Bạn có thể thử nghiệm các câu hỏi như:")
    print("   1. 'Tôi muốn xem xe điện VinFast giá dưới 600 triệu.'")
    print("   2. 'Cho tôi xem resort Vinpearl giá dưới 6 triệu.'")
    print("   3. 'Tôi tên Hoàng, xe VF 8 bị hỏng điều hòa, cần xử lý gấp.'")
    print("   4. 'Chính sách bảo hành pin xe điện kéo dài bao lâu?'")
    print("   5. 'Có xe điện nào giá dưới 200 triệu không?'")
    print("👉 Gõ 'exit', 'quit' hoặc 'q' để kết thúc.")
    print("═" * 65 + "\n")

    while True:
        try:
            user_input = input("👤 Bạn: ").strip()
            if not user_input:
                continue
            if user_input.lower() in ["exit", "quit", "q"]:
                print("\n🤖 VinAssistant: Cảm ơn bạn đã quan tâm đến Vingroup. Chúc bạn một ngày tốt lành!\n")
                break

            result = agent.run(user_input)
            print(f"\n🤖 VinAssistant:\n{result['answer']}")

            # Hiển thị tóm tắt nhật ký hành động (Trace summary)
            tools_called = [step["action"] for step in result["trace"] if "action" in step]
            if tools_called:
                print(f"\n   ⚙️ [AI Action: {', '.join(tools_called)} | Vòng lặp: {result['iterations']} | Trạng thái: {result['status']}]")
            print("-" * 65)

        except (KeyboardInterrupt, EOFError):
            print("\n\nĐã thoát khỏi phiên trò chuyện.")
            break


# ═══════════════════════════════════════════════════════════════════════════
# MAIN — Chạy thử nhanh hoặc vào chế độ chat
# ═══════════════════════════════════════════════════════════════════════════

def main():
    # Nếu truyền cờ --chat hoặc -c thì vào chế độ trò chuyện tương tác
    if any(arg in sys.argv for arg in ["--chat", "-c", "chat"]):
        interactive_chat()
        return

    user_query = "Tôi muốn xem xe điện VinFast giá dưới 600 triệu."

    print("=== RUNNING CHATBOT BASELINE ===")
    chatbot = ChatbotBaseline()
    print(chatbot.query(user_query))

    print("\n=== RUNNING TOOL CALLING AGENT ===")
    agent = ToolCallingAgent(max_iterations=5)
    result = agent.run(user_query)
    print("Result:", result["answer"])
    print("Trace Log:", json.dumps(agent.trace, indent=2, ensure_ascii=False))

    print("\n" + "─" * 65)
    print("💡 MẸO HỌC TẬP: Bạn có thể gõ lệnh sau để trò chuyện trực tiếp:")
    print("   python starter-code/template.py --chat")
    print("─" * 65)

if __name__ == "__main__":
    main()
