import os
import json
import logging
from flask import Flask, request, jsonify
try:
    import google.generativeai as genai
    HAS_GENAI = True
except ImportError:
    HAS_GENAI = False

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

api_key = os.environ.get("GEMINI_API_KEY", "")
if api_key and HAS_GENAI:
    genai.configure(api_key=api_key)

db = {
    "category": {},
    "merchant": {},
    "trigger": {},
    "customer": {}
}

@app.route("/v1/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok"})

@app.route("/v1/metadata", methods=["GET"])
def metadata():
    return jsonify({
        "team_name": "Antigravity",
        "model": "gemini-pro-latest" if api_key else "fallback-heuristic"
    })

@app.route("/v1/context", methods=["POST"])
def push_context():
    data = request.json
    scope = data.get("scope")
    cid = data.get("context_id")
    payload = data.get("payload")
    version = data.get("version", 1)
    
    if scope in db:
        existing = db[scope].get(cid)
        if existing and existing.get("version", 0) >= version:
            return jsonify({"accepted": True, "note": "ignored or no-op"})
        db[scope][cid] = {"version": version, "payload": payload}
        return jsonify({"accepted": True})
    return jsonify({"accepted": False, "error": "Invalid scope"}), 400

def generate_message(category, merchant, trigger, customer):
    if not api_key or not HAS_GENAI:
        return _heuristic_fallback(category, merchant, trigger, customer)
        
    prompt = f"""You are Vera, an AI assistant for merchants on magicpin. 
Write a WhatsApp message to be sent to a merchant (or their customer, if on behalf of merchant).

Contexts:
Category: {json.dumps(category)}
Merchant: {json.dumps(merchant)}
Trigger: {json.dumps(trigger)}
Customer: {json.dumps(customer) if customer else 'None'}

Constraints:
1. Specificity: use verifiable facts (numbers, dates, precise benchmarks).
2. Category Fit: match the voice/tone of the category.
3. Merchant Fit: personal to this merchant and honors language.
4. Trigger Relevance: connect to the exact trigger reason.
5. Engagement Compulsion: use proof, urgency, curiosity, and one simple yes/no action.
6. Do NOT fabricate data. No fake claims. Respect the session rules: one clear CTA per send.

Output strictly in JSON format:
{{
  "body": "The actual message text",
  "cta": "YES", 
  "send_as": "vera", // or "merchant_on_behalf" if sending to customer
  "rationale": "Short explanation"
}}
"""
    try:
        model = genai.GenerativeModel('gemini-pro-latest')
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.0
            )
        )
        res = json.loads(response.text)
        # Ensure default keys
        if "body" not in res: res["body"] = "Update available. Reply YES."
        if "cta" not in res: res["cta"] = "YES"
        if "send_as" not in res: res["send_as"] = "merchant_on_behalf" if customer else "vera"
        if "rationale" not in res: res["rationale"] = "LLM generation"
        return res
    except Exception as e:
        logging.error(f"LLM Error: {e}")
        return _heuristic_fallback(category, merchant, trigger, customer)

def _heuristic_fallback(category, merchant, trigger, customer):
    send_as = "merchant_on_behalf" if customer else "vera"
    owner = merchant.get("identity", {}).get("owner_first_name", "merchant")
    cat_slug = category.get("slug", "business")
    kind = trigger.get("kind", "")
    
    if kind == "research_digest":
        body = f"Hi {owner}, new research in {cat_slug} is out! Want to see the latest update to boost your performance? Reply YES."
    elif kind == "perf_dip":
        body = f"Hi {owner}, your performance has dipped recently. We should fix it before it drops further. Reply YES to get started."
    elif kind == "recall_due" and customer:
        c_name = customer.get("identity", {}).get("name", "there")
        service = trigger.get("payload", {}).get("service_due", "service")
        body = f"Hi {c_name}, it's time for your {service} at {merchant.get('identity', {}).get('name', 'our clinic')}. Reply 1 to book your slot."
    else:
        body = f"Hi {owner}, important update regarding your account. Reply YES for details."
        
    return {
        "body": body,
        "cta": "YES",
        "send_as": send_as,
        "rationale": "Fallback heuristic"
    }

@app.route("/v1/tick", methods=["POST"])
def tick():
    data = request.json
    triggers = data.get("available_triggers", [])
    actions = []
    
    for tid in triggers:
        trigger_node = db["trigger"].get(tid, {})
        trigger = trigger_node.get("payload", trigger_node)
        merchant_id = trigger.get("merchant_id")
        customer_id = trigger.get("customer_id")
        
        merchant_node = db["merchant"].get(merchant_id, {})
        merchant = merchant_node.get("payload", merchant_node)
        
        category_slug = merchant.get("category_slug")
        category_node = db["category"].get(category_slug, {})
        category = category_node.get("payload", category_node)
        
        customer = None
        if customer_id:
            customer_node = db["customer"].get(customer_id, {})
            customer = customer_node.get("payload", customer_node)
        
        res = generate_message(category, merchant, trigger, customer)
        
        actions.append({
            "trigger_id": tid,
            "merchant_id": merchant_id,
            "customer_id": customer_id,
            "body": res.get("body", "Update available"),
            "cta": res.get("cta", "YES"),
            "send_as": res.get("send_as", "vera"),
            "rationale": res.get("rationale", "")
        })
        
    return jsonify({"actions": actions})

@app.route("/v1/reply", methods=["POST"])
def reply():
    data = request.json
    message = data.get("message", "").lower()
    
    if "auto" in message or "automated" in message or "team will respond" in message:
        return jsonify({"action": "end"})
    if "stop" in message or "spam" in message or "useless" in message:
        return jsonify({"action": "end", "body": "Sorry to bother you! We won't message again."})
    if "do it" in message or "go ahead" in message or "proceed" in message:
        return jsonify({"action": "send", "body": "Done! I've started the process for you. Anything else?"})
        
    return jsonify({"action": "send", "body": "Can you clarify? Reply YES to proceed."})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
