import datetime
import hashlib
import hmac

from flask import Flask, jsonify, request
from flask_mongoengine import MongoEngine
from constants import DB_CONNECTION_STRING, REPO_NAME, HACKTOBERFEST_ACCEPTED, PR_STATE_CLOSED, WEBHOOK_SECRET
import json

app = Flask(__name__)
app.config["MONGODB_HOST"] = DB_CONNECTION_STRING

db = MongoEngine()
db.init_app(app)


# MODEL
class User(db.Document):
    nickname = db.StringField()
    name = db.StringField()
    surname = db.StringField()

    def to_json(self) -> dict:
        return {'nickname': self.nickname, 'name': self.name, 'surname': self.surname}


class Problem(db.Document):
    problem_id = db.StringField()
    name = db.StringField()
    level_name = db.StringField()
    base_points = db.FloatField()
    multiplier = db.FloatField()
    description = db.StringField()

    def to_json(self):
        return {'id': self.problem_id, 'name': self.name, 'level_name': self.level_name,
                'base_points': self.base_points, 'multiplier': self.multiplier, 'description': self.description}


class PullRequest(db.Document):
    pr_id = db.StringField()
    problem_id = db.StringField()
    nickname = db.StringField()
    bonus_points = db.FloatField()
    bonus_comment = db.StringField()
    merge_time = db.DateTimeField()
    reviewed = db.BooleanField()
    reviewed_at = db.DateTimeField()

    def to_json(self):
        return {'id': self.pr_id, 'problem_id': self.problem_id, 'nickname': self.nickname,
                'bonus_points': self.bonus_points, 'bonus_comment': self.bonus_comment, 'merge_time': self.merge_time,
                'reviewed': self.reviewed, 'reviewed_at': self.reviewed_at}


"""class FreezeTime(db.Document):
    curr_time = db.DateTimeField()
    freeze_datetime = db.DateTimeField()

    def to_json(self):
        return {'freeze_datetime': self.freeze_datetime}
"""


# CONTROLLER

# users
def get_user(nickname: str) -> dict:
    user = User.objects(nickname=nickname).first()
    if not user:
        return {'error': 'user not found'}
    return user.to_json()


def get_all_users() -> list:
    return [user.to_json() for user in User.objects()]


def add_user(data: json) -> dict:
    if User.objects(nickname=data['nickname']).first():
        return {'error': 'user present'}
    user = User(nickname=data['nickname'], name=data['name'], surname=data['surname'])
    user.save()
    return user.to_json()


def edit_user(nickname: str, data: json) -> dict:
    user = User.objects(nickname=nickname).first()
    if not user:
        return {'error': 'user not found'}
    user.update(name=data['name'], surname=data['surname'])
    return User.objects(nickname=nickname).first().to_json()


def remove_user(nickname: str) -> dict:
    user = User.objects(nickname=nickname).first()
    if not user:
        return {'error': 'user not found'}
    user.delete()
    return user.to_json()


# ----------------


# problems
def get_problem(problem_id: str) -> dict:
    problem = Problem.objects(problem_id=problem_id).first()
    if not problem:
        return {'error': 'problem not found'}
    return problem.to_json()


def get_all_problems() -> list:
    return [problem.to_json() for problem in Problem.objects()]


def add_problem(data: json) -> dict:
    if Problem.objects(problem_id=data['id']).first():
        return {'error': 'problem present'}
    problem = Problem(problem_id=data['id'], name=data['name'], level_name=data['level_name'],
                      base_points=data['base_points'],
                      multiplier=data['multiplier'], description=data['description'])
    problem.save()
    return problem.to_json()


def edit_problem(problem_id: str, data: json) -> dict:
    problem = Problem.objects(problem_id=problem_id).first()
    if not problem:
        return {'error': 'problem not found'}
    problem.update(name=data['name'], level_name=data['level_name'], base_points=data['base_points'],
                   multiplier=data['multiplier'], description=data['description'])
    return Problem.objects(problem_id=problem_id).first().to_json()


def remove_problem(problem_id: str) -> dict:
    problem = Problem.objects(problem_id=problem_id).first()
    if not problem:
        return {'error': 'problem not found'}
    problem.delete()
    return problem.to_json()


# ----------------


# pull_request
def get_pr(pr_id: str) -> dict:
    pr = PullRequest.objects(pr_id=pr_id).first()
    if not pr:
        return {'error': 'pr not found'}
    return pr.to_json()


def get_all_prs() -> list:
    return [pr.to_json() for pr in PullRequest.objects()]


def add_pr(data: json) -> dict:
    user = User.objects(nickname=data['nickname']).first()
    if not user:
        return {'error': 'user not found'}
    problem = Problem.objects(problem_id=data['problem_id']).first()
    if not problem:
        return {'error': 'problem not found'}
    if PullRequest.objects(pr_id=data['id']).first():
        return {'error': 'pr present'}
    pr = PullRequest(pr_id=data['id'], problem_id=data['problem_id'], nickname=data['nickname'],
                     bonus_points=data['bonus_points'], bonus_comment=data['bonus_comment'],
                     merge_time=datetime.datetime.now())
    pr.save()
    return pr.to_json()


def edit_pr(pr_id: str, data: json) -> dict:
    pr = PullRequest.objects(pr_id=pr_id).first()
    if not pr:
        return {'error': 'pr not found'}
    pr.update(problem_id=data['problem_id'],
              bonus_points=data['bonus_points'], bonus_comment=data['bonus_comment'], reviewed=data['reviewed'],
              reviewed_at=datetime.datetime.now())
    return PullRequest.objects(pr_id=pr_id).first().to_json()


def remove_pr(pr_id: str) -> dict:
    pr = PullRequest.objects(pr_id=pr_id).first()
    if not pr:
        return {'error': 'pr not found'}
    pr.delete()
    return pr.to_json()


# ----------------


# ranking
def get_ranking() -> list:
    users = get_all_users()
    problems = get_all_problems()
    prs = get_all_prs()
    # time_limit = datetime.datetime(2021, 10, 20, 15, 00, 00)  # get_freeze_ranking_time()
    # prs = [_ for _ in filter(lambda pr: pr['merge_time'] < time_limit and pr['reviewed'], prs)]
    prs = [_ for _ in filter(lambda pr: pr['reviewed'], prs)]

    out = []
    for user in users:
        user_prs_list = filter(lambda pr: pr['nickname'] == user['nickname'], prs)
        user['points'] = 0
        for _pr in user_prs_list:
            user_problems_list = [_ for _ in filter(lambda problem: problem['id'] == _pr['problem_id'], problems)]
            assert len(user_problems_list) == 1
            user['points'] += float(_pr['bonus_points']) + float(user_problems_list[0]['base_points']) * float(
                user_problems_list[0]['multiplier'])
        out.append(user)

    return out


"""
def get_freeze_ranking_time() -> datetime.datetime:
    freeze_time = FreezeTime.objects().order_by('-curr_time').first()
    if not freeze_time:
        return datetime.datetime.now()
    return freeze_time.to_json()['freeze_datetime']


def set_freeze_ranking_time(data: json) -> dict:
    date_time = FreezeTime.objects(freeze_datetime=data['datetime']).first()
    if date_time:
        date_time.update(curr_time=datetime.datetime.now())
        return date_time.to_json()
    date_time = FreezeTime(curr_time=datetime.datetime.now(), freeze_datetime=data['datetime'])
    date_time.save()
    return date_time.to_json()
"""


# ----------------

def verify_github_headers(signature: str, payload_body: bytes) -> bool:
    secret: bytes = WEBHOOK_SECRET.encode()
    hmac_gen = hmac.new(secret, payload_body, hashlib.sha256)
    digest = "sha256=" + hmac_gen.hexdigest()
    return hmac.compare_digest(digest, signature)


def github(data: json) -> None:
    # checks for fields in json
    if 'pull_request' not in data or 'number' not in data['pull_request'] or 'state' not in data['pull_request'] or \
            'user' not in data['pull_request'] or 'login' not in data['pull_request']['user'] or \
            'merged_at' not in data['pull_request'] or 'labels' not in data['pull_request'] or \
            'repository' not in data or 'full_name' not in data['repository']:
        return

    hacktoberfest_accepted_found = False
    # checks for right label in pull_request
    for elem in data['pull_request']['labels']:
        if 'name' not in elem:
            return
        if elem['name'] == HACKTOBERFEST_ACCEPTED:
            hacktoberfest_accepted_found = True

    # checks for right repo and correct repo state
    if data['repository']['full_name'] not in REPO_NAME or not hacktoberfest_accepted_found or \
            data['pull_request']['merged'] is False or data['action'] != PR_STATE_CLOSED:
        return

    pr_username = data['pull_request']['user']['login']
    pr_number = data['pull_request']['number']
    pr_merged_at = data['pull_request']['merged_at']

    user = User.objects(nickname=pr_username).first()
    if not user:
        return

    pr_merged_at = datetime.datetime.strptime(pr_merged_at, "%Y-%m-%dT%H:%M:%SZ")
    pr = PullRequest(pr_id=str(pr_number), problem_id="", nickname=str(pr_username),
                     bonus_points=0, bonus_comment="",
                     merge_time=pr_merged_at, reviewed=False, reviewed_at=datetime.datetime(1970, 1, 1, 0, 0, 0))
    pr.save()


# VIEW
@app.route('/api/hello')
def root():
    return jsonify({'server_status': 'online'})


@app.route('/api/user', methods=['GET'])
def view_get_all_users():
    if 'nickname' in request.args:
        return jsonify(get_user(request.args.get('nickname')))
    return jsonify(get_all_users())


@app.route('/api/user', methods=['POST'])
def view_add_user():
    data = json.loads(request.data)
    return jsonify(add_user(data))


@app.route('/api/user/<nickname>', methods=['PUT'])
def view_edit_user(nickname):
    data = json.loads(request.data)
    return jsonify(edit_user(nickname, data))


@app.route('/api/user/<nickname>', methods=['DELETE'])
def view_remove_user(nickname):
    return jsonify(remove_user(nickname))


@app.route('/api/problem', methods=['GET'])
def view_get_all_problems():
    if 'id' in request.args:
        return jsonify(get_problem(request.args.get('id')))
    return jsonify(get_all_problems())


@app.route('/api/problem', methods=['POST'])
def view_add_problem():
    data = json.loads(request.data)
    return jsonify(add_problem(data))


@app.route('/api/problem/<problem_id>', methods=['PUT'])
def view_edit_problem(problem_id):
    data = json.loads(request.data)
    return jsonify(edit_problem(problem_id, data))


@app.route('/api/problem/<problem_id>', methods=['DELETE'])
def view_remove_problem(problem_id):
    return jsonify(remove_problem(problem_id))


@app.route('/api/pr', methods=['GET'])
def view_get_all_prs():
    if 'id' in request.args:
        return jsonify(get_pr(request.args.get('id')))
    return jsonify(get_all_prs())


@app.route('/api/pr', methods=['POST'])
def view_add_pr():
    data = json.loads(request.data)
    return jsonify(add_pr(data))


@app.route('/api/pr/<pr_id>', methods=['PUT'])
def view_edit_pr(pr_id):
    data = json.loads(request.data)
    return jsonify(edit_pr(pr_id, data))


@app.route('/api/pr/<pr_id>', methods=['DELETE'])
def view_remove_pr(pr_id):
    return jsonify(remove_pr(pr_id))


@app.route('/public/ranking', methods=['GET'])
def view_get_current_ranking():
    return jsonify(get_ranking())


"""
@app.route('/api/ranking', methods=['POST'])
def view_set_freeze_ranking():
    data = json.loads(request.data)
    return jsonify(set_freeze_ranking_time(data))
"""


@app.route('/github', methods=['POST'])
def view_github():
    if not verify_github_headers(request.headers.get('X-Hub-Signature-256'), request.data):
        return jsonify({'error': 'unauthorized'}), 403
    data = json.loads(request.data)
    github(data)
    return jsonify({'response': 'ok'}), 200


@app.route('/servertime', methods=['GET'])
def get_server_time():
    return jsonify({'datetime': datetime.datetime.now()})


if __name__ == '__main__':
    app.run()
