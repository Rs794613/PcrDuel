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






            
    def _get_level(self, gid, uid):  
        try:
            r = self._connect().execute("SELECT LEVEL FROM LEVELTABLE WHERE GID=? AND UID=?",(gid,uid)).fetchone()        
            return 0 if r is None else r[0]
        except:
            raise Exception('查找等级发生错误')        
    def _get_cards(self, gid, uid):  
        with self._connect() as conn:
            r = conn.execute(
                "SELECT cid, NUM FROM UIDTABLE WHERE GID=? AND UID=? AND NUM>0", (gid, uid)
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
    "6":12    
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
        if cidnum <=6:
    
            res = chara.gen_team_pic(charalist, star_slot_verbose=False)
        else:
            res1 = chara.gen_team_pic(charalist[:6], star_slot_verbose=False)
            res2 = chara.gen_team_pic(charalist[6:], star_slot_verbose=False)
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
    

 
      
          
@sv.on_fullmatch(['招募女友','贵族约会'])   
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
        score_counter._reduce_score(gid, uid ,300)
        
        cid = get_pcr_id()
        #防止女友重复
        while duel._get_card_owner(gid,cid)!=0:
            cid = get_pcr_id()
        duel._add_card(gid,uid,cid)
        c = chara.fromid(cid)
        
        msg = f'\n招募女友成功！\n您花费了300金币\n新招募的女友为：{c.name}{c.icon.cqcode}'
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
    if  score<100:
        msg = '您的金币不足100哦。'
        await bot.send(ev, msg, at_sender=True)
        return    
    score_counter._reduce_score(gid, uid ,100)
    duel._add_level(gid,uid)
    newlevel = duel._get_level(gid,uid)
    newnoblename = get_noblename(newlevel)
    newgirlnum = get_girlnum(newlevel) 
    msg=f'花费了100金币\n您成功由{noblename}升到了{newnoblename}\n可以拥有{newgirlnum}名女友了哦。'
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
            print("测试中")
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
                msg = f'[CQ:at,qq={id}]\n砰！松了一口气，你并没有死。'
                await bot.send(ev, msg)
                n += 1
                duel_judger.change_turn(gid)
                duel_judger.turn_off_hasfired(gid)
                duel_judger.turn_on_fire(gid)
    print(winner,loser)            
    cidlist = duel._get_cards(gid,loser) 
    print(cidlist)
    selected_girl = random.choice(cidlist)
    
    duel._delete_card(gid,loser,selected_girl)
    duel._add_card(gid,winner,selected_girl)
    c = chara.fromid(selected_girl)
    msg = f'[CQ:at,qq={loser}]您输掉了贵族决斗，您被抢走了女友\n{c.name}{c.icon.cqcode}'
    await bot.send(ev, msg)
    #结算下注金币            
    score_counter = ScoreCounter2()
    support = duel_judger.get_support(gid)
    winuid = []    
    supportmsg = '金币结算:\n'
    if support!=0:
        for uid in support:
            support_id = support[uid][0]
            support_score = support[uid][1]
            if support_id == winner:
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
















