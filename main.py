import sys, os
import getopt
import pandas as pd
import re
import math
from pypinyin import pinyin, lazy_pinyin, Style

def trim_space(s):
    return s.replace(' ', '').replace(',', '').replace('，', '')

def remove_at(s, i):
    return s[0:i] + s[i+1:]

def compute_pinyin(s, style=None):
    if style is None:
        return ' '.join(lazy_pinyin(s))
    else:
        return ' '.join(lazy_pinyin(s, style=style))

TONE_TABLE = [
    set(['ā', 'ē', 'ī', 'ō', 'ū', 'ǖ']),
    set(['á', 'é', 'í', 'ó', 'ú', 'ǘ']),
    set(['ǎ', 'ě', 'ǐ', 'ǒ', 'ǔ', 'ǚ']),
    set(['à', 'è', 'ì', 'ò', 'ù', 'ǜ']),
]

def get_tone(s):
    result = list()
    for p in s.split(' '):
        hit = False
        for i in range(4):
            if len(set(p).intersection(TONE_TABLE[i])) > 0:
                result.append(str(i + 1))
                hit = True
                break
        if not hit:
            result.append('5')
    return ''.join(result)

def main(argv):
    mode = '0'
    parameter = '3323'
    mode = '1'
    parameter = 'bai vvv vv vvv,012 000 00 000;bai tou er xin,012 010 10 001'
    mode = '2'
    parameter = '1234'
#    mode = '3'
#    parameter = '风调雨顺 1234,00 00 00 20 1111;无所不包 2341,00 00 00 00 2121;得心应手 2143,01 00 00 20 2222'
    num = 3
    try:
        opts, args = getopt.getopt(argv, "hm:p:n:", ["mode=", "parameter=", "num="])
    except getopt.GetoptError:
        print('test.py -m <mode> -p <parameter> -n <num>')
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print('test.py -i <mode> -o <parameter>')
            sys.exit()
        elif opt in ("-m", "--mode"):
            mode = arg
        elif opt in ("-p", "--parameter"):
            parameter = arg
        elif opt in ("-n", "--num"):
            num = int(arg)
    if os.path.exists("all_idiom.csv"):
        all_idiom = pd.read_csv('all_idiom.csv')
    else:
        all_idiom = pd.read_json('idiom.json')
        idiom_frequency = pd.read_csv('idiom_frequency.csv')
        all_idiom = all_idiom.merge(idiom_frequency, how='outer', on='word')
        all_idiom['frequency'] = all_idiom['frequency'].fillna(1).astype(int)
        all_idiom['pinyin_r'] = all_idiom.apply(lambda x: compute_pinyin(x['word']) if x['pinyin_r'] else x['pinyin_r'], axis=1)
        all_idiom['pinyin'] = all_idiom.apply(lambda x: compute_pinyin(x['word'], style=Style.TONE) if x['pinyin'] else x['pinyin'], axis=1)
        all_idiom.to_csv("all_idiom.csv")
    if mode == '0':
        all_idiom['pinyin_rt'] = all_idiom.apply(lambda x: ''.join(map(lambda y: str(len(y)), re.split('[ ,，]',x['pinyin_r']))), axis=1)
        groups = all_idiom.groupby(by='pinyin_rt')
        group = groups.get_group(parameter).copy()
        print_max_group(all_idiom, group, num)
    elif mode == '1':
        parameter_rst = parameter.split(';', 1)
        if len(parameter_rst) > 1:
            parameter_rst = parameter_rst[1]
        else:
            parameter_rst = ''
        parameter = parameter.split(';')[0]

        hits = parameter.split(',')[1]
        parameter = trim_space(parameter.split(',')[0])
 
        count = ''.join([str(len(x)) for x in hits.split()])
        all_idiom['pinyin_rt'] = all_idiom.apply(lambda x: ''.join(map(lambda y: str(len(y)), re.split('[ ,，]',x['pinyin_r']))), axis=1)
        groups = all_idiom.groupby(by='pinyin_rt')
        group = groups.get_group(count).copy()

        while(True):
            group = filter_group_mode1(parameter, group, hits)
            if(len(group) > 1 and len(parameter_rst) > 0):
                parameter = parameter_rst.split(';')[0]
                parameter_rst = parameter_rst.split(';', 1)
                if len(parameter_rst) > 1:
                    parameter_rst = parameter_rst[1]
                else:
                    parameter_rst = ''
                hits = parameter.split(',')[1]
                parameter = trim_space(parameter.split(',')[0])
            elif len(group) <= 0:
                print('未找到匹配项')
                return
            else:
                break
        print_max_group(all_idiom, group, num)
    elif mode == '2':
        all_idiom = all_idiom[all_idiom['word'].str.len() == 4]
        all_idiom['pinyin_tone'] = all_idiom.apply(lambda x: get_tone(x['pinyin']), axis=1)
        group = all_idiom[all_idiom['pinyin_tone'].str.startswith(parameter)].copy()
        print_max_group(all_idiom, group, num)
    elif mode == '3':
        all_idiom = all_idiom[all_idiom['word'].str.len() == 4]
        parameter_rst = parameter.split(';', 1)
        if len(parameter_rst) > 1:
            parameter_rst = parameter_rst[1]
        else:
            parameter_rst = ''
        parameter = parameter.split(';')[0]

        hits = parameter.split(',')[1]
        parameter = parameter.split(',')[0]
        tones = parameter[-4:]
        tone_hits=hits[-4:]
        parameter = parameter[:-5]
        hits=hits[:-5]

        all_idiom['pinyin_tone'] = all_idiom.apply(lambda x: get_tone(x['pinyin']), axis=1)
        group = all_idiom.copy()
        while(True):
            group = filter_group_model2(parameter, group, hits, tones, tone_hits)
            if(len(group) > 1 and len(parameter_rst) > 0):
                parameter = parameter_rst.split(';')[0]
                parameter_rst = parameter_rst.split(';', 1)
                if len(parameter_rst) > 1:
                    parameter_rst = parameter_rst[1]
                else:
                    parameter_rst = ''

                hits = parameter.split(',')[1]
                parameter = parameter.split(',')[0]
                tones = parameter[-4:]
                tone_hits=hits[-4:]
                parameter = parameter[:-5]
                hits=hits[:-5]
            elif len(group) <= 0:
                print('未找到匹配项')
                return
            else:
                break
        print_max_group(all_idiom, group, num)

def filter_group_model2(parameter, group, hits, tones, tone_hits):
    for i in range(4):
        if tone_hits[i] == '0':
            group = group[~group['pinyin_tone'].str.contains(tones[i])]
        elif tone_hits[i] == '1':
            group = group[(group['pinyin_tone'].str[i] != tones[i]) & group['pinyin_tone'].str.contains(tones[i])]
        elif tone_hits[i] == '2':
            group = group[group['pinyin_tone'].str[i] == tones[i]]
        if len(group) <= 1:
            break
    group['pinyin_0' ] = group.apply(lambda x: ','.join(list(lazy_pinyin(x['word'], style=Style.INITIALS, strict=False))), axis=1)
    group['pinyin_1'] = group.apply(lambda x: ','.join(list(lazy_pinyin(x['word'], style=Style.FINALS, strict=False))), axis=1)
    hits = hits.split()
    for i in range(4):
        target = parameter[i]
        targets = list()
        targets.append(lazy_pinyin(target, style=Style.INITIALS, strict=False)[0])
        targets.append(lazy_pinyin(target, style=Style.FINALS, strict=False)[0])
        pinyin_hit = hits[i]
        outer_break = False
        for j in range(2):
            if pinyin_hit[j] == '0':
                group = group[group['pinyin_%d' % j].str.count('(^|[,])%s([,]|$)' + targets[j]) == 0]
            elif pinyin_hit[j] == '1':
                group = group[(group['pinyin_%d' % j].str.count('(^|[,])%s([,]|$)' % targets[j]) > 0) & (group['pinyin_%d' % j].str.count(('^(\w*,){%d}%s([,]|$)' % (i, targets[j]))) == 0)]
            elif pinyin_hit[j] == '2':
                group = group[group['pinyin_%d' % j].str.count(('^(\w*,){%d}%s([,]|$)' % (i, targets[j]))) > 0]
            if len(group) <= 1:
                outer_break = True
                break
        if outer_break:
            break
    return group

def print_max_group(all_idiom, group, num):
    group['pinyin_c'] = group.apply(lambda x: (math.log(x['frequency'], 2)/16 + 1) * len(set(trim_space(x['pinyin_r']))), axis=1)
    list = group.nlargest(num, ['pinyin_c', 'frequency']).index.tolist()
    for i in list:
        print(all_idiom.loc[i])

'''
parameter: xxx xx xx xxx
hits: 010 02 22 001
'''
def filter_group_mode1(parameter, group, hits):
    for i in range(len(parameter)):
        key0 = 'pinyin0_%d' % i
        key1 = 'pinyin1_%d' % i
        key2 = 'pinyin2_%d' % i
        group[key0] = group.apply(lambda x: ''.join(set(trim_space(x['pinyin_r']))), axis=1)
        group[key1] = group.apply(lambda x: ''.join(set(remove_at(trim_space(x['pinyin_r']), i))), axis=1)
        group[key2] = group.apply(lambda x: trim_space(x['pinyin_r'])[i], axis=1)
    includes = set()
    for i, hit in enumerate(list(trim_space(hits))):
        if hit == '2':
            includes.add(parameter[i])
    for i, hit in enumerate(list(trim_space(hits))):
        key0 = 'pinyin0_%d' % i
        key1 = 'pinyin1_%d' % i
        key2 = 'pinyin2_%d' % i
        target = parameter[i]
        if hit == '0' and target not in includes:
            group = group[~group[key0].str.contains(target)]
        elif hit == '1':
            group = group[(group[key2] != target) & (group[key1].str.contains(target))]
            includes.add(target)
        elif hit == '2':
            group = group[group[key2] == target]
        if len(group) <= 1:
            break
    return group

if __name__ == '__main__':
    current_work_dir = os.path.dirname(__file__)
    os.chdir(current_work_dir)
    main(sys.argv[1:])
