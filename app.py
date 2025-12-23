from flask import Flask, render_template, request, redirect, flash, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user, UserMixin
from flask_pymongo import PyMongo
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from os import getenv
from bson import ObjectId
from re import match
from datetime import datetime
from zoneinfo import ZoneInfo
from waitress import serve
from random import choice

load_dotenv()




app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = getenv('SECRET_KEY')
app.config['SESSION_TYPE'] = 'mongodb'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_message = None

@login_manager.unauthorized_handler
def unauthorized():
    return redirect(url_for('login_page'))

class User(UserMixin):
    def __init__(self, id, name, number, password, admin, money, current_team, betted_money):
        self.id = id
        self.name = name
        self.number = number
        self.password = password
        self.admin = admin
        self.money = money
        self.current_team = current_team
        self.betted_money = betted_money

    def __repr__(self):
        r = {
            'user_id': self.id,
            'name': self.name,
            'number': self.number,
            'password': self.password,
            'admin': self.admin,
            'money': self.money,
            'current_team': self.current_team,
            'self.betted_money': self.betted_money
        }
        return str(r)
    
    def is_active(self):
        return True
    
    def is_admin(self):
        return self.admin

    def get_id(self):
        return self.id

    def get_name(self):
        return self.name
    
    def get_number(self):
        return self.number
    
    def get_money(self):
        return self.money
    
    def get_current_team(self):
        return self.current_team
    
    def get_betted_money(self):
        return self.betted_money
    
    def set_money(self, amount):
        self.money = amount

    def set_current_team(self, team):
        self.team = team

    def set_betted_money(self, money):
        self.betted_money = money




mongo = PyMongo()
client = MongoClient(getenv("DB_CONNECT"), 27017)
db = client['tatta']
user_collection = db['user']
history_collection = db['history']




@login_manager.user_loader
def user_loader(user_id):
    target_user = user_collection.find_one({"_id":ObjectId(str(user_id))})
    target_user['id'] = str(target_user.pop('_id'))
    return User(**target_user)




def number_comma(num: str):
    return str(format(int(num), ','))

app.jinja_env.filters["number_comma"] = number_comma

def unix_to_date(t):
    date = datetime.fromtimestamp(t)
    today = datetime.today()
    diff = today - date

    if diff.days == 0:
        return datetime.fromtimestamp(t, tz=ZoneInfo("Asia/Seoul")).strftime('%H시 %M분 %S초')
    else:
        return datetime.fromtimestamp(t, tz=ZoneInfo("Asia/Seoul")).strftime('%Y년 %m월 %d일')

app.jinja_env.filters["unixtime"] = unix_to_date




@app.route("/")
def main_page():
    users = list(user_collection.find())
    total_money = {'1':0,'2':0,'3':0,'4':0}
    for user in users:
        if user['current_team'] != None:
            total_money[str(user['current_team'])] += int(user['betted_money'])
    sum_money = sum(total_money.values())

    def div(one, two):
        if two==0: return 0
        return round(one/two,2)

    rate = {
        '1':div(sum_money,total_money['1']),
        '2':div(sum_money,total_money['2']),
        '3':div(sum_money,total_money['3']),
        '4':div(sum_money,total_money['4'])
    }

    histories = list(history_collection.find())
    histories.sort(key=lambda x : -x['time'])

    return render_template('main.html', total_money=total_money, rate=rate, history=histories[0])




def is_valid_number(student_id):
    if not student_id.isdigit() or len(student_id) != 4: return False
    grade = int(student_id[0])
    classroom = int(student_id[1])
    number = int(student_id[2:])
    if not (1 <= grade <= 3): return False
    if not (1 <= classroom <= 8): return False
    if not (1 <= number <= 35): return False
    return True

@app.route("/signup", methods=["GET", "POST"])
def signup_page():
    if request.method == "POST":
        name = request.form.get('name')
        number = request.form.get('number')
        password = request.form.get('password')
        if not bool(match(r'^[가-힣]{2,4}$', name)): return redirect('/')
        elif not is_valid_number(number): return redirect('/')
        elif user_collection.find_one({'name':name, 'number':int(number)}): return redirect('/')

        user_data = {
            'name':name,
            'number':int(number),
            'password':password,
            'admin': False,
            'money':5000,
            'current_team':None,
            'betted_money':0
        }
        user_collection.insert_one(user_data)
        target_user = user_collection.find_one(user_data)
        if not target_user:
            print('huh?')
            return redirect('/login')
        target_user['id'] = str(target_user.pop('_id'))
        login_user(User(**target_user))
        flash("✅ 회원 가입이 정상적으로 완료되었습니다.")
        return redirect('/')
    else:
        if current_user.is_authenticated: return redirect('/')
        return render_template('signup.html')
    



@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method == "POST":
        name = request.form.get('name')
        number = request.form.get('number')
        password = request.form.get('password')

        target_user = user_collection.find_one({'name':name, 'number':int(number), 'password':password})
        if target_user:
            target_user['id'] = str(target_user.pop('_id'))
            login_user(User(**target_user))
            flash("✅ 로그인 되었습니다.")
            return redirect('/')
        else:
            return redirect('/login')
    else:
        if current_user.is_authenticated: return redirect('/')
        return render_template('login.html')




@app.route("/logout")
def logout_page():
    logout_user()
    flash("✅ 로그아웃 되었습니다.")
    return redirect('/')




@app.route('/betting', methods=['GET', 'POST'])
@login_required
def betting_page():
    if request.method == "POST":
        team = request.form.get('team')
        money = request.form.get('money')
        if not (1<=int(team)<=4): flash("❌ 팀은 4개뿐입니다.")
        elif int(money)<=0: flash("❌ 최소 1원이라도 거시죠?")
        elif int(money)>current_user.get_money(): flash("❌ 가진 만큼만 거세요.")
        elif current_user.get_current_team() != None or current_user.get_betted_money() != 0: flash("❌ 이미 베팅하였습니다.")
        else:
            target_user = user_collection.find_one({'_id':ObjectId(current_user.get_id())})
            if not target_user:
                flash(f"❌ 오류가 발생했습니다. 재로그인 후 이용해주세요.")
            else:
                current_user.set_money(current_user.get_money()-int(money))
                current_user.set_current_team(int(team))
                current_user.set_betted_money(int(money))

                user_collection.update_one({'_id':ObjectId(current_user.get_id())}, {'$inc':{'money':-int(money)}, "$set":{"current_team":int(team), "betted_money":int(money)}})
                flash(f"✅ {team}팀에 {money}원 베팅하였습니다.")
        return redirect('/')
    else:
        team = request.args.get("t", type=int)
        if not (1<=team<=4): return redirect('/')
        elif current_user.get_current_team() != None or current_user.get_betted_money() != 0:
            flash("❌ 이미 베팅하였습니다.")
            return redirect('/')
        return render_template('betting.html', team=team)




code = ['신앙은 덧없는 인간을 위하여', '달까지 닿아라 불사의 연기', '죽취비상', '성조기의 피에로', '죽은 왕녀를 위한 셉텟', '감정의 마천루', '요요발호', '유령악단', '우상에 세계를 맡기고', '네크로판타지아', '하르트만의 요괴소녀', '네이티브 페이스', '풍신소녀', '동쪽 나라의 잠들지 않는 밤']

@app.route('/admin/panel', methods=['GET', 'POST'])
@login_required
def admin_panel_page():
    if current_user.is_admin():
        return render_template('admin_panel.html', code=choice(code))
    return redirect('/')




@app.route('/admin/panel/ended', methods=['POST'])
@login_required
def admin_panel_ended_page():
    if current_user.is_admin():
        winner_team = request.form.get('winner-team')
        if not (1<=int(winner_team)<=4):
            flash("❌ 팀은 1부터 4까지라니까")
        else:
            history_collection.insert_one({
                "winner": int(winner_team),
                "time": int(datetime.now().timestamp()),
                "committer": current_user.get_name()
            })
            
            users = list(user_collection.find())
            total_money = {'1':0,'2':0,'3':0,'4':0}
            for user in users:
                if user['current_team'] != None:
                    total_money[str(user['current_team'])] += int(user['betted_money'])
            sum_money = sum(total_money.values())
            
            def div(one, two):
                if two==0: return 0
                return round(one/two,2) 

            operations = []
            for user in users:
                update_fields = {'current_team': None, 'betted_money': 0}

                if user['current_team'] == int(winner_team):
                    update_fields['money'] = (user['money'] + user['betted_money'] * div(sum_money,total_money[str(winner_team)]))

                operations.append(UpdateOne({'_id': user['_id']}, {'$set': update_fields}))
            user_collection.bulk_write(operations)

            flash('✅ 경기 결과 등록 및 보유 금액 계산 완료')

    return redirect('/')




@app.route('/admin/panel/bonus', methods=['POST'])
@login_required
def admin_panel_bonus_page():
    if current_user.is_admin():
        name = request.form.get('name')
        number = request.form.get('number')
        money = request.form.get('money')

        target_user = user_collection.find_one({'name':name, 'number':int(number)})
        if not target_user: flash('❌ 해당 사용자를 찾을 수 없습니다.')
        else:
            user_collection.update_one({'name':name, 'number':int(number)}, {'$inc':{'money':max(0, int(money))}})
            flash(f'✅ {number} {name}에게 {money} 원을 지급했습니다.')

    return redirect('/')




@app.route('/admin/panel/reset', methods=['POST'])
@login_required
def admin_panel_reset_page():
    if current_user.is_admin():
        code = request.form.get('code')
        typed_code = request.form.get('typed-code')

        if code != typed_code: flash('❌ 보안 코드가 일치하지 않습니다..')
        else:
            operations = []
            users = user_collection.find()
            for user in users:
                update_fields = {'money': 5000, 'current_team': None, 'betted_money': 0}
                operations.append(UpdateOne({'_id': user['_id']}, {'$set': update_fields}))
            user_collection.bulk_write(operations)

            flash('✅ 모든 유저의 데이터가 초기화되었습니다.')

    return redirect('/')




@app.route('/ranking')
def ranking_page():
    users = list(user_collection.find())
    users.sort(key=lambda x : -x['money'])
    return render_template('ranking.html', users=users)




if __name__ == "__main__":
    #app.run(host='0.0.0.0', port=8000, debug=True)
    serve(app, host='0.0.0.0', port=8000)
