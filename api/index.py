import os, json, requests, datetime, hashlib
from flask import Flask, request, jsonify

app = Flask(__name__)

# ================= CONFIG =================
# ================= CONFIG =================
GITHUB_TOKEN = "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"
GITHUB_REPO = "MR-CR4CK3R/ff-tour"
API_SECRET_KEY = "itsmecrackerceo"
OWNER_ID = 7480892660
BASE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/contents"
HEADERS = {
    "Authorization": f"token {GITHUB_TOKEN}",
    "Accept": "application/vnd.github+json"
}

# ================= HELPER FUNCTIONS =================
def check_auth(req):
    auth = req.headers.get("Authorization","")
    if auth.startswith("Bearer "):
        token = auth.split(" ")[1]
        return token == API_SECRET_KEY
    return False

def hash_password(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

def get_file_content(path):
    url = f"{BASE_URL}/{path}"
    r = requests.get(url, headers=HEADERS)
    if r.status_code == 200:
        data = r.json()
        content = data['content']
        encoding = data['encoding']
        sha = data['sha']
        text = json.loads(requests.utils.unquote(content).encode().decode('base64')) if encoding=='base64' else json.loads(content)
        return text, sha
    elif r.status_code == 404:
        return None, None
    else:
        return None, None

def put_file_content(path, data, sha=None, message="Update file"):
    url = f"{BASE_URL}/{path}"
    content = json.dumps(data)
    payload = {"message": message, "content": content.encode("utf-8").decode("utf-8")}
    if sha: payload["sha"] = sha
    r = requests.put(url, headers=HEADERS, json=payload)
    return r.status_code == 201 or r.status_code == 200

# ================= DATA FILES =================
USERS_FILE = "data/users.json"
MATCHES_FILE = "data/matches.json"
TRANSACTIONS_FILE = "data/transactions.json"
RULES_FILE = "data/rules.json"
BROADCASTS_FILE = "data/broadcasts.json"

# ================= ROUTES =================

@app.route('/auth/signup', methods=['POST'])
def signup():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    userid = str(data.get("userid"))
    phone = data.get("phone")
    name = data.get("name")
    password = data.get("password")
    if not all([userid, phone, name, password]): return jsonify({"error":"Missing fields"}),400
    
    users, sha = get_file_content(USERS_FILE)
    if users is None: users = {}
    # Duplicate check
    user_count = sum(1 for u in users.values() if u['phone']==phone or str(u['userid'])==userid)
    if user_count >= 2: return jsonify({"error":"Max 2 accounts per phone/chat"}),400
    
    users[userid] = {
        "userid": userid,
        "phone": phone,
        "name": name,
        "password": hash_password(password),
        "main_balance":0,
        "winning_balance":0,
        "played_matches":0,
        "kills":0,
        "joined_matches":[],
        "is_banned":False
    }
    put_file_content(USERS_FILE, users, sha)
    return jsonify({"success":"Signup successful"}),200

@app.route('/auth/login', methods=['POST'])
def login():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    identifier = str(data.get("identifier"))
    password = data.get("password")
    userid = str(data.get("chat_id"))
    if not all([identifier,password]): return jsonify({"error":"Missing fields"}),400
    
    users,_ = get_file_content(USERS_FILE)
    if users is None: return jsonify({"error":"No users"}),404
    
    user = next((u for u in users.values() if u['phone']==identifier or str(u['userid'])==identifier), None)
    if not user: return jsonify({"error":"User not found"}),404
    if user['password'] != hash_password(password): return jsonify({"error":"Invalid password"}),403
    
    return jsonify({"success":"Login successful","token":API_SECRET_KEY}),200

@app.route('/users/<userid>', methods=['GET'])
def get_user(userid):
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    users,_ = get_file_content(USERS_FILE)
    user = users.get(userid) if users else None
    if not user: return jsonify({"error":"User not found"}),404
    return jsonify(user),200

@app.route('/wallet/convert', methods=['POST'])
def convert_wallet():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    userid = str(data.get("userid"))
    users, sha = get_file_content(USERS_FILE)
    if not users or userid not in users: return jsonify({"error":"User not found"}),404
    
    amt = users[userid]['winning_balance']
    users[userid]['winning_balance'] = 0
    users[userid]['main_balance'] += amt
    put_file_content(USERS_FILE, users, sha)
    return jsonify({"converted_amount": amt, "main_balance": users[userid]['main_balance']}),200

@app.route('/transactions/deposit', methods=['POST'])
def deposit():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    transactions, sha = get_file_content(TRANSACTIONS_FILE)
    if transactions is None: transactions = {"transactions":[]}
    txn_id = f"TXN{len(transactions['transactions'])+1:04d}"
    data['id'] = txn_id
    data['type'] = "deposit"
    data['status'] = "pending"
    transactions['transactions'].append(data)
    put_file_content(TRANSACTIONS_FILE, transactions, sha)
    return jsonify({"success":"Deposit request created","id":txn_id}),200

@app.route('/transactions/withdraw', methods=['POST'])
def withdraw():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    userid = str(data.get("userid"))
    amount = float(data.get("amount",0))
    users, u_sha = get_file_content(USERS_FILE)
    if not users or userid not in users: return jsonify({"error":"User not found"}),404
    if users[userid]['winning_balance'] < amount: return jsonify({"error":"Insufficient balance"}),400
    
    fee = round(amount*0.05,2)
    final_amount = amount - fee
    users[userid]['winning_balance'] -= amount
    put_file_content(USERS_FILE, users, u_sha)
    
    transactions, t_sha = get_file_content(TRANSACTIONS_FILE)
    if transactions is None: transactions = {"transactions":[]}
    txn_id = f"TXN{len(transactions['transactions'])+1:04d}"
    data.update({"id":txn_id,"type":"withdraw","fee":fee,"final_amount":final_amount,"status":"pending"})
    transactions['transactions'].append(data)
    put_file_content(TRANSACTIONS_FILE, transactions, t_sha)
    return jsonify({"success":"Withdraw request created","fee":fee,"final_amount":final_amount}),200

@app.route('/transactions/pending', methods=['GET'])
def pending_transactions():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    txn_type = request.args.get("type")
    transactions,_ = get_file_content(TRANSACTIONS_FILE)
    pending = [t for t in transactions['transactions'] if t['status']=='pending' and t['type']==txn_type] if transactions else []
    return jsonify({"pending_transactions": pending}),200

@app.route('/admin/transaction/<txn_type>', methods=['POST'])
def admin_process_transaction(txn_type):
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    txn_id = data.get("transaction_id")
    action = data.get("action")  # yes/no
    users, u_sha = get_file_content(USERS_FILE)
    transactions, t_sha = get_file_content(TRANSACTIONS_FILE)
    txn = next((t for t in transactions['transactions'] if t['id']==txn_id), None)
    if not txn: return jsonify({"error":"Transaction not found"}),404
    
    userid = str(txn['userid'])
    if action=="yes":
        if txn_type=="deposit":
            users[userid]['main_balance'] += txn['amount']
        elif txn_type=="withdraw":
            pass # already deducted
        txn['status']="success"
    else:
        txn['status']="failed"
        if txn_type=="withdraw":
            users[userid]['winning_balance'] += txn['amount'] # refund
    
    put_file_content(USERS_FILE, users, u_sha)
    put_file_content(TRANSACTIONS_FILE, transactions, t_sha)
    
    return jsonify({"success":f"Transaction {txn_id} updated","user_id":userid}),200

@app.route('/matches/upcoming', methods=['GET'])
def upcoming_matches():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    matches,_ = get_file_content(MATCHES_FILE)
    if not matches: matches = {"matches":[]}
    upcoming = [m for m in matches['matches'] if m['status']=='upcoming']
    return jsonify({"matches":upcoming}),200

@app.route('/matches/<match_id>', methods=['GET'])
def get_match(match_id):
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    matches,_ = get_file_content(MATCHES_FILE)
    if not matches: matches = {"matches":[]}
    match = next((m for m in matches['matches'] if m['match_id']==match_id), None)
    if not match: return jsonify({"error":"Match not found"}),404
    return jsonify(match),200

@app.route('/matches/join', methods=['POST'])
def join_match():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    data = request.json
    userid = str(data.get("userid"))
    match_id = data.get("match_id")
    uid = data.get("uid")
    ff_name = data.get("ff_name","Unknown")
    
    users, u_sha = get_file_content(USERS_FILE)
    matches, m_sha = get_file_content(MATCHES_FILE)
    if not users or userid not in users: return jsonify({"error":"User not found"}),404
    match = next((m for m in matches['matches'] if m['match_id']==match_id), None)
    if not match: return jsonify({"error":"Match not found"}),404
    if users[userid]['main_balance']<match['entry_fee']: return jsonify({"error":"Insufficient main balance"}),400
    
    users[userid]['main_balance'] -= match['entry_fee']
    match['joined_users'].append({"userid":userid,"uid":uid,"ff_name":ff_name})
    put_file_content(USERS_FILE, users, u_sha)
    put_file_content(MATCHES_FILE, matches, m_sha)
    return jsonify({"success":"Joined match"}),200

@app.route('/rules', methods=['GET'])
def get_rules():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    rules,_ = get_file_content(RULES_FILE)
    if not rules: rules = {"BR":"Default BR Rules","CS":"Default CS Rules"}
    return jsonify(rules),200

@app.route('/settings/deposit_info', methods=['GET'])
def deposit_info():
    if not check_auth(request): return jsonify({"error":"Unauthorized"}), 401
    method = request.args.get("method")
    return jsonify({"number":"01XXXXXXXXX"}),200

# ================= RUN =================
if __name__=="__main__":
    app.run(debug=True)
