#!/usr/bin/env python3
import pexpect
import re
import json
import sys

PROGRAM_PATH = './gdb_sample_03'
OUTPUT_MD = 'plot.md'

def clean_ansi(text):
    return re.sub(r'\x1B\[\d+(;\d+)*m', '', text)

def sanitize_line(code_line):
    return code_line.strip().replace('"', '\\"')

def parse_locals(local_output):
    return {m.group(1): m.group(2) 
            for m in re.finditer(r'^([a-zA-Z_]\w*)\s*=\s*(.*)$', local_output, re.M)}

def generate_mermaid(steps):
    diagram = ["```mermaid", "graph TD"]
    for i, step in enumerate(steps):
        node = f'S{i}["{step["state"]}"]'
        if i > 0:
            diagram.append(f'    S{i-1} -->|"{steps[i-1]["statement"]}"| {node}')
        diagram.append(f'    {node}')
    diagram.append("```")
    return '\n'.join(diagram)

def debug_gdb_interaction(gdb):
    """交互式调试函数"""
    while True:
        try:
            gdb.expect(r'.+', timeout=0.5)
            print("DEBUG OUTPUT:", clean_ansi(gdb.before + gdb.after))
        except pexpect.TIMEOUT:
            return

def main():
    # 启动GDB并捕获完整输出
    gdb = pexpect.spawn(f'gdb --nx --quiet {PROGRAM_PATH}', 
                       timeout=20,
                       encoding='utf-8',
                       codec_errors='ignore')
    
    # 等待GDB初始化完成
    try:
        gdb.expect(r'\(gdb\) ')
    except pexpect.TIMEOUT:
        print("GDB启动失败，最后输出：")
        debug_gdb_interaction(gdb)
        sys.exit(1)

    # 配置调试环境
    gdb.sendline('set pagination off')
    gdb.sendline('set confirm off')
    gdb.sendline('break main')
    gdb.sendline('run')
    
    # 使用模糊匹配定位main函数
    try:
        gdb.expect(r'(Breakpoint.*main|in\s+main\b)', timeout=15)
    except Exception as e:
        print("Main函数定位失败，完整调试记录：")
        debug_gdb_interaction(gdb)
        sys.exit(2)

    steps = []
    max_steps = 100

    try:
        while len(steps) < max_steps:
            # 获取当前堆栈信息
            gdb.sendline('frame')
            gdb.expect(r'\(gdb\) ')
            frame = clean_ansi(gdb.before)
            
            # 提取源码行号
            line_num = re.search(r':(\d+)\s*$', frame)
            if not line_num:
                code_line = "UNKNOWN"
            else:
                gdb.sendline(f'list {line_num[1]},{line_num[1]}')
                gdb.expect(r'\(gdb\) ')
                code_line = re.search(r'\d+[ \t]+(.*)', clean_ansi(gdb.before))[1]

            # 获取局部变量
            gdb.sendline('info locals')
            gdb.expect(r'\(gdb\) ')
            locals_output = clean_ansi(gdb.before)
            
            # 记录状态
            steps.append({
                "statement": sanitize_line(code_line),
                "state": parse_locals(locals_output)
            })

            # 执行单步
            gdb.sendline('step')
            ret = gdb.expect([
                r'exited normally',
                r'received signal',
                r'Cannot step',
                r'\(gdb\) ',
                pexpect.TIMEOUT,
                pexpect.EOF
            ], timeout=10)
            
            if ret in (0, 1, 2):
                break

    except Exception as e:
        print(f"执行异常: {str(e)}")
        debug_gdb_interaction(gdb)

    # 生成报告
    if steps:
        with open(OUTPUT_MD, 'w') as f:
            f.write(f"# 执行轨迹\n\n")
            f.write(generate_mermaid(steps))
            f.write("\n\n## 详细记录\n```json\n")
            f.write(json.dumps(steps, indent=2))
            f.write("\n```")
        print(f"生成报告至 {OUTPUT_MD}")
    else:
        print("未捕获到有效执行步骤")

if __name__ == "__main__":
    main()