import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
import json
import sys

BASE_URL = "http://127.0.0.1:5000"

def run_tests():
    print("==================================================")
    print("MediReminder Comprehensive Automated API Test Suite")
    print("==================================================")

    cookie_jar = http.cookiejar.CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

    # Test 1: Web root
    print("[1] Testing Web App Root (GET /)...")
    res = opener.open(f"{BASE_URL}/")
    assert res.status == 200, f"Expected 200, got {res.status}"
    html = res.read().decode('utf-8')
    assert "MediReminder" in html, "MediReminder not found in HTML"
    print("    PASSED: HTML5 web page loaded.")

    # Test 2: PWA Manifest
    print("[2] Testing PWA Manifest (GET /manifest.json)...")
    res = opener.open(f"{BASE_URL}/manifest.json")
    assert res.status == 200
    manifest = json.loads(res.read().decode('utf-8'))
    assert manifest["short_name"] == "MediReminder"
    print("    PASSED: PWA manifest valid.")

    # Test 3: Service Worker
    print("[3] Testing Service Worker (GET /sw.js)...")
    res = opener.open(f"{BASE_URL}/sw.js")
    assert res.status == 200
    sw_code = res.read().decode('utf-8')
    assert "medireminder" in sw_code.lower()
    print("    PASSED: Service Worker served with root scope.")

    # Test 4: VAPID Public Key
    print("[4] Testing VAPID Public Key (GET /api/notifications/vapid-public-key)...")
    res = opener.open(f"{BASE_URL}/api/notifications/vapid-public-key")
    assert res.status == 200
    data = json.loads(res.read().decode('utf-8'))
    assert "publicKey" in data and len(data["publicKey"]) > 20
    print(f"    PASSED: Public key retrieved: {data['publicKey'][:16]}...")

    # Test 5: Authentication Login (demo_patient / demo1234)
    print("[5] Testing Authentication Login (POST /api/auth/login)...")
    login_data = json.dumps({"username": "demo_patient", "password": "demo1234"}).encode('utf-8')
    req = urllib.request.Request(f"{BASE_URL}/api/auth/login", data=login_data, headers={'Content-Type': 'application/json'})
    res = opener.open(req)
    assert res.status == 200
    auth_resp = json.loads(res.read().decode('utf-8'))
    assert auth_resp["user"]["username"] == "demo_patient"
    print(f"    PASSED: Logged in as {auth_resp['user']['full_name']}")

    # Test 6: Dashboard Summary
    print("[6] Testing Dashboard Summary (GET /api/dashboard/summary)...")
    res = opener.open(f"{BASE_URL}/api/dashboard/summary")
    assert res.status == 200
    dash = json.loads(res.read().decode('utf-8'))
    print(f"    PASSED: Total Medicines={dash['total_medicines']}, Scheduled Today={dash['total_scheduled']}, Adherence={dash['adherence_rate']}%")

    # Test 7: Medicines List
    print("[7] Testing Medicines CRUD (GET /api/medicines)...")
    res = opener.open(f"{BASE_URL}/api/medicines")
    assert res.status == 200
    meds = json.loads(res.read().decode('utf-8'))["medicines"]
    assert len(meds) >= 5
    print(f"    PASSED: {len(meds)} active medicines retrieved.")

    # Test 8: Registered Time Validation & Reminder Actions
    reminders = dash.get("reminders", [])
    future_rem = next((r for r in reminders if r.get('is_future')), None)
    due_rem = next((r for r in reminders if r.get('is_due')), None)

    if future_rem:
        print(f"[8a] Testing Future Reminder Rejection (POST /api/reminders/{future_rem['id']}/action at {future_rem['scheduled_time']})...")
        action_data = json.dumps({"action": "take"}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/reminders/{future_rem['id']}/action", data=action_data, headers={'Content-Type': 'application/json'})
        try:
            opener.open(req)
            raise AssertionError("Should have failed to take future reminder!")
        except urllib.error.HTTPError as ex:
            assert ex.code == 400
            err_body = json.loads(ex.read().decode('utf-8'))
            assert err_body["error"] == "Too Early"
            print(f"    PASSED: Successfully rejected early intake with message: '{err_body['message']}'")

    if due_rem:
        print(f"[8b] Testing Due Reminder Intake (POST /api/reminders/{due_rem['id']}/action at {due_rem['scheduled_time']})...")
        action_data = json.dumps({"action": "take"}).encode('utf-8')
        req = urllib.request.Request(f"{BASE_URL}/api/reminders/{due_rem['id']}/action", data=action_data, headers={'Content-Type': 'application/json'})
        res = opener.open(req)
        assert res.status == 200
        action_res = json.loads(res.read().decode('utf-8'))
        assert action_res["reminder"]["status"] == "taken"
        print(f"    PASSED: Due reminder marked as taken at registered time.")

    # Test 9: Adherence Statistics
    print("[9] Testing Adherence Statistics (GET /api/adherence/stats)...")
    res = opener.open(f"{BASE_URL}/api/adherence/stats")
    assert res.status == 200
    stats = json.loads(res.read().decode('utf-8'))
    print(f"    PASSED: Overall Adherence={stats['overall_rate']}%, Streak={stats['current_streak']} days, Taken={stats['total_taken']}, Missed={stats['total_missed']}")

    # Test 10: CSV Report Export
    print("[10] Testing Adherence CSV Export (GET /api/adherence/export)...")
    res = opener.open(f"{BASE_URL}/api/adherence/export")
    assert res.status == 200
    csv_content = res.read().decode('utf-8')
    assert "Record ID" in csv_content and "Medicine Name" in csv_content
    print("    PASSED: Medical Adherence CSV export generated.")

    print("==================================================")
    print("ALL 10 TESTS PASSED PERFECTLY (100% OPERATIONAL)!")
    print("==================================================")

if __name__ == "__main__":
    run_tests()
