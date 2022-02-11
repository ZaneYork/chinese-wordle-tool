import getopt
import json
import math
import os
import re
import sys
import traceback

import pandas as pd
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS
from pypinyin import Style, lazy_pinyin, style

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
CORS(app)

TONE_TABLE = [
    set(['ā', 'ē', 'ī', 'ō', 'ū', 'ǖ']),
    set(['á', 'é', 'í', 'ó', 'ú', 'ǘ']),
    set(['ǎ', 'ě', 'ǐ', 'ǒ', 'ǔ', 'ǚ']),
    set(['à', 'è', 'ì', 'ò', 'ù', 'ǜ']),
]

def tone_only(pinyin, **kwargs):
    for i in range(4):
        if len(set(pinyin).intersection(TONE_TABLE[i])) > 0:
            return str(i + 1)
    return '5'

style.register('TONE_ONLY', tone_only)

def trim_space(s):
    return s.replace(' ', '').replace(',', '').replace('，', '')

def remove_at(s, i):
    return s[0:i] + s[i+1:]

def compute_pinyin(s, style=None):
    if style is None:
        return ' '.join(lazy_pinyin(s))
    else:
        return ' '.join(lazy_pinyin(s, style=style))

all_idiom = None

def init():
    global all_idiom
    if os.path.exists("all_idiom.csv"):
        all_idiom = pd.read_csv('all_idiom.csv')
    else:
        all_idiom = pd.read_json('idiom.json')
        idiom_frequency = pd.read_csv('idiom_frequency.csv')
        all_idiom = all_idiom.merge(idiom_frequency, how='outer', on='word')
        all_idiom['frequency'] = all_idiom['frequency'].fillna(1).astype(int)
        all_idiom['pinyin_r'] = all_idiom.apply(lambda x: compute_pinyin(x['word']) if x['pinyin_r'] else x['pinyin_r'], axis=1)
        all_idiom['pinyin_rt'] = all_idiom.apply(lambda x: int(''.join(map(lambda y: str(len(y)), re.split('[ ,，]',x['pinyin_r'])))), axis=1)
        all_idiom['pinyin'] = all_idiom.apply(lambda x: compute_pinyin(x['word'], style=Style.TONE) if x['pinyin'] else x['pinyin'], axis=1)
        all_idiom['pinyin_tone'] = all_idiom.apply(lambda x: ''.join(lazy_pinyin(x['word'], style="TONE_ONLY")), axis=1)
        all_idiom['pinyin_initials' ] = all_idiom.apply(lambda x: ','.join(list(lazy_pinyin(x['word'], style=Style.INITIALS, strict=False))), axis=1)
        all_idiom['pinyin_finals'] = all_idiom.apply(lambda x: ','.join(list(lazy_pinyin(x['word'], style=Style.FINALS, strict=False))), axis=1)
        all_idiom.to_csv("all_idiom.csv")

def fetch_next_input(parameter):
    parameter_rst = parameter.split(';', 1)
    if len(parameter_rst) > 1:
        parameter_rst = parameter_rst[1]
    else:
        parameter_rst = ''
    parameter = parameter.split(';')[0]
    return parameter,parameter_rst

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
            group = group[~group[key0].str.contains(target, regex=False, case=True, na=False)]
        elif hit == '1':
            group = group[(group[key2] != target) & (group[key1].str.contains(target, regex=False, case=True, na=False))]
            includes.add(target)
        elif hit == '2':
            group = group[group[key2] == target]
        if len(group) <= 1:
            break
    return group

def filter_with_target_field(group, field_name, values, value_hits):
    includes_value = set()
    for i in range(4):
        if value_hits[i] == '2':
            includes_value.add(values[i])
    for i in range(4):
        if value_hits[i] == '0' and values[i] not in includes_value:
            group = group[~group[field_name].str.contains(values[i], regex=False, case=True, na=False)]
        elif value_hits[i] == '1':
            group = group[(group[field_name].str[i] != values[i]) & group[field_name].str.contains(values[i], regex=False, case=True, na=False)]
            includes_value.add(values[i])
        elif value_hits[i] == '2':
            group = group[group[field_name].str[i] == values[i]]
        if len(group) <= 1:
            break
    return group

def filter_group_model2(parameter, group, hits, tones, tone_hits, word_hits):
    group = filter_with_target_field(group, 'pinyin_tone', tones, tone_hits)
    if len(group) <= 1:
        return group
    group = filter_with_target_field(group, 'word', parameter, word_hits)
    if len(group) <= 1:
        return group
    hits = hits.split()
    for i in range(4):
        target = parameter[i]
        targets = list()
        targets.append(lazy_pinyin(target, style=Style.INITIALS, strict=False)[0])
        targets.append(lazy_pinyin(target, style=Style.FINALS, strict=False)[0])
        pinyin_hit = hits[i]
        for j,name in enumerate(['initials', 'finals']):
            key = 'pinyin_%s' % name
            if pinyin_hit[j] == '0':
                group = group[group[key].str.count('(^|[,])%s([,]|$)' + targets[j]) == 0]
            elif pinyin_hit[j] == '1':
                group = group[(group[key].str.count('(^|[,])%s([,]|$)' % targets[j]) > 0) & (group[key].str.count(('^(\w*,){%d}%s([,]|$)' % (i, targets[j]))) == 0)]
            elif pinyin_hit[j] == '2':
                group = group[group[key].str.count(('^(\w*,){%d}%s([,]|$)' % (i, targets[j]))) > 0]
            if len(group) <= 1:
                return group
    return group

def filter_logic(mode, parameter):
    global all_idiom
    if mode == '0':
        groups = all_idiom.groupby(by='pinyin_rt')
        group = groups.get_group(int(parameter)).copy()
        return all_idiom, group
    elif mode == '1':
        parameter, parameter_rst = fetch_next_input(parameter)

        hits = parameter.split(',')[1]
        parameter = trim_space(parameter.split(',')[0])
 
        count = ''.join([str(len(x)) for x in hits.split()])
        groups = all_idiom.groupby(by='pinyin_rt')
        group = groups.get_group(int(count)).copy()

        while(True):
            group = filter_group_mode1(parameter, group, hits)
            if(len(group) > 1 and len(parameter_rst) > 0):
                parameter, parameter_rst = fetch_next_input(parameter)

                hits = parameter.split(',')[1]
                parameter = trim_space(parameter.split(',')[0])
            elif len(group) <= 0:
                break
            else:
                break
        return all_idiom, group
    elif mode == '2':
        four_idiom = all_idiom[all_idiom['word'].str.len() == 4]
        group = four_idiom[four_idiom['pinyin_tone'].str.startswith(parameter)].copy()
        return four_idiom, group
    elif mode == '3':
        four_idiom = all_idiom[all_idiom['word'].str.len() == 4]

        parameter, parameter_rst = fetch_next_input(parameter)

        hits = parameter.split(',')[1]
        parameter = parameter.split(',')[0]
        tones = ''.join(lazy_pinyin(parameter, style="TONE_ONLY"))
        tone_hits=hits[-4:]
        word_hits=hits[-9:-5]
        hits=hits[:-10]

        group = four_idiom.copy()
        while(True):
            group = filter_group_model2(parameter, group, hits, tones, tone_hits, word_hits)
            if(len(group) > 1 and len(parameter_rst) > 0):
                parameter, parameter_rst = fetch_next_input(parameter)

                hits = parameter.split(',')[1]
                parameter = parameter.split(',')[0]
                tones = ''.join(lazy_pinyin(parameter, style="TONE_ONLY"))
                tone_hits=hits[-4:]
                word_hits=hits[-9:-5]
                hits=hits[:-10]
            elif len(group) <= 0:
                break
            else:
                break
        return four_idiom, group
    elif mode == '4':
        four_idiom = all_idiom[all_idiom['word'].str.len() == 4]
        group = four_idiom[four_idiom['word'].str.count(parameter) > 0].copy()
        return four_idiom, group
    elif mode == '5':
        four_idiom = all_idiom[all_idiom['word'].str.len() == 4]
        group = four_idiom[four_idiom['pinyin_r'].str.count(parameter) > 0].copy()
        return four_idiom, group
    return None, None

def print_max_group(all_idiom, group, num):
    for item in get_max_group(all_idiom, group, num):
        print(item)

def get_max_group(all_idiom, group, num):
    result = list()
    if(len(group) == 0):
        return result
    group['pinyin_c'] = group.apply(lambda x: (math.log(x['frequency'], 2)/16 + 1) * len(set(trim_space(x['pinyin_r']))), axis=1)
    ret_list = group.nlargest(num, ['pinyin_c', 'frequency']).index.tolist()
    for i in ret_list:
        result.append(json.loads(all_idiom.loc[i].to_json(orient = 'index',force_ascii=False)))
    return result

@app.route('/predict', methods=['GET'])
def predict():
    try:
        mode = request.args.get('mode')
        parameter = request.args.get('parameter')
        if len(trim_space(parameter)) == 0:
            return jsonify({'status': 1, 'message': '请输入参数', 'result': []})
        all_idiom, group = filter_logic(mode, parameter)
        result = get_max_group(all_idiom, group, 6)
        return jsonify({'status': 0, 'message': 'success', 'result': result})
    except:
        traceback.print_exc()
        return jsonify({'status': 2, 'message': '执行出错', 'result': []})


@app.route('/', methods=['GET'])
def index():
    return render_template('index.html')

def main(argv):
    # mode = '0'
    # parameter = '3323'
    # mode = '1'
    # parameter = 'bai vvv vv vvv,012 000 00 000;bai tou er xin,012 010 10 001'
    # mode = '2'
    # parameter = '2134'
    mode = '3'
    parameter = '行之有效,00 11 10 00 0100 1101;各执一词,00 11 12 22 0010 1022'
    num = 6
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
    all_idiom, group = filter_logic(mode, parameter)
    if all_idiom is not None and len(group) > 0:
        print_max_group(all_idiom, group, num)
    else:
        print('未找到匹配项')

if __name__ == '__main__':
    current_work_dir = os.path.dirname(__file__)
    os.chdir(current_work_dir)
    init()
    # main(sys.argv[1:])
    app.run(debug=True, host="0.0.0.0")
