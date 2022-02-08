import sys
import getopt
import pandas as pd
import re
import math


def trim_space(s):
    return s.replace(' ', '').replace(',', '').replace('，', '')

def remove_at(s, i):
    return s[0:i] + s[i+1:]

def main(argv):
    mode = '0'
    parameter = '3323'
    mode = '1'
    parameter = 'bai vvv vv vvv,012 000 00 000;bai tou er xin,012 010 10 001'
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
    all_idiom = pd.read_json('idiom.json')
    idiom_frequency = pd.read_csv('idiom_frequency.csv')
    all_idiom = all_idiom.merge(idiom_frequency, how='left', on='word')
    all_idiom['frequency'] = all_idiom['frequency'].fillna(1).astype(int)
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
            elif len(group) < 0:
                print('未找到匹配项')
                return
            else:
                break
        print_max_group(all_idiom, group, num)

def print_max_group(all_idiom, group, num):
    group['pinyin_c'] = group.apply(lambda x: (math.log(x['frequency'], 2)/16 + 1) * len(set(trim_space(x['pinyin_r']))), axis=1)
    list = group.nlargest(num, ['pinyin_c', 'frequency']).index.tolist()
    for i in list:
        print(all_idiom.loc[i])

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
        if len(group) == 1:
            break
    return group

if __name__ == '__main__':
    main(sys.argv[1:])
    
