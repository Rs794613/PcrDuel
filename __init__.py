from hoshino import Service, R
from hoshino.typing import *
from hoshino import Service, priv, util
from hoshino.util import DailyNumberLimiter, pic2b64, concat_pic, silence
import sqlite3, os, random, asyncio
from nonebot import MessageSegment
from hoshino.typing import CQEvent
from hoshino.modules.priconne import _pcr_data
from  PIL  import   Image,ImageFont,ImageDraw
from io import BytesIO
import base64
from hoshino.modules.priconne import chara

lmt = DailyNumberLimiter(1)
sv = Service('pcr-duel', enable_on_default=True)
DUEL_DB_PATH = os.path.expanduser('~/.hoshino/pcr_duel.db')
SCORE_DB_PATH = os.path.expanduser('~/.hoshino/pcr_running_counter.db')
BLACKLIST_ID = [1000,1072, 1908, 4031, 9000,1069,1073,1701,1702]
WAIT_TIME = 30
DUEL_SUPPORT_TIME = 20


Addgirlfail = [
'你参加了一场贵族舞会，热闹的舞会场今天竟然没人同你跳舞。',
'你邀请到了心仪的女友跳舞，可是跳舞时却踩掉了她的鞋，她生气的离开了。',
'你为这次舞会准备了很久，结果一不小心在桌子上睡着了，醒来时只看到了过期的邀请函。',
'你参加了一场贵族舞会，可是舞会上只有一名男性向你一直眨眼。',
'你准备参加一场贵族舞会，可惜因为忘记穿礼服，被拦在了门外。',
'你沉浸在舞会的美食之中，忘了此行的目的。',
'你本准备参加舞会，却被会长拉去出了一晚上刀。'
]
Addgirlsuccess = [
'你参加了一场贵族舞会，你优雅的舞姿让每位年轻女孩都望向了你。',
'你参加了一场贵族舞会，你的帅气使你成为了舞会的宠儿。',
'你在舞会门口就遇到了一位女孩，你挽着她的手走进了舞会。',
'你在舞会的闲聊中无意中谈到了自己显赫的家室，你成为了舞会的宠儿。',
'没有人比你更懂舞会，每一个女孩都为你的风度倾倒。'
]












#用于与赛跑金币互通
class ScoreCounter2:
    def __init__(self):
        os.makedirs(os.path.dirname(SCORE_DB_PATH), exist_ok=True)
        self._create_table()


    def _connect(self):
        return sqlite3.connect(SCORE_DB_PATH)


    def _create_table(self):
        try:
            self._connect().execute('''CREATE TABLE IF NOT EXISTS SCORECOUNTER
                          (GID             INT    NOT NULL,
                           UID             INT    NOT NULL,
                           SCORE           INT    NOT NULL,
                           PRIMARY KEY(GID, UID));''')
        except:
            raise Exception('创建表发生错误')
    
    
    def _add_score(self, gid, uid ,score):
        try:
            current_score = self._get_score(gid, uid)
            conn = self._connect()
            conn.execute("INSERT OR REPLACE INTO SCORECOUNTER (GID,UID,SCORE) \
                                VALUES (?,?,?)", (gid, uid, current_score+score))
            conn.commit()       
        except:
            raise Exception('更新表发生错误')

    def _reduce_score(self, gid, uid ,score):
        try:
            current_score = self._get_score(gid, uid)
            if current_score >= score:
                conn = self._connect()
                conn.execute("INSERT OR REPLACE INTO SCORECOUNTER (GID,UID,SCORE) \
                                VALUES (?,?,?)", (gid, uid, current_score-score))
                conn.commit()     
            else:
                conn = self._connect()
                conn.execute("INSERT OR REPLACE INTO SCORECOUNTER (GID,UID,SCORE) \
                                VALUES (?,?,?)", (gid, uid, 0))
                conn.commit()     
        except:
            raise Exception('更新表发生错误')

    def _get_score(self, gid, uid):
        try:
            r = self._connect().execute("SELECT SCORE FROM SCORECOUNTER WHERE GID=? AND UID=?",(gid,uid)).fetchone()        
            return 0 if r is None else r[0]
        except:
            raise Exception('查找表发生错误')
            
#判断金币是否足够下注
    def _judge_score(self, gid, uid ,score):
        try:
            current_score = self._get_score(gid, uid)
            if current_score >= score:
                return 1
            else:
                return 0
        except Exception as e:
            raise Exception(str(e))            
            
            
            

#记录贵族相关数据
class DuelCounter:
    def __init__(self):
        os.makedirs(os.path.dirname(DUEL_DB_PATH), exist_ok=True)
        self._create_charatable()
        self._create_uidtable()
        self._create_leveltable()        
    def _connect(self):
        return sqlite3.connect(DUEL_DB_PATH)
    def _create_charatable(self):
        try:
            self._connect().execute('''CREATE TABLE IF NOT EXISTS CHARATABLE
                          (GID             INT    NOT NULL,
                           CID             INT    NOT NULL,
                           UID           INT    NOT NULL,
                           PRIMARY KEY(GID, CID));''')
        except:
            raise Exception('创建角色表发生错误')  
    def _create_uidtable(self):
        try:
            self._connect().execute('''CREATE TABLE IF NOT EXISTS UIDTABLE
                          (GID             INT    NOT NULL,
                           UID             INT    NOT NULL,
                           CID           INT    NOT NULL,
                           NUM           INT    NOT NULL,
                           PRIMARY KEY(GID, UID, CID));''')
        except:
            raise Exception('创建UID表发生错误') 
    def _create_leveltable(self):
        try:
            self._connect().execute('''CREATE TABLE IF NOT EXISTS LEVELTABLE
                          (GID             INT    NOT NULL,
                           UID             INT    NOT NULL,
                           LEVEL           INT    NOT NULL,
                           
                           PRIMARY KEY(GID, UID));''')
        except:
            raise Exception('创建UID表发生错误')         
              
    def _get_card_owner(self,gid,cid):
        try:
            r = self._connect().execute("SELECT UID FROM CHARATABLE WHERE GID=? AND CID=?",(gid,cid)).fetchone()        
            return 0 if r is None else r[0]
        except:
            raise Exception('查找角色归属发生错误')   
    def _set_card_owner(self,gid,cid,uid):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO CHARATABLE (GID, CID, UID) VALUES (?, ?, ?)",
                (gid, cid, uid),
            )  
    def _delete_card_owner(self,gid,cid):
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM CHARATABLE  WHERE GID=? AND CID=?",
                (gid, cid),
            ) 
            
    #查询已被邀请的女友列表     
    def _get_card_list(self,gid):
        with self._connect() as conn:
            r = conn.execute(
                f"SELECT CID FROM CHARATABLE WHERE GID={gid}").fetchall()
            return [c[0] for c in r]if r else {}  
        




            
    def _get_level(self, gid, uid):  
        try:
            r = self._connect().execute("SELECT LEVEL FROM LEVELTABLE WHERE GID=? AND UID=?",(gid,uid)).fetchone()        
            return 0 if r is None else r[0]
        except:
            raise Exception('查找等级发生错误')        
    def _get_cards(self, gid, uid):  
        with self._connect() as conn:
            r = conn.execute(
                "SELECT CID, NUM FROM UIDTABLE WHERE GID=? AND UID=? AND NUM>0", (gid, uid)
            ).fetchall()
        return [c[0]for c in r]if r else {}  
    
    def _get_card_num(self, gid, uid, cid):
        with self._connect() as conn:
            r = conn.execute(
                "SELECT NUM FROM UIDTABLE WHERE GID=? AND UID=? AND CID=?", (gid, uid, cid)
            ).fetchone()
            return r[0] if r else 0    
    
    def _add_card(self, gid, uid, cid, increment=1):
        num = self._get_card_num(gid, uid, cid)
        num += increment
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO UIDTABLE (GID, UID, CID, NUM) VALUES (?, ?, ?, ?)",
                (gid, uid, cid, num),
            )
        self._set_card_owner(gid,cid,uid)
    
    def _delete_card(self, gid, uid, cid, increment=1):
        num = self._get_card_num(gid, uid, cid)
        num -= increment
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO UIDTABLE (GID, UID, CID, NUM) VALUES (?, ?, ?, ?)",
                (gid, uid, cid, num),
            )
        self._delete_card_owner(gid,cid)
    
       
    def _add_level(self, gid, uid, increment=1):
        level = self._get_level(gid, uid)
        level += increment
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO LEVELTABLE (GID, UID, LEVEL) VALUES (?, ?, ?)",
                (gid, uid, level),
            )
    def _reduce_level(self, gid, uid, increment=1):
        level = self._get_level(gid, uid)
        level -= increment
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO LEVELTABLE (GID, UID, LEVEL) VALUES (?, ?, ?)",
                (gid, uid, level),
            )        
            
            
    def _set_level(self, gid, uid, level):
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO LEVELTABLE (GID, UID, LEVEL) VALUES (?, ?, ?)",
                (gid, uid, level),
            )            

#记录决斗和下注数据
class DuelJudger:
    def __init__(self):
        self.on = {}
        self.accept_on = {}
        self.support_on = {}
        self.fire_on = {}
        self.deadnum = {}
        self.support = {}
        self.turn = {}
        self.duelid = {}
        self.isaccept = {}
        self.hasfired_on={}
        
    def set_support(self,gid):
        self.support[gid] = {}
    def get_support(self,gid):
        return self.support[gid] if self.support.get(gid) is not None else 0
    def add_support(self,gid,uid,id,score):
        self.support[gid][uid]=[id,score]
    def get_support_id(self,gid,uid):
        if self.support[gid].get(uid) is not None:
            return self.support[gid][uid][0]
        else :
            return 0
    def get_support_score(self,gid,uid):
        if self.support[gid].get(uid) is not None:
            return self.support[gid][uid][1]
        else :
            return 0
            
#五个开关：决斗，接受，下注， 开枪, 是否已经开枪           
            
    def get_on_off_status(self, gid):
        return self.on[gid] if self.on.get(gid) is not None else False
    def turn_on(self, gid):
        self.on[gid] = True
    def turn_off(self, gid):
        self.on[gid] = False
 
    def get_on_off_accept_status(self, gid):
        return self.accept_on[gid] if self.accept_on.get(gid) is not None else False
    def turn_on_accept(self, gid):
        self.accept_on[gid] = True
    def turn_off_accept(self, gid):
        self.accept_on[gid] = False

    def get_on_off_support_status(self, gid):
        return self.support_on[gid] if self.support_on.get(gid) is not None else False
    def turn_on_support(self, gid):
        self.support_on[gid] = True
    def turn_off_support(self, gid):
        self.support_on[gid] = False

    def get_on_off_fire_status(self, gid):
        return self.fire_on[gid] if self.fire_on.get(gid) is not None else False
    def turn_on_fire(self, gid):
        self.fire_on[gid] = True
    def turn_off_fire(self, gid):
        self.fire_on[gid] = False

    def get_on_off_hasfired_status(self, gid):
        return self.hasfired_on[gid] if self.hasfired_on.get(gid) is not None else False
    def turn_on_hasfired(self, gid):
        self.hasfired_on[gid] = True
    def turn_off_hasfired(self, gid):
        self.hasfired_on[gid] = False







#记录决斗者id
    def init_duelid(self,gid):
        self.duelid[gid]=[] 
    def set_duelid(self,gid,id1,id2):
        self.duelid[gid]=[id1,id2]
    def get_duelid(self,gid):
        return self.duelid[gid] if self.accept_on.get(gid) is not None else [0,0]  
    #查询一个决斗者是1号还是2号
    def get_duelnum(self,gid,uid):
        return self.duelid[gid].index(uid)+1
        
        
        
        
        
        
        
   
#记录由谁开枪
    def init_turn(self,gid):
        self.turn[gid]=1
    def get_turn(self,gid):
        return self.turn[gid] if self.turn[gid] is not None else 0
    def change_turn(self,gid):
        if self.get_turn(gid)==1:
            self.turn[gid]=2
            return 2
        else: 
            self.turn[gid]=1
            return 1
        
#记录子弹位置
    def init_deadnum(self,gid):
        self.deadnum[gid]=None
    def set_deadnum(self,gid,num):
        self.deadnum[gid]=num
    def get_deadnum(self,gid):
        return self.deadnum[gid]if self.deadnum[gid]is not None else False
        
#记录是否接受
    def init_isaccept(self,gid):
        self.isaccept[gid]=False
    def on_isaccept(self,gid):
        self.isaccept[gid]=True
    def off_isaccept(self,gid):
        self.isaccept[gid]=False
    def get_isaccept(self,gid):
        return self.isaccept[gid] if self.isaccept[gid] is not None else False     
            
                       
duel_judger = DuelJudger()

        
#随机生成一个pcr角色id
def get_pcr_id():
    chara_id_list = list(_pcr_data.CHARA_NAME.keys())
    while True:
        random.shuffle(chara_id_list)
        if chara_id_list[0] not in BLACKLIST_ID: break
    return chara_id_list[0]

#生成没被约过的角色列表
def get_newgirl_list(gid):
    chara_id_list = list(_pcr_data.CHARA_NAME.keys())
    duel = DuelCounter()
    old_list = duel._get_card_list(gid)
    new_list = []
    for card in chara_id_list:
        if card not in BLACKLIST_ID and card not in old_list:
            new_list.append(card)
    return new_list
        


















#取爵位名
def get_noblename(level:int):
    namedict = {
    "1":"男爵",
    "2":"子爵",
    "3":"伯爵",
    "4":"侯爵",
    "5":"公爵",
    "6":"国王"
    }
    return namedict[str(level)]    
#返回爵位对应的女友数
def get_girlnum(level:int):
    numdict = {
    "1":3,
    "2":5,
    "3":7,
    "4":9,
    "5":11,
    "6":13    
    }    
    return numdict[str(level)] 

#返回升级到爵位所需要的金币数
def get_noblescore(level:int):
    numdict = {
    "1":0,
    "2":100,
    "3":300,
    "4":500,
    "5":1000,
    "6":2000    
    }  
    return numdict[str(level)]





    

@sv.on_fullmatch('贵族签到')
async def noblelogin(bot, ev: CQEvent):
    gid = ev.group_id
    uid = ev.user_id
    if not lmt.check(uid):
        await bot.send(ev, '今天已经签到过了哦，明天再来吧。', at_sender=True)
        return
    duel = DuelCounter()
    if duel._get_level(gid, uid)== 0:
        msg = '您还未在本群创建过贵族，请发送 创建贵族 开始您的贵族之旅。'
        await bot.send(ev, msg, at_sender=True)
        return      
    score_counter = ScoreCounter2()
    lmt.increase(uid)
    score_counter._add_score(gid, uid ,100)
    level = duel._get_level(gid,uid)
    noblename = get_noblename(level)
    score = score_counter._get_score(gid, uid) 
    msg = f'签到成功！已领取100金币。\n{noblename}先生，您现在共有{score}金币。'
    await bot.send(ev, msg, at_sender=True)
   

@sv.on_fullmatch('创建贵族')
async def add_noble(bot, ev: CQEvent):
    try:
        gid = ev.group_id
        uid = ev.user_id
        duel = DuelCounter()
        if duel._get_level(gid, uid)!= 0:
            msg = '您已经在本群创建过贵族了，请发送 查询贵族 查询。'
            await bot.send(ev, msg, at_sender=True)
            return 
        else:
            cid = get_pcr_id()
            #防止情人重复
            while duel._get_card_owner(gid,cid)!=0:
                cid = get_pcr_id()
            duel._add_card(gid,uid,cid)
            c = chara.fromid(cid)
            duel._set_level(gid, uid, 1)
            msg = f'\n创建贵族成功！\n您的初始爵位是男爵\n可以拥有3名女友。\n为您分配的初始女友为：{c.name}{c.icon.cqcode}'
            await bot.send(ev, msg, at_sender=True)
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e))               
            
            
@sv.on_fullmatch(['查询贵族','我的贵族'])   
async def inquire_noble(bot, ev: CQEvent):

    gid = ev.group_id
    uid = ev.user_id
    duel = DuelCounter()
    score_counter = ScoreCounter2()
    if duel._get_level(gid, uid)== 0:
        msg = '您还未在本群创建过贵族，请发送 创建贵族 开始您的贵族之旅。'
        await bot.send(ev, msg, at_sender=True)
        return         
    level = duel._get_level(gid,uid)
    noblename = get_noblename(level)
    girlnum = get_girlnum(level)
    score = score_counter._get_score(gid, uid)
    charalist = []

    cidlist = duel._get_cards(gid,uid)
    cidnum = len(cidlist)
    if cidnum == 0:
        msg= f'''
╔                          ╗
  您的爵位为{noblename}
  您的金币为{score}
  您共可拥有{girlnum}名女友
  您目前没有女友。
  发送[贵族约会]
  可以招募女友哦。
  
╚                          ╝
'''
        await bot.send(ev, msg, at_sender=True)    
    
    
    else:
        for cid in cidlist:
            charalist.append(chara.Chara(cid,0,0)) 
        if cidnum <=7:
    
            res = chara.gen_team_pic(charalist, star_slot_verbose=False)
        else:
            res1 = chara.gen_team_pic(charalist[:7], star_slot_verbose=False)
            res2 = chara.gen_team_pic(charalist[7:], star_slot_verbose=False)
            res = concat_pic([res1, res2]) 
        bio  = BytesIO()
        res.save(bio, format='PNG')
        base64_str = 'base64://' + base64.b64encode(bio.getvalue()).decode()
        mes  = f"[CQ:image,file={base64_str}]"
    
        msg= f'''
╔                          ╗
  您的爵位为{noblename}
  您的金币为{score}
  您共可拥有{girlnum}名女友
  您已拥有{cidnum}名女友
  她们是：
    {mes}   
╚                          ╝
'''
        await bot.send(ev, msg, at_sender=True)  
    
          
@sv.on_fullmatch(['招募女友','贵族舞会','贵族约会'])   
async def add_girl(bot, ev: CQEvent):
    gid = ev.group_id
    uid = ev.user_id
    duel = DuelCounter() 
    score_counter = ScoreCounter2()

    if duel._get_level(gid, uid)== 0:
        msg = '您还未在本群创建过贵族，请发送 创建贵族 开始您的贵族之旅。'
        duel_judger.turn_off(ev.group_id) 
        
        await bot.send(ev, msg, at_sender=True)
        return              
    else:
        #防止女友数超过上限
        level = duel._get_level(gid,uid)
        noblename = get_noblename(level)
        girlnum = get_girlnum(level) 
        cidlist = duel._get_cards(gid,uid)
        cidnum = len(cidlist)
        if cidnum >= girlnum:
            msg = '您的女友已经满了哦，快点发送[升级贵族]进行升级吧。'
            await bot.send(ev, msg, at_sender=True)
            return
        score = score_counter._get_score(gid, uid)
        if score<300:
            msg = '您的金币不足300哦。'
            await bot.send(ev, msg, at_sender=True)
            return
        newgirllist = get_newgirl_list(gid)
        #判断女友是否被抢没
        if len(newgirllist) == 0:
            await bot.send(ev, '这个群已经没有可以约到的新女友了哦。', at_sender=True)
            return    
        score_counter._reduce_score(gid, uid ,300)   


        #招募女友失败
        if random.random() <0.4:
            losetext = random.choice(Addgirlfail) 
            msg = f'\n{losetext}\n您花费了300金币，但是没有约到新的女友。'
            await bot.send(ev, msg, at_sender=True)
            return
            
            
        #招募女友成功
        cid = random.choice(newgirllist)

        duel._add_card(gid,uid,cid)
        c = chara.fromid(cid)
        wintext = random.choice(Addgirlsuccess)
        msg = f'\n{wintext}\n招募女友成功！\n您花费了300金币\n新招募的女友为：{c.name}{c.icon.cqcode}'
        await bot.send(ev, msg, at_sender=True)        




@sv.on_fullmatch(['升级爵位','升级贵族'])  
async def add_girl(bot, ev: CQEvent):
    gid = ev.group_id
    uid = ev.user_id
    duel = DuelCounter() 
    score_counter = ScoreCounter2() 
    score = score_counter._get_score(gid, uid)        
    level = duel._get_level(gid,uid)
    noblename = get_noblename(level)
    girlnum = get_girlnum(level) 
    cidlist = duel._get_cards(gid,uid)
    cidnum = len(cidlist)  
    
   
    if level ==6:
       msg = f'您已经是最高爵位{noblename}了，不能再升级了。'
       await bot.send(ev, msg, at_sender=True)
       return     
    
    if cidnum < girlnum :
        msg = f'您的女友没满哦。\n需要达到{girlnum}名女友\n您现在有{cidnum}名。'
        await bot.send(ev, msg, at_sender=True)
        return
    needscore = get_noblescore(level+1)
    futurename = get_noblename(level+1)
      
    if  score < needscore:
        msg = f'您的金币不足哦。\n升级到{futurename}需要{needscore}金币'
        await bot.send(ev, msg, at_sender=True)
        return    
    score_counter._reduce_score(gid, uid ,needscore)
    duel._add_level(gid,uid)
    newlevel = duel._get_level(gid,uid)
    newnoblename = get_noblename(newlevel)
    newgirlnum = get_girlnum(newlevel) 
    msg=f'花费了{needscore}金币\n您成功由{noblename}升到了{newnoblename}\n可以拥有{newgirlnum}名女友了哦。'
    await bot.send(ev, msg, at_sender=True)

    

@sv.on_prefix('贵族决斗')
async def nobleduel(bot, ev: CQEvent):
    if ev.message[0].type == 'at':
        id2 = int(ev.message[0].data['qq'])
    else:
        await bot.finish(ev, '参数格式错误, 请重试')
    if duel_judger.get_on_off_status(ev.group_id):
            await bot.send(ev, "此轮决斗还没结束，请勿重复使用指令。")
            return
    gid = ev.group_id 
    duel_judger.turn_on(gid)
    id1 = ev.user_id
    duel = DuelCounter() 

    
    
    
    if duel._get_level(gid, id1)== 0:
        msg = f'[CQ:at,qq={id1}]决斗发起者还未在创建过贵族\n请发送 创建贵族 开始您的贵族之旅。'
        duel_judger.turn_off(ev.group_id) 
        await bot.send(ev, msg)
        return
    if duel._get_cards(gid,id1) == {}:
        msg = f'[CQ:at,qq={id1}]您没有女友，不能参与决斗哦。'
        duel_judger.turn_off(ev.group_id) 
        await bot.send(ev, msg)
        return        
        
    if duel._get_level(gid, id2)== 0:
        msg = f'[CQ:at,qq={id2}]被决斗者还未在本群创建过贵族\n请发送 创建贵族 开始您的贵族之旅。'
        duel_judger.turn_off(ev.group_id) 
        await bot.send(ev, msg)
        return 
    if duel._get_cards(gid,id2) == {}:
        msg = f'[CQ:at,qq={id2}]您没有女友，不能参与决斗哦。'
        duel_judger.turn_off(ev.group_id) 
        await bot.send(ev, msg)
        return             
 
    #判定双方的女友是否已经超过上限
    level_1 = duel._get_level(gid,id1)
    noblename_1 = get_noblename(level_1)
    girlnum_1 = get_girlnum(level_1) 
    cidlist_1 = duel._get_cards(gid,id1)
    cidnum_1 = len(cidlist_1)
    #这里设定大于才会提醒，就是可以超上限1名，可以自己改成大于等于。
    if cidnum_1 > girlnum_1:
       msg = f'[CQ:at,qq={id1}]您的女友超过了爵位上限，先去升级爵位吧。' 
       duel_judger.turn_off(ev.group_id) 
       await bot.send(ev, msg)
       return      
    level_2 = duel._get_level(gid,id2)
    noblename_2 = get_noblename(level_2)
    girlnum_2 = get_girlnum(level_2) 
    cidlist_2 = duel._get_cards(gid,id2)
    cidnum_2= len(cidlist_2)
    if cidnum_2 > girlnum_2:
       msg = f'[CQ:at,qq={id2}]您的女友超过了爵位上限，先去升级爵位吧。' 
       duel_judger.turn_off(ev.group_id) 
       await bot.send(ev, msg)
       return  
      
    duel_judger.init_isaccept(gid)
    duel_judger.set_duelid(gid,id1,id2)    
    duel_judger.turn_on_accept(gid)
    msg = f'[CQ:at,qq={id2}]对方向您发起了优雅的贵族决斗，请在{WAIT_TIME}秒内[接受/拒绝]。'
    await bot.send(ev, msg)
    
    await asyncio.sleep(WAIT_TIME)
    duel_judger.turn_off_accept(gid)
    if duel_judger.get_isaccept(gid) is False:
        msg = '决斗被拒绝。'
        await bot.send(ev, msg, at_sender=True)
        duel_judger.turn_off(gid)
        return
    duel = DuelCounter()
    level1 = duel._get_level(gid,id1)
    noblename1 = get_noblename(level1) 
    level2 = duel._get_level(gid,id2)
    noblename2 = get_noblename(level2)     
    msg = f'''对方接受了决斗！    
1号：[CQ:at,qq={id1}]
爵位为：{noblename1}
2号：[CQ:at,qq={id2}]
爵位为：{noblename2}
其他人请在{DUEL_SUPPORT_TIME}秒选择支持的对象。
[支持1/2号xxx金币]'''


   
    await bot.send(ev, msg)
    duel_judger.turn_on_support(gid)
    await asyncio.sleep(DUEL_SUPPORT_TIME)
    duel_judger.turn_off_support(gid)
    deadnum = random.randint(1,6)
    duel_judger.set_deadnum(gid,deadnum)
    duel_judger.init_turn(gid)
    duel_judger.turn_on_fire(gid)
    duel_judger.turn_off_hasfired(gid)
    msg = f'支持环节结束，下面请决斗双方轮流[开枪]。\n[CQ:at,qq={id1}]先开枪，30秒未开枪自动认输'
    
    await bot.send(ev, msg)
    n=1
    while(n<=6):
        wait_n = 0
        while(wait_n<30):
            if duel_judger.get_on_off_hasfired_status(gid):
                break
            
            wait_n += 1
            await asyncio.sleep(1)
        if wait_n >=30:
            #超时未开枪的胜负判定
            loser = duel_judger.get_duelid(gid)[duel_judger.get_turn(gid)-1]
            winner = duel_judger.get_duelid(gid)[2-duel_judger.get_turn(gid)]
            msg = f'[CQ:at,qq={loser}]\n你明智的选择了认输。'
            await bot.send(ev, msg)
            break
        else :
            if n ==duel_judger.get_deadnum(gid):
                #被子弹打到的胜负判定
                loser = duel_judger.get_duelid(gid)[duel_judger.get_turn(gid)-1]
                winner = duel_judger.get_duelid(gid)[2-duel_judger.get_turn(gid)]
                msg = f'[CQ:at,qq={loser}]\n砰！你死了。'
                await bot.send(ev, msg)                
                break 
            else :
                id = duel_judger.get_duelid(gid)[duel_judger.get_turn(gid)-1]
                id2 = duel_judger.get_duelid(gid)[2-duel_judger.get_turn(gid)]
                msg = f'[CQ:at,qq={id}]\n砰！松了一口气，你并没有死。\n[CQ:at,qq={id2}]\n轮到你开枪了哦。'
                await bot.send(ev, msg)
                n += 1
                duel_judger.change_turn(gid)
                duel_judger.turn_off_hasfired(gid)
                duel_judger.turn_on_fire(gid)
  
    cidlist = duel._get_cards(gid,loser) 
    selected_girl = random.choice(cidlist)
    duel._delete_card(gid,loser,selected_girl)
    duel._add_card(gid,winner,selected_girl)
    c = chara.fromid(selected_girl)
    msg = f'[CQ:at,qq={loser}]您输掉了贵族决斗，您被抢走了女友\n{c.name}{c.icon.cqcode}'
    await bot.send(ev, msg)
    
    #判定是否掉爵位
    level_loser = duel._get_level(gid,loser)
    if level_loser>1:
        noblename_loser = get_noblename(level_loser)
        girlnum_loser = get_girlnum(level_loser-1) 
        cidlist_loser = duel._get_cards(gid,loser)
        cidnum_loser = len(cidlist_loser)
        if cidnum_loser < girlnum_loser:
            duel._reduce_level(gid,loser)
            new_noblename = get_noblename(level_loser-1)
            msg = f'[CQ:at,qq={loser}]\n您的女友数为{cidnum_loser}名\n小于爵位需要的女友数{girlnum_loser}名\n您的爵位下降了到了{new_noblename}'
            await bot.send(ev, msg)
            

    
    #结算下注金币            
    score_counter = ScoreCounter2()
    support = duel_judger.get_support(gid)
    winuid = []    
    supportmsg = '金币结算:\n'
    winnum = duel_judger.get_duelnum(gid,winner) 

    if support!=0:
        for uid in support:
            support_id = support[uid][0]
            support_score = support[uid][1]
            if support_id == winnum:
                winuid.append(uid)
                winscore = support_score*2
                score_counter._add_score(gid, uid ,winscore)
                supportmsg += f'[CQ:at,qq={uid}]+{winscore}金币\n'     
            else:
                score_counter._reduce_score(gid, uid ,support_score)
                supportmsg += f'[CQ:at,qq={uid}]-{support_score}金币\n'
    await bot.send(ev, supportmsg) 
    duel_judger.set_support(ev.group_id) 
    duel_judger.turn_off(ev.group_id)    
    return            
    


@sv.on_fullmatch('接受')
async def duelaccept(bot, ev: CQEvent):
    gid = ev.group_id
    if duel_judger.get_on_off_accept_status(gid):
        if ev.user_id == duel_judger.get_duelid(gid)[1]:
            gid = ev.group_id
            msg = '贵族决斗接受成功，请耐心等待决斗开始。'
            await bot.send(ev, msg, at_sender=True)
            duel_judger.turn_off_accept(gid)
            duel_judger.on_isaccept(gid)
        else:
            print('不是被决斗者')
    else:print('现在不在决斗期间')
        
@sv.on_fullmatch('拒绝')
async def duelrefuse(bot, ev: CQEvent):
    gid = ev.group_id
    if duel_judger.get_on_off_accept_status(gid):
        if ev.user_id == duel_judger.get_duelid(gid)[1]:
            gid = ev.group_id
            msg = '您已拒绝贵族决斗。'
            await bot.send(ev, msg, at_sender=True)
            duel_judger.turn_off_accept(gid)
            duel_judger.off_isaccept(gid)            

@sv.on_fullmatch('开枪')
async def duelfire(bot, ev: CQEvent):
    gid = ev.group_id
    if duel_judger.get_on_off_fire_status(gid):
        if ev.user_id == duel_judger.get_duelid(gid)[duel_judger.get_turn(gid)-1]:
            
            duel_judger.turn_on_hasfired(gid)
            duel_judger.turn_off_fire(gid)
        
        
@sv.on_rex(r'^支持(1|2)号(\d+)(金币|币)$') 
async def on_input_duel_score(bot, ev: CQEvent):
    try:
        if duel_judger.get_on_off_support_status(ev.group_id):
            gid = ev.group_id
            uid = ev.user_id
            
            match = ev['match']
            select_id = int(match.group(1))
            input_score = int(match.group(2))
            print(select_id,input_score)
            score_counter = ScoreCounter2()
            #若下注该群下注字典不存在则创建
            if duel_judger.get_support(gid) == 0:
                duel_judger.set_support(gid)
            support = duel_judger.get_support(gid)
            #检查是否重复下注
            if uid in support:
                msg = '您已经支持过了。'
                await bot.send(ev, msg, at_sender=True)
                return
            #检查是否是决斗人员
            duellist = duel_judger.get_duelid(gid)
            if uid in duellist:
                msg = '决斗参与者不能支持。'
                await bot.send(ev, msg, at_sender=True)
                return                
          
            #检查金币是否足够下注
            if score_counter._judge_score(gid, uid ,input_score) == 0:
                msg = '您的金币不足。'
                await bot.send(ev, msg, at_sender=True)
                return
            else :
                duel_judger.add_support(gid,uid,select_id,input_score)
                msg = f'支持{select_id}号成功。'
                await bot.send(ev, msg, at_sender=True)                
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e))                



#以下部分与赛跑的重合，有一个即可，两个插件都装建议注释掉。
@sv.on_prefix(['领金币','领取金币'])
async def add_score(bot, ev: CQEvent):
    try:
        score_counter = ScoreCounter2()
        gid = ev.group_id
        uid = ev.user_id
        
        current_score = score_counter._get_score(gid, uid)
        if current_score == 0:
            score_counter._add_score(gid, uid ,50)
            msg = '您已领取50金币'
            await bot.send(ev, msg, at_sender=True)
            return
        else:     
            msg = '金币为0才能领取哦。'
            await bot.send(ev, msg, at_sender=True)
            return
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e))         
@sv.on_prefix(['查金币','查询金币','查看金币'])
async def get_score(bot, ev: CQEvent):
    try:
        score_counter = ScoreCounter2()
        gid = ev.group_id
        uid = ev.user_id
        
        current_score = score_counter._get_score(gid, uid)
        msg = f'您的金币为{current_score}'
        await bot.send(ev, msg, at_sender=True)
        return
    except Exception as e:
        await bot.send(ev, '错误:\n' + str(e)) 



@sv.on_rex(f'^为(\d+)充值(\d+)金币$')
async def cheat_score(bot, ev: CQEvent):
    if not priv.check_priv(ev, priv.SUPERUSER):
        await bot.finish(ev, '只有机器人管理才能使用氪金功能哦。', at_sender=True)    
    gid = ev.group_id
    match = ev['match']
    id = int(match.group(1))
    num =int(match.group(2))
    duel = DuelCounter()
    score_counter = ScoreCounter2()    
    if duel._get_level(gid, id)== 0:
        await bot.finish(ev, '该用户还未在本群创建贵族哦。', at_sender=True) 
    score_counter._add_score(gid, id ,num)
    score = score_counter._get_score(gid, id)
    msg = f'已为[CQ:at,qq={id}]充值{num}金币。\n现在共有{score}金币。'
    await bot.send(ev, msg)


@sv.on_fullmatch('重置决斗')
async def init_duel(bot, ev: CQEvent):
    if not priv.check_priv(ev, priv.ADMIN):
        await bot.finish(ev, '只有群管理才能使用重置决斗哦。', at_sender=True)   
    duel_judger.turn_off(ev.group_id) 
    msg = '已重置本群决斗状态！'
    await bot.send(ev, msg, at_sender=True)
    
  


@sv.on_prefix(['查女友','查询女友','查看女友'])
async def search_girl(bot, ev: CQEvent):
    args = ev.message.extract_plain_text().split()
    gid = ev.group_id
    if not args:
        await bot.send(ev, '请输入查女友+pcr角色名。', at_sender=True)
        return    
    name = args[0]
    cid = chara.name2id(name)
    if cid == 1000:
        await bot.send(ev, '请输入正确的pcr角色名。', at_sender=True)
        return
    duel = DuelCounter()    
    owner = duel._get_card_owner(gid,cid)
    c = chara.fromid(cid)
    
    if owner == 0:
        await bot.send(ev, f'{c.name}现在还是单身哦，快去约到她吧。', at_sender=True)
        return
    else:
        msg = f'{c.name}现在正在\n[CQ:at,qq={owner}]的身边哦。{c.icon.cqcode}'
        await bot.send(ev, msg)
        
       






