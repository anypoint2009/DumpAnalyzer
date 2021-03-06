import re


def find_backtrace(text):
    bt = ""
    # extract frame and source
    bt_pattern = re.compile(r"-\n[ ]*(\d+:[ ].+)"
                            r"([^-]+Source:[ ].+:)*", re.M)
    bt_methods = bt_pattern.findall(text)
    for m_tuple in bt_methods:
        m = list(m_tuple)
        # remove offset if exists
        if " + 0x" in m[0]:
            m[0] = m[0][:m[0].index(" + 0x")]
        # merge into a line
        if m[1]:
            m[1] = m[1][m[1].index("Source: ") + 8:-1]
            bt += m[0] + " at " + m[1] + "\n"
        else:
            bt += m[0] + "\n"
    return bt


def find_exception(text):
    ex = ""
    # extract headers
    headers = []
    header_pattern = re.compile(r"(^exception.+no[.].+)\n"
                                r"([\s\S]+?exception[ ]throw[ ]location:)", re.M)
    for h in header_pattern.findall(text):
        header = "\n" + h[0] + "\n" + h[1].strip() + "\n"
        headers.append(header)
    # extract bodies
    bodies = []
    body_pattern = re.compile(r"(\d+:[ ].+[+].+[ ]at[ ].+):", re.M)
    # handle exception without source
    body_pattern_sp = re.compile(r"(\d+:[ ].+[+].+)[ ]", re.M)
    whole = body_pattern.findall(text)
    if not whole:
        whole = body_pattern_sp.findall(text)
    # get break points
    points = []
    for i, b in enumerate(whole):
        if b[:b.index(":")] == whole[0][0]:
            points.append(i)
    points.append(len(whole))
    # processing body
    for i in range(len(points) - 1):
        body = ""
        for line in whole[points[i]:points[i + 1]]:
            # remove offset if exists
            offset_pattern = re.compile(r"([ ]const)*[+]*0x\w+([ ]in[ ])*")
            body += re.sub(offset_pattern, "", line) + "\n"
        bodies.append(body)
    # merge header and body
    for h, b in zip(headers, bodies):
        ex += h + b
    return ex


def find_stack(path):
    res = ""
    with open(path, "r", encoding="ISO-8859-1") as fp:
        file_text = fp.read()
    # set stack pattern
    stack_pattern = re.compile(r"\n(\[CRASH_STACK\][\s\S]+)"
                               r"\[CRASH_REGISTERS\]", re.M)
    content = stack_pattern.findall(file_text)
    if not content:
        return ""
    else:
        stack = content[0]
    # extract backtrace
    bt = find_backtrace(stack)
    res += bt
    # merge exception if exists
    ex_header = "-> Pending exceptions (possible root cause) <-"
    if ex_header in stack:
        ex = find_exception(stack)
        res += ex
    return res
