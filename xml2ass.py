# -*- coding:utf-8 -*-
import os
import re
import sys
import math
import xmltodict
import json
import shlex

def sec2hms(sec):  # 转换时间的函数
    hms = str(int(sec//3600)).zfill(2)+':' + \
        str(int((sec % 3600)//60)).zfill(2)+':'+str(round(sec % 60, 2))
    return hms

COLOR_MAP = {'black': '000000', 'white': 'FFFFFF', 'red': 'FF0000', 'green': '00ff00', 'yellow': 'FFFF00', 'blue': '0000FF', 'orange': 'ffcc00',
            'pink': 'FF8080', 'cyan': '00FFFF', 'purple': 'C000FF', 'niconicowhite': 'cccc99', 'white2': 'cccc99', 'truered': 'cc0033',
            'red2': 'cc0033', 'passionorange': 'ff6600', 'orange2': 'ff6600', 'madyellow': '999900', 'yellow2': '999900', 'elementalgreen': '00cc66',
            'green2': '00cc66', 'marineblue': '33ffcc', 'blue2': '33ffcc', 'nobleviolet': '6633cc', 'purple2': '6633cc'}  # 颜色列表

def get_color(styles):
    color = 'FFFFFF'
    color_important = None

    for style in styles:  # 颜色调整
        m = re.match(r'#([0-9A-Fa-f]{6})', style)
        if m:
            color_important = str(m[1])
        elif style in COLOR_MAP:
            color = COLOR_MAP[style]
    color = color_important or color
    assColor = f'\\1c&H{color[-2:]}{color[2:-2]}{color[:2]}&'
    if color == '000000':
        assColor += '\\3c&HFFFFFF&'
    return assColor


def xml2ass(xml_name):
    with open(xml_name, 'r', encoding='utf-8') as fx:
        if xml_name.lower().endswith('.xml'):
            xml_dict = xmltodict.parse(fx.read(), strip_whitespace=False)
            # 获取所有弹幕
            if 'NiconamaComment' in xml_dict:
                chats = xml_dict['NiconamaComment']['LiveCommentDataArray']['chat']
            else:
                chats = xml_dict['packet']['chat']
            chats = [{key.lstrip('@#'): v for key, v in d.items()}
                     for d in chats]

        elif xml_name.lower().endswith('.json'):
            json_dict = json.load(fx)
            chats = []
            for d in json_dict:
                if 'chat' in d:
                    d = d['chat']
                if not 'vpos' in d:
                    continue
                if 'content' in d:
                    d['text'] = d.pop('content')
                chats.append(d)
    
    if not chats[1].get('premium'):
        chats.sort(key=lambda x: int(x.get('vpos') or 0))  # 按 vpos 排序
    else:
        chats.sort(key=lambda x: int(x.get('date') or 0))  # 普通nico按 date 排序
    for i in range(len(chats)):
        if chats[i]['vpos'] != '0':  #确定开始时的date
            dateStart = int(chats[i]['date']) - int(int(chats[i]['vpos'])//100)
            break
        dateStart = 0

    # 弹幕参数
    AASize = 18  # AA弹幕字体大小
    AAHighAdjust = 0  # AA弹幕行间间隔
    OfficeSize = 40  # 运营弹幕字体大小
    OfficeBgHeight = 72  # 运营弹幕背景遮盖高度
    fontName = 'Source Han Sans JP'
    danmakuSize = 68
    danmakuLineHeight = 64  # 弹幕行高度
    danmakuFontSpace = 2  # 弹幕行间间隔
    timeDanmaku = 8  # 普通弹幕持续时间，默认8秒
    limitLineAmount = 11  # 屏上弹幕行数限制
    danmakuPassageway = []  # 计算弹幕应该在哪一行出现
    for i in range(limitLineAmount):
        danmakuPassageway.append(0)
    dm_count = 0  # 处理同时出过多弹幕的情况
    vpos_now = 0
    include_aa = False  # 判断是否有AA弹幕
    voteCheck = False  # 判断投票是否开启
    videoWidth = 1280  # 视频宽度，默认3M码率生放，不用改
    videoHeight = 720  # 视频高度，默认3M码率生放，不用改
    fontSize = 64  # 普通弹幕字体大小
    officialCheck = False

    # 字幕行处理
    eventA = 'Comment: 0,0:00:00.00,0:00:00.00,AA,,0,0,0,,AA弹幕\n'  # AA弹幕
    eventO = 'Comment: 0,0:00:00.00,0:00:00.00,Office,,0,0,0,,运营弹幕\n'  # 运营弹幕
    eventD = 'Comment: 0,0:00:00.00,0:00:00.00,Danmaku,,0,0,0,,普通弹幕\n'  # 普通弹幕
    officeBg = f'm 0 0 l {videoWidth} 0 l {videoWidth} {OfficeBgHeight} l 0 {OfficeBgHeight}'  # 运营弹幕遮盖

    # 处理弹幕
    for chat in chats:
        if not chat.get('vpos'):
            continue
        premium = chat.get('premium')
        if chat.get('user_id'):
            user_id = chat['user_id']
        isOfficial = True if premium in ['2', '3'] or user_id == '-1'  else False
        if chat.get('text'):
            text = chat['text']
        elif isOfficial and voteCheck:
            text = '/vote stop'
        else:
            continue  # 文本
        mail = chat.get('mail', '')  # mail,颜色，位置，大小，AA
        vpos = int(chat['vpos']) if chat['vpos'] != '0' and not chat.get('premium') else (int(chat['date']) - dateStart) *100 # 读取时间
        # NCV now use whole second for operator's comment's vpos instead of 1/100 second for some reason so fix it here.
        # /nicoad seems isn't affected by this.
        if premium == '2' and not '/nicoad' in text:
            vpos *= 100
        startTime = sec2hms(round(vpos/100, 2))  # 转换开始时间
        endTime = sec2hms(round(vpos/100, 2)+timeDanmaku) if not isOfficial else sec2hms(round(vpos/100, 2)+14)  # 转换结束时间
        # 过滤弹幕
        has_ngword = False
        for ngword in ['※ NGコメント', '/clear', '/trialpanel',  '/spi', '/disconnect', '/gift', '/commentlock', '/nicoad', '/info', '/jump', '/play', '/redirect',
            'ニコニ広告しました', 'Display Forbidden', 'Hidden Restricted',  '30分延長しました', 'Ended', 'Display Restricted', 'Hide Marquee', '【ギフト貢献','/ichiba']:
            if ngword in text:
                has_ngword = True
                break
        if has_ngword:
            continue

        if officialCheck:  # 释放之前捕捉的运营弹幕
            if vpos-vposW > 1400 or isOfficial:
                if isOfficial:
                    endTimeW = startTime
                eventBg = 'Dialogue: 4,'+startTimeW+','+endTimeW+',Office,,0,0,0,,{\\an5\\p1\\pos('+str(
                    math.floor(videoWidth/2))+','+str(math.floor(OfficeBgHeight/2))+')\\bord0\\1c&H000000&\\1a&H78&}'+officeBg+'\n'
                textW = textW.replace('/perm', '')
                if 'href' in textW or 'http' in textW:
                    textW = re.sub(r'<a href=.*?><u>(.+?)</u></a>', r'\1', textW)
                    textW = re.sub(r'\(?http.*\)?$', '', textW)
                    assColorW = '\\1c&HFF8000&\\u1'
                else:
                    assColorW = get_color([])
                eventDm = 'Dialogue: 5,'+startTimeW+','+endTimeW+',Office,,0,0,0,,{\\an5\\pos('+str(math.floor(videoWidth/2))+','+str(
                    math.floor(OfficeBgHeight/2))+')\\bord0'+assColorW+'\\fsp0}'+textW.replace('/perm ', '')+'\n'
                if len(text) > 50:
                    eventDm = eventDm.replace('fsp0', 'fsp0\\fs30')
                eventO += eventBg+eventDm.replace('　', '  ')
                officialCheck = False

        assColor = get_color(mail.split(' '))
        if isOfficial:  # 处理运营弹幕
             # 处理投票开始和投票结果 for kari new
            if re.search(r'Poll$', text):
                split_text = shlex.split(text.replace('/enquete',''))
                split_text = [t.replace('\\', '') for t in split_text]
                startTimeQ = startTime
                textQ = split_text[0]
                textO = re.findall(r'\[(.+?)\]',text)
                textR = []
                voteCheck = True
                continue
            if voteCheck and 'Result' in text:
                textR = re.findall(r'[0-9.]+%',text)
                startTimeR = startTime
                continue
            #<chat date="1726749046" date_usec="125440000" thread="" premium="2" user_id="" vpos="2446">/vote new 【アンケート結果】本日の番組はいかがでしたか？
            # 　1：97.6% とても良かった
            # 　2：1.7% まぁまぁ良かった
            # 　3：0.3% ふつうだった
            # 　4：0.2% あまり良くなかった
            # 　5：0.2% 良くなかった</chat>
            # for NCV newest
            m = re.search(r'^/vote new\s+\【(.+?)\】(.+)', text)
            if m: # 处理投票开始和投票结果
                if m[1] == 'アンケート開始':
                    startTimeQ = startTime
                    textQ = m[2]
                    textO = [re.search(r'^.*\d+：(.+)$', t)[1] for t in text.splitlines()[1:]]
                    textR = []
                    voteCheck = True
                    continue
                elif m[1] == 'アンケート結果':
                    startTimeR = startTime
                    textR = [re.search(r'^.*\d+：(.+%).*$', t)[1] for t in text.splitlines()[1:]]
                    continue
            # for older websocket response
            # /vote start 本日の番組はいかがでしたか？ とても良かった まぁまぁ良かった ふつうだった あまり良くなかった 良くなかった
            # /vote showresult per 980 11 4 3 2
            # /vote stop
            if re.search(r'^/vote (start|showresult)', text):  # 处理投票开始和投票结果
                split_text = shlex.split(text)
                split_text = [t.replace('\\', '') for t in split_text]
                if split_text[1] == 'start':
                    startTimeQ = startTime
                    textQ = split_text[2]
                    textO = split_text[3:]
                    textR = []
                    voteCheck = True
                elif split_text[1] == 'showresult':
                    startTimeR = startTime
                    textR = split_text[3:]
                    textR = [f'{int(t)/10:.1f}%' for t in textR]
                continue

            if voteCheck:  # 生成投票
                endTimeV = sec2hms(round(vpos/100, 2))
                eventQBg = 'Dialogue: 4,'+startTimeQ+','+endTimeV+',Office,,0,0,0,,{\\an5\\p1\\pos('+str(
                    math.floor(videoWidth/2))+','+str(math.floor(OfficeBgHeight/2))+')\\bord0\\1c&H000000&\\1a&H78&}'+officeBg+'\n'
                eventQText = 'Dialogue: 5,'+startTimeQ+','+endTimeV+',Office,,0,0,0,,{\\an5\\pos('+str(math.floor(videoWidth/2))+','+str(
                    math.floor(OfficeBgHeight/2))+')\\1c&HFF8000&\\bord0\\fsp0}Q.{\\1c&HFFFFFF&}'+textQ.replace('<br>', '\\N')+'\n'
                eventQmask = 'Dialogue: 3,'+startTimeQ+','+endTimeV+',Office,,0,0,0,,{\\an5\\p1\\bord0\\1c&H000000&\\pos('+str(math.floor(videoWidth/2))+','+str(
                    math.floor(videoHeight/2))+')\\1a&HC8&}'+'m 0 0 l '+str(videoWidth+20)+' 0 l '+str(videoWidth+20)+' '+str(videoHeight+20)+' l 0 '+str(videoHeight+20)+'\n'
                if len(textQ) > 50:
                    eventQText = eventQText.replace('fsp0', 'fsp0\\fs30')
                eventO += eventQBg + eventQText + eventQmask
                fontSize_anketo = math.floor(fontSize/4*3)
                if len(textO) <= 3:
                    bgWidth = math.floor(videoWidth/4)
                    bgHeight = math.floor(videoHeight/3)
                    XArray = [[math.floor(bgWidth/2)], [math.floor(videoWidth/3)-40, (math.floor(videoWidth/2)-math.floor(videoWidth/3))+math.floor(
                        videoWidth/2)+40], [math.floor(videoWidth/2)-bgWidth-40, math.floor(videoWidth/2), math.floor(videoWidth/2)+bgWidth+40]]
                    numBg = 'm 0 0 l ' + \
                        str(fontSize*1.5)+' 0 l '+str(fontSize*1.5) + \
                        ' 0 l 0 '+str(fontSize*1.5)
                    bg = 'm 0 0 l ' + \
                        str(bgWidth)+' 0 l '+str(bgWidth)+' ' + \
                        str(bgHeight)+' l 0 '+str(bgHeight)
                    resultBg = 'm 0 0 s 150 0 150 60 0 60 c'
                    X = XArray[len(textO)-1]
                    Y = [360]
                    for j in range(len(Y)):
                        for i in range(len(X)):
                            voteNumBg = 'Dialogue: 5,'+startTimeQ+','+endTimeV+',Anketo,,0,0,0,,{\\an5\\p1\\bord0\\1c&HFFFFC8&\\pos('+str(
                                X[i]-math.floor(bgWidth/2)+fontSize*0.75)+','+str(Y[j]-math.floor(bgHeight/2)+fontSize*0.75)+')}'+numBg+'\n'
                            voteNumText = 'Dialogue: 5,'+startTimeQ+','+endTimeV+',Anketo,,0,0,0,,{\\an5\\bord0\\1c&HD5A07B&\\pos('+str(X[i]-math.floor(
                                bgWidth/2)+math.floor(fontSize/2))+','+str(Y[j]-math.floor(bgHeight/2)+math.floor(fontSize/2))+')}'+str(i+1)+'\n'
                            voteBg = 'Dialogue: 5,'+startTimeQ+','+endTimeV + \
                                ',Anketo,,0,0,0,,{\\an5\\p1\\3c&HFFFFC8&\\bord6\\1c&HD5A07B&\\1a&H78&\\pos('+str(
                                    X[i])+','+str(Y[j])+')}'+bg+'\n'
                            if len(textO[i]) <= 7:
                                textNow = '\\N'+textO[i]
                            elif 7 < len(textO[i]) <= 14:
                                textNow = '\\N' + \
                                    textO[i][0:7]+'\\N'+textO[i][7:]
                            elif len(textO[i]) > 14:
                                textNow = '\\N'+textO[i][0:7]+'\\N' + \
                                    textO[i][7:14]+'\\N'+textO[i][14:]
                            voteText = 'Dialogue: 5,'+startTimeQ+','+endTimeV + \
                                ',Anketo,,0,0,0,,{\\an5\\bord0\\1c&HFFFFFF&\\pos('+str(
                                    X[i])+','+str(Y[j])+')}'+textNow+'\n'
                            eventO += voteBg + voteText + voteNumBg + voteNumText
                            if textR != []:
                                voteResultBg = 'Dialogue: 5,'+startTimeR+','+endTimeV + \
                                    ',Anketo,,0,0,0,,{\\an5\\p1\\bord0\\1c&H3E2E2A&\\pos('+str(
                                        X[i])+','+str(Y[j]+math.floor(bgHeight/2))+')}'+resultBg+'\n'
                                voteResultext = 'Dialogue: 5,'+startTimeR+','+endTimeV + ',Anketo,,0,0,0,,{\\fs'+str(
                                    fontSize_anketo)+'\\an5\\bord0\\1c&H76FAF8&\\pos('+str(X[i])+','+str(Y[j]+math.floor(bgHeight/2))+')}'+str(textR[i])+'\n'

                                eventO += voteResultBg + voteResultext
                elif len(textO) >= 4:
                    bgWidth = math.floor(videoWidth/5)
                    bgHeight = math.floor(videoHeight/4)

                    XArray = [[math.floor(bgWidth/2)], [math.floor(videoWidth/3)-40, (math.floor(videoWidth/2)-math.floor(videoWidth/3))+math.floor(
                        videoWidth/2)+40], [math.floor(videoWidth/2)-bgWidth-40, math.floor(videoWidth/2), math.floor(videoWidth/2)+bgWidth+40]]
                    YArray = [[math.floor(videoHeight/2)], [math.floor(videoHeight/3), (math.floor(videoHeight/2)-math.floor(videoHeight/3))+math.floor(
                        videoHeight/2)], [math.floor(videoHeight/2)-bgHeight-20, math.floor(videoHeight/2)+20, math.floor(videoHeight/2)+bgHeight+60]]
                    X = XArray[2]
                    Y = YArray[2]
                    if len(textO) == 4:
                        bgWidth = math.floor(videoWidth/4)
                        bgHeight = math.floor(videoHeight/4)
                        X = XArray[1]
                        Y = YArray[1]
                    elif len(textO) >= 5 and len(textO) <= 6:
                        bgHeight = math.floor(videoHeight/4)
                        Y = YArray[1]
                    elif len(textO) == 8:
                        X = [160, 480, 800, 1120]
                        Y = YArray[1]
                    elif len(textO) > 6:
                        bgHeight = math.floor(videoHeight/4.5)
                        Y = YArray[2]

                    numBg = 'm 0 0 l '+str(math.floor(fontSize_anketo*1.25))+' 0 l '+str(
                        math.floor(fontSize_anketo*1.25))+' 0 l 0 '+str(math.floor(fontSize_anketo*1.25))
                    bg = 'm 0 0 l ' + \
                        str(bgWidth)+' 0 l '+str(bgWidth)+' ' + \
                        str(bgHeight)+' l 0 '+str(bgHeight)
                    resultBg = 'm 0 0 s 150 0 150 60 0 60 c'

                    num = 0
                    for j in range(len(Y)):
                        for i in range(len(X)):
                            if num == len(textO):
                                continue
                            voteNumBg = 'Dialogue: 5,'+startTimeQ+','+endTimeV+',Anketo,,0,0,0,,{\\an5\\p1\\bord0\\1c&HFFFFC8&\\pos('+str(X[i]-math.floor(
                                bgWidth/2)+math.floor(fontSize_anketo*1.25/2))+','+str(Y[j]-math.floor(bgHeight/2)+math.floor(fontSize_anketo*1.25/2))+')}'+numBg+'\n'
                            voteNumText = 'Dialogue: 5,'+startTimeQ+','+endTimeV+',Anketo,,0,0,0,,{\\fs'+str(fontSize_anketo)+'\\an5\\bord0\\1c&HD5A07B&\\pos('+str(
                                X[i]-math.floor(bgWidth/2)+math.floor(fontSize_anketo/3))+','+str(Y[j]-math.floor(bgHeight/2)+math.floor(fontSize_anketo/3))+')}'+str(num+1)+'\n'
                            voteBg = 'Dialogue: 5,'+startTimeQ+','+endTimeV + \
                                ',Anketo,,0,0,0,,{\\an5\\p1\\3c&HFFFFC8&\\bord6\\1c&HD5A07B&\\1a&H78&\\pos('+str(
                                    X[i])+','+str(Y[j])+')}'+bg+'\n'
                            if len(textO[num]) <= 7:
                                textNow = textO[num]
                            elif 7 < len(textO[num]) <= 14:
                                textNow = textO[num][0:7]+'\\N'+textO[num][7:]
                            elif len(textO[num]) > 14:
                                textNow = textO[num][0:7]+'\\N' + \
                                    textO[num][7:14]+'\\N'+textO[num][14:]
                            voteText = 'Dialogue: 5,'+startTimeQ+','+endTimeV+',Anketo,,0,0,0,,{\\fs'+str(
                                fontSize_anketo)+'\\an5\\bord0\\1c&HFFFFFF&\\pos('+str(X[i])+','+str(Y[j])+')}'+textNow+'\n'
                            eventO += voteBg + voteText + voteNumBg + voteNumText
                            if textR != []:
                                voteResultBg = 'Dialogue: 5,'+startTimeR+','+endTimeV + \
                                    ',Anketo,,0,0,0,,{\\an5\\p1\\bord0\\1c&H3E2E2A&\\pos('+str(
                                        X[i])+','+str(Y[j]+math.floor(bgHeight/2))+')}'+resultBg+'\n'
                                voteResultext = 'Dialogue: 5,'+startTimeR+','+endTimeV+',Anketo,,0,0,0,,{\\fs'+str(
                                    fontSize_anketo)+'\\an5\\bord0\\1c&H76FAF8&\\pos('+str(X[i])+','+str(Y[j]+math.floor(bgHeight/2))+')}'+str(textR[num])+'\n'
                                eventO += voteResultBg + voteResultext
                            num += 1
                voteCheck = False
                continue
            # 处理非投票运营弹幕
            startTimeW = startTime
            endTimeW = endTime
            textW = text.replace('/marquee ', '')
            vposW = vpos
            officialCheck = True

        else:  # 处理用户弹幕
            pos = 0
            is_aa = False
            text = text.replace('\n', '\\N')
            for style in mail.split(' '):  # 样式调整
                if style == 'ue':
                    pos = 8
                elif style == 'shita':
                    pos = 2
                elif style in ['gothic', 'mincho']:  # 判断AA弹幕
                    is_aa = True
                    include_aa = True
            if is_aa:  # AA弹幕跳过，在后一部分处理
                continue
            elif pos == 2:  # 底部弹幕
                eventD += 'Dialogue: 2,'+startTime+','+endTime + \
                    ',Danmaku,,0,0,0,,{\\an2'+assColor+'}'+text+'\n'
            elif pos == 8:  # 顶部弹幕
                eventD += 'Dialogue: 2,'+startTime+','+endTime + \
                    ',Danmaku,,0,0,0,,{\\an8'+assColor+'}'+text+'\n'
            else:  # 普通滚动弹幕
                if vpos > vpos_now:
                    vpos_now = vpos
                    dm_count = 0
                vpos_next_min = float('inf')
                vpos_next = int(vpos+1280/(len(text)*70+1280) *
                                timeDanmaku*100)  # 弹幕不是太密集时，控制同一条通道的弹幕不超过前一行
                dm_count += 1
                for i in range(limitLineAmount):
                    if vpos_next >= danmakuPassageway[i]:
                        passageway_index = i
                        danmakuPassageway[i] = vpos+timeDanmaku*100
                        break
                    elif danmakuPassageway[i] < vpos_next_min:
                        vpos_next_min = danmakuPassageway[i]
                        Passageway_min = i
                    elif i == limitLineAmount-1 and vpos_next < vpos_next_min:
                        passageway_index = Passageway_min
                        danmakuPassageway[Passageway_min] = vpos + timeDanmaku*100
                if dm_count > 11:
                    passageway_index = dm_count % 11
                # 计算弹幕位置
                sx = videoWidth
                sy = danmakuLineHeight*(passageway_index)
                ex = 0-len(text)*(danmakuSize+danmakuFontSpace)
                ey = danmakuLineHeight*(passageway_index)
                # 生成弹幕行并加入总弹幕
                if premium == '0':
                    eventD += 'Dialogue: 2,'+startTime+','+endTime + \
                        ',Danmaku,,0,0,0,,{\\an7\\alpha80\\move('+str(sx)+','+str(
                            sy)+','+str(ex)+','+str(ey)+')'+assColor+'}'+text+'\n'
                else:
                    eventD += 'Dialogue: 2,'+startTime+','+endTime + \
                        ',Danmaku,,0,0,0,,{\\an7\\move('+str(sx)+','+str(
                            sy)+','+str(ex)+','+str(ey)+')'+assColor+'}'+text+'\n'

    if include_aa:  # 处理AA弹幕
        for chat in chats:
            mail = chat.get('mail', '')
            sytles = mail.split(' ')
            if 'mincho' in sytles or 'gothic' in sytles:  # 判断AA弹幕行进行处理
                text = chat['text']
                vpos = int(chat['vpos'])
                startTime = sec2hms(round(vpos/100, 2))
                endTime = sec2hms(round(vpos/100, 2)+timeDanmaku)
                assColor = get_color(sytles)
                # 分成多行生成弹幕并整合成完整AA弹幕
                textAA = text.split('\n')
                for a in range(len(textAA)):
                    eventA += 'Dialogue: 1,'+startTime+','+endTime+',AA,,0,0,0,,{\\an4\\fsp-1\\move('+str(videoWidth)+','+str(
                        (AASize-1)*a+AAHighAdjust)+','+str(-fontSize*10)+',' + str((AASize-1)*a+AAHighAdjust)+')'+assColor+'}'+textAA[a]+'\n'

    # 定义ass文件头
    header = '[Script Info]\n\
; Script generated by Aegisub 3.2.2\n\
; http://www.aegisub.org/\n\
ScriptType: v4.00+\n\
PlayResX: 1280\n\
PlayResY: 720\n\
\n\
[V4+ Styles]\n\
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n\
Style: Default,微软雅黑,54,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,0,0,0,0\n\
Style: Alternate,微软雅黑,36,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,0,0,0,0\n\
Style: AA,黑体,'+str(AASize)+',&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,2,0,0,0,0\n\
Style: Office,'+fontName+','+str(OfficeSize)+',&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,1.5,0,2,0,0,10,0\n\
Style: Anketo,'+fontName+','+str(fontSize)+',&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,1.5,0,2,0,0,10,0\n\
Style: Danmaku,'+fontName+','+str(fontSize)+',&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,2,0,1,1.5,0,2,0,0,10,0\n\n\
[Events]\n\
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n'

    # 写入ass
    with open(os.path.splitext(xml_name)[0]+'.ass', 'w', encoding='utf-8-sig') as f:
        f.write(header)
        f.write(eventO)
        f.write(eventD)
        f.write(eventA)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        for i in range(len(sys.argv)-1):  # 输入文件
            xml_name = sys.argv[i+1]
            xml2ass(xml_name)
