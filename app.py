import os
import base64
import random
import requests
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

BASE_URL = "https://exam.prsuuniv.in"

def encode_b64(value):
    return base64.b64encode(str(value).encode('utf-8')).decode('utf-8')

COURSE_MAP = {
    "bed_4": {
        "coursename": "Bachelor of Education",
        "semester": "4",
        "studentty": "REGULAR"
    },
    "msc_botany_2": {
        "coursename": "Master of Science in Botany",
        "semester": "2",
        "studentty": "REGULAR"
    }
}

@app.route('/get-result-url', methods=['POST', 'OPTIONS'])
def get_result_url():
    if request.method == 'OPTIONS':
        return jsonify({"status": "ok"}), 200

    try:
        data = request.get_json(force=True, silent=True) or {}
        roll_number = str(data.get("roll_number", "")).strip()
        course_key = data.get("course_key", "bed_4")

        if not roll_number:
            return jsonify({"success": False, "error": "Roll number is required"}), 400

        course_info = COURSE_MAP.get(course_key)
        if not course_info:
            return jsonify({"success": False, "error": "Invalid course selected"}), 400

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest"
        })

        studentty_b64 = encode_b64(course_info["studentty"])
        semester_b64 = encode_b64(course_info["semester"])
        coursename_b64 = encode_b64(course_info["coursename"])
        
        salted_roll = f"{random.randint(1000, 9999)}{roll_number}@@{random.randint(1000, 9999)}"
        examroll_b64 = encode_b64(salted_roll)

        endpoint = f"{BASE_URL}/prsuresult/home/student/result/msw/check19/{semester_b64}/{studentty_b64}/{examroll_b64}/{coursename_b64}/resultrack"

        response = session.get(endpoint, timeout=15)
        res_data = response.json()

        # Handle Status 2 (ABC ID Verification step required by PRSU)
        if res_data.get("status") == 2 and res_data.get("message"):
            try:
                msg_parts = res_data.get("message").split("@")
                ansidrno = msg_parts[0] if len(msg_parts) > 0 else ""
                student_id = msg_parts[1] if len(msg_parts) > 1 else ""
                name = msg_parts[2] if len(msg_parts) > 2 else ""
                dob = msg_parts[3] if len(msg_parts) > 3 else ""

                # Step 1: Query ABC ID info
                abc_url = f"{BASE_URL}/prsuform/abcidfromenroll"
                abc_res = session.get(abc_url, params={
                    "ansidrno": ansidrno,
                    "student_id": student_id,
                    "name": name,
                    "dob": dob
                }, timeout=10).json()

                # Step 2: Post verification update if record found
                if abc_res and isinstance(abc_res, list) and len(abc_res) > 0:
                    rec = abc_res[0]
                    if rec.get("abcid"):
                        session.post(f"{BASE_URL}/prsuresult/student/updateResultAbcid", data={
                            "abcid": rec.get("abcid"),
                            "ansidrno": rec.get("ansidrno"),
                            "student_id": rec.get("student_id")
                        }, timeout=10)
            except Exception as e:
                print(f"ABC Verification sub-step skipped: {e}")

        # Extract direct redirect link
        redirect_path = res_data.get("redirect")
        if redirect_path:
            redirect_path = redirect_path.strip('"')
            full_url = f"{BASE_URL}{redirect_path}"
            return jsonify({"success": True, "result_url": full_url}), 200
        else:
            return jsonify({"success": False, "error": "Result not found on PRSU server."}), 404

    except Exception as e:
        print(f"Error processing request: {e}")
        return jsonify({"success": False, "error": "Failed to connect to PRSU server."}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
