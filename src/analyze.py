#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import re
import sys
import json
import hashlib

from clang.cindex import Config
from multiprocessing import Pool

from symbol import *
from component import *
from crash_stack import *

from argument import parser
from statistics import cal_metrics
from output import format_print, stats_print
from persistence import dump_components, dump_symbols, load_symbols


def update_components(root):
    queue = []
    component_dict = dict()
    queue.append(root)
    while len(queue) > 0:
        prefix = queue.pop(0)
        cmk_path = os.path.join(prefix, "CMakeLists.txt")
        if os.path.exists(cmk_path):
            # get 2 types of component
            parents, children = find_component(cmk_path)
            # save parent component
            for com in parents:
                component_dict[prefix] = com
            # save child component
            child_dict = get_child(children, prefix)
            for child in child_dict:
                component_dict[child] = child_dict[child]
        for node in os.listdir(prefix):
            child = os.path.join(prefix, node)
            if os.path.isdir(child):
                queue.append(child)
    return component_dict


def update_symbols(root):
    symbol_dict = dict()
    # update symbols using multi-process
    paths = get_paths(root)
    pool = Pool(4)
    results = pool.map(find_symbol, paths)
    for res in filter(lambda x: x is not None, results):
        for k in res:
            if "::::" in k:
                k = k[:k.rindex("::::")] + \
                    "::(anonymous namespace)::" + \
                    k[k.rindex("::::")+4:]
            symbol_dict[k] = res[k]
    pool.close()
    pool.join()
    return symbol_dict


def pre_process(paths, mode):
    dumps = []
    # set crash stack pattern
    pattern = re.compile(r"[\n](\[CRASH_STACK\][\S\s]+)"
                         r"\[CRASH_REGISTERS\]", re.M)
    for path in paths:
        with open(path, "r") as fp:
            file_text = fp.read()
        stack = pattern.findall(file_text)
        if mode == "ast":
            trace = find_stack(stack[0])
            trace = to_component(trace)
        else:
            trace = find_stack(stack[0])
        dumps.append(trace)
    return dumps


def first_component(m_list):
    method, source = m_list
    # get component by source
    if "/" in source:
        path = args.source
        for layer in m_list[1].split("/"):
            path = os.path.join(path, layer)
        component = best_matched(path)
    # get component by symbol
    else:
        try:
            component = symbols[method]
        except KeyError:
            component = method
    return component


def find_key(text):
    key = ""
    component = ""
    bt_pattern = re.compile(r"[-][\n][ ]+\d+[:][ ](.+)"
                            r"([^-]+?Source[:][ ].+[:])*", re.M)
    bt_methods = bt_pattern.findall(text)
    for m_tuple in bt_methods:
        # convert tuple to list
        m = list(m_tuple)
        if m[1]:
            m[1] = m[1][m[1].index("Source: ")+8:-1]
        # remove address information
        if " + 0x" in m[0]:
            method = m[0][:m[0].rindex(" + 0x")]
        else:
            method = m[0]
        # remove parameter variable and return type
        if "(" in method:
            method = method[:method.index("(")]
        if " " in method:
            method = method[method.index(" ")+1:]
        m[0] = method
        # apply stop words
        if method not in stop_words and \
                "ltt" not in method and \
                "std" not in method and \
                "::" in method:
            # first component rule
            if component != "" and first_component(m) != component:
                break
            else:
                component = first_component(m)
                key += method + "\n"
    # compare by MD5
    md5 = hashlib.md5()
    message = key
    md5.update(message.encode("utf-8"))
    return md5.hexdigest()


def stats_process(paths, mode):
    compares = []
    for path in paths:
        with open(path, "r", encoding="ISO-8859-1") as fp:
            text = fp.read()
        if mode == "csi":
            compare = find_stack(text)
        else:
            compare = find_key(text)
        compares.append(compare)
    return compares


if __name__ == "__main__":
    symbols = load_symbols()
    stop_words_path = os.path.join(os.getcwd(), "json", "stop_words.json")
    try:
        with open(stop_words_path, "r") as f:
            stop_words = json.load(f)
    except FileNotFoundError:
        print("Can't find stop_words, please check!")
    # load libclang.so
    lib_path = r"C:\LLVM\bin" if sys.platform == "win32" else "/usr/local/lib"
    if not Config.loaded:
        Config.set_library_path(lib_path)
    # parse arguments
    args = parser.parse_args()
    if args.update:
        # create json directory if not exist
        json_path = os.path.join(os.getcwd(), "json")
        if not os.path.exists(json_path):
            os.makedirs(json_path)
        # get and save json
        com_dict = update_components(args.source)
        dump_components(com_dict)
        sym_dict = update_symbols(args.source)
        dump_symbols(sym_dict)
    # output similarity result
    data_sets_path = os.path.join(os.getcwd(), "json", "data_sets.json")
    try:
        with open(data_sets_path, "r") as f:
            data_sets = json.load(f)
    except FileNotFoundError:
        print("Can't find data_sets, please check!")
    # do data analysis
    if args.stats:
        precisions = []
        recalls = []
        f1s = []
        for single_set in data_sets:
            single_list = []
            p_list = []
            n_list = []
            # get positives hash code
            for p_paths in single_set[0]:
                p_texts = stats_process(p_paths, args.mode)
                p_list.append(p_texts)
            single_list.append(p_list)
            # get negatives hash code
            for n_paths in single_set[1]:
                n_texts = stats_process(n_paths, args.mode)
                n_list.append(n_texts)
            single_list.append(n_list)
            # calculate metrics
            precision, recall, f1 = cal_metrics(single_list)
            precisions.append(precision)
            recalls.append(recall)
            f1s.append(f1)
        stats_print([precisions, recalls, f1s])
    else:
        result = pre_process(args.dump, args.mode)
        format_print(result)
