# インストールした discord.py を読み込む
import discord
import random   # おみくじで使用
import re       # 正規表現に必要（残り体力に使用）
from discord.ext import tasks
from datetime import datetime
from discord.ext import commands
# スプレッドシート連携用 ※ライブラリ「gspread」と「oauth2client」のインストールが必要です。
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials
# 設定ファイル読み込み
import configparser
import math
import os 
import queue

    # 接続に必要なオブジェクトを生成
client = discord.Client()

fincount    = 0                     # 凸終了人数カウント変数
bossindex   = 0
nowboss     = 0                     # トータルで何体目のボスか？
round       = 1                     # 周回数
stage       = 1

# スプレッドシートの場所
C_BOSS      = 'B3:B7'
C_BOSSHPMAX = 'C3:C7'
C_NOWBOSS   = 'D3:D7'
C_BOSSHP    = 'E3:E7'
C_MEMBERNAME= 'I3:I32'
C_MEMBERID  = 'J3:J32'
C_TOTSU     = 'K3:K32'
C_ROUND     = 'V5'
C_STAGE     = 'V6'
C_YOYAKU    = 'F3:F7'
C_NOWTOTSU  = 'N3:N32'
C_MOGI      = 'R3:R32'
S_DAY       = 'B2'
S_NAME      = 'C5:C64'
S_DAMAGE    = 'D5:AY64'
C_RATE      = 'B11:E15'
C_DMG       = [['BF%d:BG%d','BH%d:BI%d','BJ%d:BK%d','BL%d:BM%d','BN%d:BO%d'],['AU%d:AV%d','AW%d:AX%d','AY%d:AZ%d','BA%d:BB%d','BC%d:BD%d'],['AJ%d:AK%d','AL%d:AM%d','AN%d:AO%d','AP%d:AQ%d','AR%d:AS%d'],['Y%d:Z%d','AA%d:AB%d','AC%d:AD%d','AE%d:AF%d','AG%d:AH%d']]
C_DMGCNT    = [['W33','W34','W35','W36','W37'],['W26','W27','W28','W29','W30'],['W19','W20','W21','W22','W23'],['W12','W13','W14','W15','W16']]
C_DMGAVE    = [['V33','V34','V35','V36','V37'],['V26','V27','V28','V29','V30'],['V19','V20','V21','V22','V23'],['V12','V13','V14','V15','V16']]
C_DMGALL    = 'Y3:BO120'
C_DMGCNTALL = 'W12:W37'
C_DMGCNTALL2= ['W33:W37','W26:W30','W19:W23','W12:W16']

# ダメージ記憶用
dmgindex = [[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]

# user情報リスト
memberid      = []            # クラメンのＩＤを取得するリスト
membername    = []            # クラメンの名前を取得するリスト
usercount     = 0             # クラメンの人数
totsucount    = []            # 凸数リスト
totsunow      = []            # 0:凸ってない 1:凸中 2:持ち越し中
simulated     = []            # 今模擬戦中か
taskill       = []            # タスキル回数
bosyu_list    = []            # 凸募集用

# 同時凸ナビ用
syn1mention  = ""
syn2mention  = ""
synstatus    = 0
othermention = ""

# 予約システム用
yoyaku = [[], [], [], [], []]
yoyakuname = ["", "", "", "", ""]

# 設定ファイルからサーバ設定を読み込む
inifile = configparser.ConfigParser()
inifile.read('sanoba_config.ini', 'UTF-8')
TOKEN       = inifile.get('config', 'TOKEN')
CHANNEL_T   = int(inifile.get('config', 'CHANNEL_T'))       # 凸宣言チャンネルID
CHANNEL_S   = int(inifile.get('config', 'CHANNEL_S'))       # 凸状況確認チャンネルID
CHANNEL_SYN = int(inifile.get('config', 'CHANNEL_SYN'))     # 同時ナビ用チャンネル
CHANNEL_RSV = int(inifile.get('config', 'CHANNEL_RSV'))     # 予約用チャンネル
CHANNEL_FIN = int(inifile.get('config', 'CHANNEL_FIN'))     # 凸終わり報告チャンネル
CHANNEL_ZAT = int(inifile.get('config', 'CHANNEL_ZAT'))     # 雑談チャンネル
ID_SRV = int(inifile.get('config', 'ID_SRV'))     
lot_channel_id = int(inifile.get('config', 'lot_channel_id'))
roles_mem   = int(inifile.get('config', 'roles_mem'))       # 役職くらめんID
SHEETNAME   = inifile.get('config', 'SHEETNAME')            # シート名
SPREADSHEET_KEY = inifile.get('config', 'SPREADSHEET_KEY')
JSON_FILE = inifile.get('config', 'JSON_FILE')

# スプレッドシートのワークシートを取得する
scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
credentials = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
gc = gspread.authorize(credentials)
wsclass = gc.open_by_key(SPREADSHEET_KEY)
worksheet = wsclass.sheet1

#スプレッドシートからボスの名前とHPを取得する
boss        = [tboss.value for tboss in worksheet.range(C_BOSS)]
bosshp      = [int(tbosshp.value) for tbosshp in worksheet.range(C_BOSSHPMAX)]
hp          = bosshp[0]             #ボスの現在HP
rate        = [float(trate.value) for trate in worksheet.range(C_RATE)]     # スコア倍率

# スプシの範囲内の一つの情報を更新する
def gsvalueset(gsrange, index, gsvalue):
    lll = worksheet.range(gsrange)
    lll[index].value = gsvalue
    worksheet.update_cells(lll)


# スプシの予約情報更新関数
def yoyakuupdate(x):
    global yoyakuname
    l_yoyakuname = [membername[memberid.index(i)] for i in yoyaku[x]]
    yoyakuname[x] = ','.join(l_yoyakuname)
    gsvalueset(C_YOYAKU, x, yoyakuname[x])

# roundからstageを計算する関数
def roundstage(round):
    if round <= 3:
        stage = 1
    elif round >=4 and round <= 10:
        stage = 2
    elif round >= 11 and round <= 34:
        stage = 3
    elif round >=35:
        stage = 4        
    return stage

# メッセージを送った人のindexを取得
def authorindex(message):
    num = memberid.index(message.author.id)
    return num

# ダメージ量から周回数を計算する
def syucalc(dmgall):
    sindex = nowboss
    syu, sindex2 = divmod(sindex, 5)
    shp = hp
    while 1:
        if shp >= dmgall:           # 最後の計算
            nokori = shp - dmgall
            break
        else:                       # 途中の計算
            dmgall -= shp
            # 次ボスへ
            sindex += 1
            syu, sindex2 = divmod(sindex, 5)
            shp = bosshp[sindex2]
            sstg = roundstage(syu)
    syumessage = f'{syu+1}周目の{boss[sindex2]}で残りHP{nokori}万です。'
    return syumessage

# スコアから周回数を計算する
def syucalcs(scrall):
    sindex = nowboss
    syu, sindex2 = divmod(sindex, 5)
    sstg = roundstage(syu)
    srate = rate[(sstg-1)*5+sindex2]
    shp = hp
    while 1:
        if shp >= (scrall/srate):           # 最後の計算
            nokori = shp - (scrall/srate)
            break
        else:                               # 途中の計算
            scrall -= shp*srate
            # 次ボスへ
            sindex += 1
            syu, sindex2 = divmod(sindex, 5)
            shp = bosshp[sindex2]
            sstg = roundstage(syu)
            srate = rate[(sindex2*3)+(sstg-1)]
    syumessage = f'{syu+1}周目の{boss[sindex2]}で残りHP{int(nokori)}万です。'
    return syumessage  

# 起動時に動作する処理
@client.event
async def on_ready():
    """起動時に通知してくれる処理"""
    print('ログインしました')
    print(client.user.name)  # ボットの名前
    print(client.user.id)  # ボットのID
    print(discord.__version__)  # discord.pyのバージョン
    print('------')

# メッセージ受信時に動作する処理
@client.event
async def on_message(message):
    #ここで書き換えるものだけ。参照するだけのグローバル変数はここに書かなくて良い
    global fincount
    global bossindex
    global nowboss
    global round
    global stage
    global hp
    global memberid
    global membername
    global usercount
    global totsucount
    global totsunow
    global simulated
    global taskill
    global syn1mention
    global syn2mention
    global synstatus
    global othermention
    global yoyaku
    global yoyakuname
    global bosyu_list
    global dmgindex

    # メッセージ送信者がBotだった場合は無視する
    if message.author.bot:
        return

  # メンバー情報、ボス情報をすべて初期化する。メンバーに変更があった場合に行って下さい
    if message.content == '!cb start':
        if message.channel.id == lot_channel_id:
            channel = client.get_channel(CHANNEL_T)
        await channel.send("```シズルお姉ちゃんを起こしています。。。```")
        usercount       = 0
        memberid        = []            # クラメンのＩＤリストを初期化する
        membername      = []            # クラメンの名前リストを初期化する
        totsucount      = []            # 凸数リストを初期化する
        totsunow        = []            # 凸状況リスト初期化する
        simulated       = []            # 模擬戦リストを初期化する
        taskill         = []            # タスキルリストを初期化する
        fincount        = 0
        l_membername    = worksheet.range(C_MEMBERNAME)
        l_memberid      = worksheet.range(C_MEMBERID)
        l_totsu         = worksheet.range(C_TOTSU)
        l_totsunow      = worksheet.range(C_NOWTOTSU)
        l_mogi          = worksheet.range(C_MOGI)
        for i in range(30):
            l_membername[i].value = ""                  # スプシのメンバーを初期化する
            l_memberid[i].value = ""
            l_totsu[i].value = 0                   # スプシの現在の凸数を初期化する
            l_totsunow[i].value = 0
            l_mogi[i].value = 0
        i = 0
        for member in message.guild.members:    # user情報を全員チェックする
            for role in member.roles:           # userのロールをチェックする
                if role.id == roles_mem:        # ロールが「くらめん」なら
                    membername.append(member.name)
                    memberid.append(member.id)
                    totsucount.append(0)
                    totsunow.append(0)
                    simulated.append(0)
                    taskill.append(0)
                    usercount += 1                  # user数をカウントアップする
                    l_membername[i].value = member.name # スプシのメンバー名を更新する
                    l_memberid[i].value = str(member.id)
                    i += 1
        worksheet.update_cells(l_membername)
        worksheet.update_cells(l_memberid)
        worksheet.update_cells(l_totsu)
        worksheet.update_cells(l_totsunow)
        worksheet.update_cells(l_mogi)
        # ボス情報
        bossindex  = 0
        nowboss    = 0
        round      = 1
        stage      = 1
        hp         = bosshp[0]
        yoyaku     = [[], [], [], [], []]
        yoyakuname = ["", "", "", "", ""]
        l_nowboss  = worksheet.range(C_NOWBOSS)
        l_bosshp   = worksheet.range(C_BOSSHP)
        l_yoyaku   = worksheet.range(C_YOYAKU)
        for i in range(5):
            l_nowboss[i].value  = ""
            l_bosshp[i].value   = ""
            l_yoyaku[i].value   = ""
        l_nowboss[0].value    = "★"
        l_bosshp[0].value     = str(hp)
        worksheet.update_cells(l_nowboss)
        worksheet.update_cells(l_bosshp)
        worksheet.update_cells(l_yoyaku)
        worksheet.update_acell(C_ROUND, round)
        worksheet.update_acell(C_STAGE, stage)
        # ダメージ記録系
        dmgindex = [[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0],[0,0,0,0,0]]
        strdmg = SHEETNAME + '!' + C_DMGALL
        wsclass.values_clear(strdmg)
        for i in range(3):
            strdmg = SHEETNAME + '!' + C_DMGCNTALL2[i]
            wsclass.values_clear(strdmg)
        # 完了メッセージ
        await channel.send("お姉ちゃんだよ！")
                        
    # ここから真面目
    if message.content == "!cb read":
        channel = client.get_channel(CHANNEL_T)
        await channel.send("読み込んでくるから、待っててね。")
        membername = [i.value for i in worksheet.range(C_MEMBERNAME) if i.value != ""]
        usercount = len(membername)
        memberid = [int(i.value) for i in worksheet.range(C_MEMBERID) if i.value != ""]
        totsucount = [int(i.value) for i in worksheet.range(C_TOTSU) if i.value != ""]
        totsunow = [int(i.value) for i in worksheet.range(C_NOWTOTSU) if i.value != ""]
        simulated = [int(i.value) for i in worksheet.range(C_MOGI) if i.value != ""]
        taskill = [0] * usercount
        yoyakuname = [i.value for i in worksheet.range(C_YOYAKU)]
        for i in range(5):
            yoyakunamelist = [i for i in yoyakuname[i].split(",") if i != ""]
            if len(yoyakunamelist) == 0:
                yoyaku[i] = []
            else:
                yoyaku[i] = [memberid[membername.index(j)] for j in yoyakunamelist]
        bossindex = [i.value for i in worksheet.range(C_NOWBOSS)].index("★")
        l_bosshp = [i.value for i in worksheet.range(C_BOSSHP)]
        hp = int(l_bosshp[bossindex])
        round = int(worksheet.acell(C_ROUND).value)
        stage = int(worksheet.acell(C_STAGE).value)
        nowboss = (round - 1) * 5 + bossindex
        fincount = int(worksheet.acell('V3').value)
        for i in range(3):
            tmpdmgcnt = worksheet.range(C_DMGCNTALL2[i])
            for j in range(5):
                if tmpdmgcnt[j].value != "":
                    dmgindex[i][j] = int(tmpdmgcnt[j].value)
                else:
                    dmgindex[i][j] = 0
        print( dmgindex )
        await channel.send("読み込み出来たよ")


    # 凸るとき
    if message.content == "凸":
        # 開始報告した人を名前リストから探し、凸数を更新する
        i = authorindex(message)
        if totsunow[i] == 0:
            if totsucount[i] >= 3:
                await message.channel.send(f"{message.author.mention}君？キミの凸はもう終わってるはずだよ？")
            else:
                channel = client.get_channel(CHANNEL_T)
                await channel.send(f"{message.author.mention}君が{str(totsucount[i]+1)}凸目開始するみたいだよ。")
                totsunow[i] = 1
                gsvalueset(C_NOWTOTSU, i, 1)
        elif totsunow[i] == 1:
            await message.channel.send(f"{message.author.mention}君？キミは今{str(totsucount[i]+1)}凸目の途中だよ")
        elif totsunow[i] == -1:
            channel = client.get_channel(CHANNEL_T)
            await channel.send(f"{message.author.mention}の持ち越しだよ")
            totsunow[i] = 2
            gsvalueset(C_NOWTOTSU, i, 2)
        elif totsunow[i] == 2:
            await message.channel.send(f"{message.author.mention}君は今持ち越し中だよ")

    if message.content == "凸らない":
        channel = client.get_channel(CHANNEL_T)
        i = authorindex(message)
        if totsunow[i] == 1:
            totsunow[i] = 0
            gsvalueset(C_NOWTOTSU, i, 0)
            await channel.send(f"{message.author.mention}の凸を取り消したわ")
        elif totsunow[i] == 2:
            totsunow[i] = -1
            gsvalueset(C_NOWTOTSU, i, -1)
            await channel.send(f"{message.author.mention}君の持ち越し凸を取り消したわ")
        elif totsucount[i] <= 0:
            await channel.send(f"{message.author.mention}君、あなた凸宣言してないわよ？")

    if re.match( "凸った@[0-9]+", message.content ):          # メッセージが「凸終了@XXX(数字)」かどうか？を正規表現でチェックする
        if re.match("凸った@[0-9]+代理", message.content):
            n = message.content.find("代理")
            damage = int(message.content[4:n])
            i = membername.index(message.content[n+2:])
            enderid = memberid[i]
            endermention = client.get_user(enderid).mention
        else:
            damage = int(message.content[4:])
            enderid = message.author.id
            endermention = message.author.mention
        i = memberid.index(enderid)
        if damage <= hp:
            channel = client.get_channel(CHANNEL_T)
            if totsunow[i] >= 1:                    # 凸宣言をしたか
                totsucount[i] += 1                      # 凸回数をカウントアップする
                if totsucount[i] == 3:                  # 3なら終わりメッセージも追加
                    fincount += 1                       # fincount（凸終了人数）をカウントアップ（+1）する
                    channel = client.get_channel(CHANNEL_FIN)
                    await channel.send(f"{endermention}の3凸は終了。お疲れ様。 凸完了{str(fincount)}人目")
                    channel = client.get_channel(CHANNEL_T)
                    await channel.send(f"{endermention}の3凸終了よ。")
                    gsvalueset(C_TOTSU, i, 3)
                elif totsucount[i] > 3:                 # 3より大きければエラーメッセージ表示
                    await channel.send(f"{endermention}君の凸報告は終わっているはずよ、落ち着いて")
                else:                                   # 3より小さいとき
                    await channel.send(f"{endermention}君は {str(totsucount[i])}凸目終了したわ。")
                    gsvalueset(C_TOTSU, i, totsucount[i])
                if synstatus == 6:                     # 同時凸用処理
                    channel = client.get_channel(CHANNEL_SYN)
                    if endermention == syn1mention:
                        await channel.send(f"{endermention}が凸完了したから{syn2mention}は戦闘開始してちょうだい。")
                    elif endermention == syn2mention:
                        await channel.send(f"{endermention}の凸完了したから{syn1mention}は戦闘開始してちょうだい。")
                    else:
                        await channel.send("同時凸対象外の凸完了宣言があったわね。")
                    await channel.send("同時凸ナビを終わるわ。お疲れ様。")
                    syn1mention = ""
                    syn2mention = ""
                    synstatus = 0
                    othermention = ""
                    channel = client.get_channel(CHANNEL_T)
                if totsucount[i] <= 3:
                    hp -= damage
                    await channel.send( f"{boss[bossindex]}の残りのHPは約{str(hp)}万みたいだね。" )
                    # 凸募集リストから削除
                    if membername[i] in bosyu_list:
                        bosyu_list.remove(membername[i])
                    # スプレッドシートの残りHPを更新する
                    gsvalueset(C_BOSSHP, bossindex, str(hp))
                    # スプシにダメージを残す（平均ダメージ計算用）
                    if totsunow[i] != 2:    
                        c_dmgwrite = C_DMG[stage-1][bossindex] % (dmgindex[stage-1][bossindex]+3,dmgindex[stage-1][bossindex]+3)   # スプシに書き込むセルの位置を取得する
                        l_dmgwrite = worksheet.range(c_dmgwrite)
                        l_dmgwrite[0].value = client.get_user(enderid).name
                        l_dmgwrite[1].value = damage
                        worksheet.update_cells(l_dmgwrite)
                        dmgindex[stage-1][bossindex] += 1                                                        # スプシのダメージ書き込みインデックスを更新する
                        worksheet.update_acell(C_DMGCNT[stage-1][bossindex], dmgindex[stage-1][bossindex])
                totsunow[i] = 0
                gsvalueset(C_NOWTOTSU, i, 0)
            else:
                await message.channel.send("凸る時にはまず'凸'って宣言してね。持ち越しでも'凸'よ")
        else:
            await message.channel.send(f"エラー発生。残りHP以上のダメージが入力されたわ\nLAなら「凸った@LA」よ。違うなら「凸った@」の後ろのダメージを{str(hp)}より小さくしてね")

    if message.content.startswith("凸った@LA"):
        if message.content == "凸った@LA":
            i = memberid.index(message.author.id)
        elif message.content.startswith("凸った@LA代理"):
            i = membername.index(message.content[8:])
        if totsunow[i] == 1:
            totsunow[i] = -1
            gsvalueset(C_NOWTOTSU, i, -1)
            nowboss += 1
            round, bossindex = divmod(nowboss, 5)
            round += 1
            stage = roundstage(round)
            hp = bosshp[bossindex]
            if dmgindex[stage-1][bossindex] == 0:
                dmgmsg = "\n次の周から平均ダメージ表示します。"
            else:
                dmgave = worksheet.acell(C_DMGAVE[stage-1][bossindex]).value
                dmgave = math.floor(float(dmgave))
                kaisu,amari = divmod(hp, int(dmgave))
                dmgmsg = f"\n平均ダメージは{int(dmgave)}万だから{kaisu}人で{amari}万残るぐらいかしら。"
            channel = client.get_channel(CHANNEL_T)
            await channel.send(f"<@&{roles_mem}> {stage}段階目{boss[bossindex]}({round}周目)   HPは{str(hp)}万よ。" + dmgmsg)
            # スプシのボス情報を更新する
            for i in range(5):
                if i == bossindex:
                    gsvalueset(C_NOWBOSS, i, "★")
                    gsvalueset(C_BOSSHP, i, str(hp))
                else:
                    gsvalueset(C_NOWBOSS, i, "")
                    gsvalueset(C_BOSSHP, i, "")
            worksheet.update_acell(C_ROUND, str(round))
            worksheet.update_acell(C_STAGE, str(stage))
            # 予約者に通知
            if len(yoyaku[bossindex]) == 0:
                await channel.send( '予約は...ないわね。' )
            else:
                tmessage = "行きたい人は..."
                for tmember in yoyaku[bossindex]:
                    tuser = client.get_user(tmember)
                    if totsunow[memberid.index(tuser.id)] == 2 or totsunow[memberid.index(tuser.id)] == -1:
                        tmessage += f"{tuser.mention}(持ち越し) "
                    else:
                        tmessage += f"{tuser.mention} "
                tmessage += f'の{str(len(yoyaku[bossindex]))}人よ。\n行ける人は行ってね、行けない人も連絡くれるとありがたいわ。\n{boss[bossindex]}の行きたい人リストは一度クリアします。'
                await channel.send(tmessage)
                yoyaku[bossindex] = []
                gsvalueset(C_YOYAKU, bossindex, "")
        elif totsunow[i] == 0:
            await message.channel.send("凸る時にはまず'凸'って宣言してね")
        elif totsunow[i] == 2:
            totsunow[i] = 0
            gsvalueset(C_NOWTOTSU, i, 0)
            nowboss += 1
            round, bossindex = divmod(nowboss, 5)
            round += 1
            stage = roundstage(round)
            hp = bosshp[bossindex]
            if dmgindex[stage-1][bossindex] == 0:
                dmgmsg = "\n次の周から平均ダメージ表示します。"
            else:
                dmgave = worksheet.acell(C_DMGAVE[stage-1][bossindex]).value
                dmgave = math.floor(float(dmgave))
                kaisu,amari = divmod(hp, int(dmgave))
                dmgmsg = f"\n平均ダメージは{int(dmgave)}万だから{kaisu}人で{amari}万残るぐらいかしら。"
            channel = client.get_channel(CHANNEL_T)
            await channel.send(f"<@&{roles_mem}> {stage}段階目{boss[bossindex]}({round}周目)   HPは{str(hp)}万よ。" + dmgmsg)
            # スプシのボス情報を更新する
            for i in range(5):
                if i == bossindex:
                    gsvalueset(C_NOWBOSS, i, "★")
                    gsvalueset(C_BOSSHP, i, str(hp))
                else:
                    gsvalueset(C_NOWBOSS, i, "")
                    gsvalueset(C_BOSSHP, i, "")
            worksheet.update_acell(C_ROUND, str(round))
            worksheet.update_acell(C_STAGE, str(stage))
            # 予約者に通知
            if len(yoyaku[bossindex]) == 0:
                await channel.send( '予約は...ないわね。' )
            else:
                tmessage = "行きたい人は"
                for tmember in yoyaku[bossindex]:
                    tuser = client.get_user(tmember)
                    if totsunow[memberid.index(tuser.id)] == 2 or totsunow[memberid.index(tuser.id)] == -1:
                        tmessage += f"{tuser.mention}(持ち越し) "
                    else:
                        tmessage += f"{tuser.mention} "
                tmessage += f'の{str(len(yoyaku[bossindex]))}人よ。\n行ける人は行ってね、行けない人も連絡をくれると嬉しいわ。\n{boss[bossindex]}の行きたい人リストは一度クリアします'
                await channel.send(tmessage)
                yoyaku[bossindex] = []
                gsvalueset(C_YOYAKU, bossindex, "")

    if message.content == "凸った":
        await message.channel.send('凸ったのあとに@を付けて、万単位で与えたダメージを加えてね（例：凸った@234）')

    # 模擬戦
    if message.content == "模擬":
        channel = client.get_channel(CHANNEL_T)
        await channel.send(f"{message.author.mention}は模擬戦をするらしいわ")
        i = authorindex(message)
        simulated[i] = 1
        gsvalueset(C_MOGI, i, 1)

    if message.content == "模擬った":
        channel = client.get_channel(CHANNEL_T)
        await channel.send(f"{message.author.mention}が模擬戦を終えたそうよ")
        i = authorindex(message)
        simulated[i] = 0
        gsvalueset(C_MOGI, i, 0)

    if message.content == "模擬情報":
        channel = client.get_channel(CHANNEL_S)
        smessage = "今模擬戦をやっているのは\n"
        scount = 0
        for i in range(usercount):
            if simulated[i] == 1:
                smessage += f"{membername[i]}\n"
                scount += 1
        if scount == 0:
            await channel.send(f"{smessage}誰もいないわ。")
        else:
            await channel.send(f"{smessage}の{str(scount)}人よ。")

    if message.content == "凸残り":  # 凸残ってる人だけ表示する場合
        tmessage1 = "1凸残りは\n"
        tmessage2 = "2凸残りは\n"
        tmessage3 = "3凸残りは\n"
        tmessage11 = ""
        tmessage12 = ""
        tmessage13 = ""
        tcount1 = 0
        tcount2 = 0
        tcountMOT = 0
        for i in range(usercount):                      # i=0からi=29まで30回繰り返す処理を実行する
            if totsucount[i] == 2:                      # 凸回数2回なら残り1凸
                if totsunow[i] == -1 or totsunow[i] == 2:
                    tmessage11 += membername[i] + "(持ち越し中)\n"
                    tcountMOT += 1
                else:
                    tmessage1 += membername[i] + "\n"
                tcount1 += 1
                tcount2 += 1
            elif totsucount[i] == 1:                    # 凸回数1回なら残り2凸
                if totsunow[i] == -1 or totsunow[i] == 2:
                    tmessage12 += membername[i] + "(持ち越し中)\n"
                    tcountMOT += 1
                else:
                    tmessage2 += membername[i] + "\n"
                tcount1 += 2
                tcount2 += 1
            elif totsucount[i] == 0:                    # 凸回数0回なら残り3凸
                if totsunow[i] == -1 or totsunow[i] == 2:
                    tmessage13 += membername[i] + "(持ち越し中)\n"
                    tcountMOT += 1
                else:
                    tmessage3 += membername[i] + "\n"
                tcount1 += 3
                tcount2 += 1
        tmessage = tmessage1 + tmessage11 + tmessage2 + tmessage12 + tmessage3 + tmessage13
        channel = client.get_channel(CHANNEL_S)
        await channel.send( '---[現在の残り凸状況]---' )
        await channel.send( f'{tmessage}以上 残り{str(tcount2)}人(うち持ち越し中{str(tcountMOT)}人)\n残り凸数合計{str(tcount1)}(持ち越し{tcountMOT})よ。' )

    if message.content == "全体状況":  # 全員の凸状況を把握したいとき
        channel = client.get_channel(CHANNEL_S)
        await channel.send( '---[現在の凸状況]---' )
        await channel.send( f'今のボスは__{stage}段階目__、__{boss[bossindex]}__、__{round}周目__で残りHPは__{str(hp)}万__よ。' )
        tmessage0 = "3凸終了\n"
        tmessage1 = "1凸残り\n"
        tmessage2 = "2凸残り\n"
        tmessage3 = "3凸残り\n"
        tmessage11 = ""
        tmessage12 = ""
        tmessage13 = ""
        tcount1 = 0
        tcount2 = 0
        tcountMOT = 0
        for i in range(usercount):                      # i=0からi=29まで30回繰り返す処理を実行する
            if totsucount[i] == 3:                      # 3凸終わった人
                tmessage0 += membername[i] + "\n"
            elif totsucount[i] == 2:                      # 凸回数2回なら残り1凸
                if totsunow[i] == -1 or totsunow[i] == 2:
                    tmessage11 += membername[i] + "(持ち越し中)\n"
                    tcountMOT += 1
                else:
                    tmessage1 += membername[i] + "\n"
                tcount1 += 1
                tcount2 += 1
            elif totsucount[i] == 1:                    # 凸回数1回なら残り2凸
                if totsunow[i] == -1 or totsunow[i] == 2:
                    tmessage12 += membername[i] + "(持ち越し中)\n"
                    tcountMOT += 1
                else:
                    tmessage2 += membername[i] + "\n"
                tcount1 += 2
                tcount2 += 1
            elif totsucount[i] == 0:                    # 凸回数0回なら残り3凸
                if totsunow[i] == -1 or totsunow[i] == 2:
                    tmessage13 += membername[i] + "(持ち越し中)\n"
                    tcountMOT += 1
                else:
                    tmessage3 += membername[i] + "\n"
                tcount1 += 3
                tcount2 += 1
        tmessage = tmessage1 + tmessage11 + tmessage2 + tmessage12 + tmessage3 + tmessage13
        channel = client.get_channel(CHANNEL_S)
        await channel.send( '---[現在の残り凸状況]---' )
        await channel.send( f'```{tmessage}以上 残り{str(tcount2)}人(うち持ち越し中{str(tcountMOT)}人)```\n残り凸数合計{str(tcount1)}(+持ち越し{tcountMOT})よ。' )

    if message.content == "私の状況":
        i = authorindex(message)
        await message.channel.send(f'確認したところ、今のボスは{stage}段階目{boss[bossindex]}、{round}周目)、残りHPは{str(hp)}万\n{message.author.mention}さんの残り凸数は{str(3-totsucount[i])}のようね、間違いないかしら？')

    if message.content.startswith('!タスキル'):
        channel = client.get_channel(CHANNEL_T)
        i = authorindex(message)
        taskill[i] += 1
        if taskill[i] == 1:
            await channel.send(f"{message.author.mention}君、タスキルしたの！？あり得ない！！！お姉ちゃんチョーーーーーーーーーーーーープ！！！！！！")
            tskl = discord.utils.get(message.guild.roles, name='タスキル')
            await message.author.add_roles(tskl)
        else:
            await channel.send(f"おい...{message.author.mention}君？{taskill[i]}回目よ...?お姉ちゃんとの言いつけも守れないなんて失望したわ...")
            tskl = discord.utils.get(message.guild.roles, name='タスキル')
            await message.author.add_roles(tskl)

    if message.content.startswith('!cancel'):
        channel = client.get_channel(CHANNEL_T)
        await channel.send(f"{message.author.mention}タスキルしてなかったの？お姉ちゃんを弄んだのね！！！酷いわ！！！")
        tskl = discord.utils.get(message.guild.roles, name='タスキル')
        await message.author.remove_roles(tskl)

    ################ 同時凸ナビ用処理 ################
    if message.content == "!同時":
        channel = client.get_channel(CHANNEL_SYN)
        i = authorindex(message)
        if totsunow[i] == 0:
            if synstatus == 0:      # 同時でないとき
                syn1mention = message.author.mention
                await channel.send(f"同時凸ナビを開始します。\n {syn1mention}は待機してて。\n同時凸を開始する為にもう一人必要だから、それまで待ってね" )
                synstatus = 1
                totsunow[i] = 1
                gsvalueset(C_NOWTOTSU, i, 1)
            elif synstatus == 1:    # 一人だけ同時宣言のとき。
                syn2mention = message.author.mention
                await channel.send(f"二人分の入力を確認、{syn1mention}と{syn2mention}は戦闘開始後、戦闘をメニューを押して中止してコマンド「/in」を打ってちょうだい。\nそれじゃ、戦闘を始めてちょうだい。" )
                synstatus = 2
                totsunow[i] = 1
                gsvalueset(C_NOWTOTSU, i, 1)
            else:
                await channel.send(f"{message.author.mention}死にたいようね？" )
        else:
            await channel.send(f"{message.author.mention}小田真理！")


    if message.content == "/in":
        channel = client.get_channel(CHANNEL_SYN)
        if synstatus == 2:
            if message.author.mention == syn1mention:
                await channel.send(f"{message.author.mention}はそのまま{syn2mention}の入力を待つように。" )
                synstatus = 3
                othermention = syn2mention
            elif message.author.mention == syn2mention:
                await channel.send(f"{message.author.mention}はそのまま{syn1mention}の入力を待つように。" )
                synstatus = 3
                othermention = syn1mention
            else:
                await channel.send(f"{message.author.mention}、今進行中よ、邪魔だからすっこんでなさい" )
        elif synstatus == 3:
            if othermention == message.author.mention:
                await channel.send(f"対象二人の戦闘開始が確認できたわ。\n{syn1mention}と{syn2mention}は戦闘終了5秒前まで進めたら戦闘をもう一度止めてコマンド「/last5」を打ってちょうだい。\nそれじゃ、戦闘を再開して。" )
                synstatus = 4
            else:
                await channel.send(f"{message.author.mention}貴様、どうやら死にたいようだな、良かろう" )
        else:
            await channel.send(f"{message.author.mention}小田真理！" )


    if message.content == "/last5":
        channel = client.get_channel(CHANNEL_SYN)
        if synstatus == 4:
            if message.author.mention == syn1mention:
                othermention = syn2mention
                await channel.send(f"{message.author.mention}はそのまま{othermention}を待って。" )
                synstatus = 5
            elif message.author.mention == syn2mention:
                othermention = syn1mention
                synstatus = 5
            else:
                await channel.send(f"{message.author.mention}、黙りなさい" )
        elif synstatus == 5 and message.author.mention == othermention:
            await channel.send(f"{syn1mention}と{syn2mention}はどちらが先に通すか話し合って決めて。\n先に通す人は戦闘終了後にコマンド「凸終了@XXX」を忘れず入力するように。\n二人の予想ダメージを!同時予測XXX&YYYと打てば予測返却時間が出るから困ったら使ってね。\nそれじゃ、先に通す人は戦闘開始して。" )
            synstatus = 6
        else:
            await channel.send(f"{message.author.mention}小田真理！" )


    if message.content.startswith("返却時間"):
        n = message.content.find("&")
        damageA = int(message.content[4:n])
        damageB = int(message.content[n+1:])
        if damageB == 0 :               # 0割になるエラー
            await message.channel.send(f"ダメージ0はダメだよ")
        elif (damageA + damageB) < hp:
            await message.channel.send(f"その二人のダメージじゃボスを倒せないわね")
        else:
            if hp < damageA:
                await message.channel.send(f"{str(damageA)}→{str(damageB)}だと最初の人のダメージでボスが死ぬわ")
            else:
                m = min( 90, 100 + (-(hp - damageA) * 90 // damageB) + 10)
                await message.channel.send(f"*{str(damageA)}*→*{str(damageB)}*だと予測返却時間は__{str(m)}秒__よ")
            if hp < damageB:
                await message.channel.send(f"{str(damageB)}→{str(damageA)}だと最初の人のダメージでボスが死ぬわ")
            else:
                m = min( 90, 100 + (-(hp - damageB) * 90 // damageA + 10 ))
                await message.channel.send(f"*{str(damageB)}*→*{str(damageA)}*だと予測返却時間は__{str(m)}秒__よ")


    if message.content == "!同時キャンセル":
        for i in range(usercount):
            if client.get_user(memberid[i]).mention == syn1mention or client.get_user(memberid[i]).mention == syn2mention:
                totsunow[i] = 0
                gsvalueset(C_NOWTOTSU, i, 0)
        syn1mention = ""
        syn2mention = ""
        synstatus = 0
        othermention = ""
        channel = client.get_channel(CHANNEL_SYN)
        await channel.send(f"キャンセルを受け付けました。同時凸ナビを終了します。" )

    ############## ボスに行きたい人が予約するとき ################
    if re.match("希望[1-5]$", message.content):
        x = int(message.content[2:3]) - 1
        if memberid[authorindex(message)] in yoyaku[x]:
            await message.channel.send(f"{message.author.mention}君、既に__{boss[x]}__に予約入ってるよ？")
        else:
            channel = client.get_channel(CHANNEL_RSV)
            await channel.send(f"{message.author.mention}君の__{boss[x]}__の予約を受け付けたよ。")
            yoyaku[x].append(message.author.id)
            yoyakuupdate(x)

    #予約取り消し
    if message.content == "凸れない":
        channel = client.get_channel(CHANNEL_RSV)
        for i in range(5):
            if message.author.id in yoyaku[i]:
                yoyaku[i].remove(message.author.id)
                yoyakuupdate(i)
        await channel.send(f"{message.author.mention}のルートをリセットしたわ。")


    if message.content == "凸りたいリスト":
        lindex = bossindex
        tmessage = ""
        for i in range(5):
            if lindex >= 4:
                lindex = 0
            else:
                lindex += 1
            tmessage += f'{boss[lindex]}の申請者は'
            if len(yoyaku[lindex]) == 0:
                tmessage += "...今のところいないわね。\n"
            else:
                for tmember in yoyaku[lindex]:
                    tuser = client.get_user(tmember)
                    if totsunow[memberid.index(tuser.id)] == 2 or totsunow[memberid.index(tuser.id)] == -1:
                        tmessage += f"{tuser.mention}(持ち越し優先) "
                    else:
                        tmessage += f"{tuser.mention} "
                tmessage += f'の{str(len(yoyaku[lindex]))}人よ。\n'
        await message.channel.send(tmessage)


    if message.content.startswith("/凸募集@"):
        bosyu_list = []
        recruitment = int(message.content[5:])
        text = "あと{}人 募集中\n"
        revmsg = text.format(recruitment)
        msg = await message.channel.send(revmsg)
        await msg.add_reaction('\u21a9')
        await msg.add_reaction('\u23eb')
        while len(bosyu_list) < int(message.content[5:]):
            reaction = await client.wait_for("reaction_add")
            bot_reaction = reaction[0]
            bot_member = reaction[1]
            if bot_member != msg.author:
                if bot_reaction.emoji == '\u21a9':
                    if bot_member.name in bosyu_list:
                        bosyu_list.remove(bot_member.name)
                        recruitment += 1
                        await msg.edit(content=text.format(recruitment) + '\n'.join(bosyu_list))
                elif bot_reaction.emoji == '\u23eb':
                    if bot_member.name in bosyu_list:
                        pass
                    else:
                        bosyu_list.append(bot_member.name)
                        recruitment -= 1
                        await msg.edit(content=text.format(recruitment) + '\n'.join(bosyu_list))
                elif bot_reaction.emoji == '✖':
                    await msg.edit(content='募集終了\n'+ '\n'.join(bosyu_list))
                    break
                await msg.remove_reaction(bot_reaction.emoji, bot_member)
        else:
            await msg.edit(content='募集終了\n'+ '\n'.join(bosyu_list))


    if message.content == "/凸募集状況":
        channel = client.get_channel(CHANNEL_S)
        if bosyu_list:
            await channel.send("今凸待ちの人は\n" + "\n".join(bosyu_list) + f"\nの{str(len(bosyu_list))}人よ")
        else:
            await channel.send("今凸待ちの人はいないようね")

    if message.content == "ピーチ":
        channel = client.get_channel(CHANNEL_T)
        await channel.send(f"ピーチ「<@&{roles_mem}> 助けてマリオ！」")

    if re.match( "周回予測ダメージ@[0-9]+", message.content ):        # メッセージが「周回予測ダメージ@XXX(数字)」かどうか？を正規表現でチェックする
        damage = int(message.content[9:])
        await message.channel.send( syucalc( damage ) )

    if re.match( "周回予測スコア@[0-9]+", message.content ):          # メッセージが「周回予測スコア@XXX(数字)」かどうか？を正規表現でチェックする
        cmdscr = int(message.content[8:])
        await message.channel.send( syucalcs( cmdscr ) ) 

    if client.user in message.mentions: # 話しかけられたかの判定
        reply = (f'{message.author.mention}',f'{message.author.mention}よしよし、良い子だね～',f'{message.author.mention} 黙りなさい',f'{message.author.mention}小田真理！！！',f'{message.author.mention}にゃん',f'{message.author.mention}なんや',f'{message.author.mention}ちゅっちゅ',f'{message.author.mention}話しかけんじゃねえよ！') # 返信メッセージの作成
        await message.channel.send(random.choice(reply)) # 返信メッセージを送信

gspreadtimer = 0
now_old = ""

# 50秒に一回ループ
@tasks.loop(seconds=50)
async def loop():
    await client.wait_until_ready()

    global fincount
    global totsucount
    global totsunow
    global simulated
    global taskill
    global syn1mention
    global syn2mention
    global othermention
    global synstatus
    global gspreadtimer
    global workbook
    global worksheet
    global now_old

    now = datetime.now().strftime('%H:%M')      # 現在の時刻
    if now == '19:00' and now_old != now:
        channel = client.get_channel(CHANNEL_ZAT)
        await channel.send('デイリー忘れたらお姉ちゃんの頭突きが飛んでくるよ！')

    elif now == '20:00' and now_old != now:
#        channel = client.get_channel(CHANNEL_ZAT)
#        await channel.send('```本日のクランバトルの集計を開始します。```')
        # 色々リセット
        await client.wait_until_ready()
        guild = client.get_guild(ID_SRV)
        tskl = discord.utils.get(guild.roles,name='タスキル')
        for member in guild.members:
            if tskl in member.roles:
               await member.remove_roles(tskl)
        fincount = 0
        totsucount = [0] * usercount
        totsunow = [0] * usercount
        simulated = [0] * usercount
        taskill = [0] * usercount
        syn1mention = ""
        syn2mention = ""
        othermention = ""
        synstatus = 0
#        channel = client.get_channel(CHANNEL_ZAT)
#        await channel.send('プリコネの日付更新の時間よ\n5時20分になったら誰か順位のスクショをお願いできるかしら？')
        #スプレッドシートを初期化する
        for i in range(30):
            gsvalueset(C_TOTSU, i, 0)
            gsvalueset(C_NOWTOTSU, i, 0)
            gsvalueset(C_MOGI, i, 0)

    now_old = now                               # 前回の時刻

    # 定期的にスプシに接続しなおす
    gspreadtimer += 1
    if(gspreadtimer >= 60):      # 一定時間が経過したら
        print(f"{now} スプシ再ログイン処理します")
        gspreadtimer = 0
        scope = ['https://spreadsheets.google.com/feeds','https://www.googleapis.com/auth/drive']
        credentials = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
        gc = gspread.authorize(credentials)
        worksheet = gc.open_by_key(SPREADSHEET_KEY).sheet1


#ループ処理実行
loop.start()


# Botの起動とDiscordサーバーへの接続
client.run( TOKEN )
