#!/usr/bin/env python3
import os
import argparse

def create_gdb_script(max_steps=50, output_file="plot.md", main_only=True):
    """创建GDB Python脚本，生成简洁正确的Mermaid状态迁移图"""
    
    script = '''# GDB State Transition Visualization Script

# Set breakpoint at main and run
break main
run

python
import gdb
import json
import os

# Variables to store state information
states = []
transitions = []
current_state_id = 0
max_steps = %d
main_only = %s

def get_stack_state():
    """获取当前栈帧的状态"""
    state = {}
    
    try:
        frame = gdb.selected_frame()
        function_name = frame.function().name if frame.function() else "unknown"
        state["function"] = function_name
        
        # 获取当前行
        sal = frame.find_sal()
        state["line"] = sal.line
        
        # 尝试获取源代码
        try:
            with open(sal.symtab.filename, 'r') as f:
                lines = f.readlines()
                if 0 <= sal.line - 1 < len(lines):
                    state["code"] = lines[sal.line - 1].strip()
                else:
                    state["code"] = f"Line {sal.line}"
        except:
            state["code"] = f"Line {sal.line}"
        
        # 获取局部变量
        local_vars = {}
        block = frame.block()
        while block is not None:
            for symbol in block:
                if symbol.is_variable:
                    # 跳过内部变量
                    if symbol.name.startswith("__"):
                        continue
                    
                    try:
                        value = symbol.value(frame)
                        val_str = str(value)
                        
                        # 过滤掉"<optimized out>"和过长的值
                        if "<optimized out>" in val_str:
                            continue
                            
                        # 过滤掉可能的"垃圾值"（初始化前的大数）
                        if symbol.name in ["n", "steps"] and function_name == "main":
                            try:
                                int_val = int(val_str)
                                # 如果是非常大的数可能是未初始化的值
                                if int_val > 1000000:
                                    continue
                            except:
                                pass
                        
                        local_vars[symbol.name] = val_str
                    except:
                        pass
            
            block = block.superblock
        
        state["locals"] = local_vars
    except Exception as e:
        print(f"Error getting stack state: {str(e)}")
    
    return state

def record_state(transition_label=None):
    """记录当前程序状态"""
    global current_state_id, states, transitions
    
    # 获取当前状态
    state = get_stack_state()
    
    # 跳过main函数外的状态（如果开启了main_only选项）
    if main_only and state.get("function") != "main" and len(states) > 0:
        return None
    
    # 创建状态ID
    current_state_id += 1
    state_id = f"S{current_state_id}"
    state["id"] = state_id
    
    # 记录状态
    states.append(state)
    
    # 如果有前一个状态，记录转换
    if len(states) > 1 and transition_label:
        prev_state = states[-2]
        transitions.append({
            "from": prev_state["id"],
            "to": state_id,
            "label": transition_label
        })
    
    return state

def generate_plot_md():
    """生成Markdown文件，包含更简洁正确的Mermaid状态图"""
    with open("%s", "w") as f:
        # 标题
        f.write("# 程序状态迁移图\\n\\n")
        
        # Mermaid图
        f.write("```mermaid\\nstateDiagram-v2\\n")
        
        # 添加状态节点 - 只显示变量值
        for state in states:
            # 创建简洁的状态内容，只包含变量
            vars_content = []
            for var, value in state["locals"].items():
                vars_content.append(f"{var} = {value}")
            
            # 如果没有变量，则添加空状态
            if not vars_content:
                f.write(f"    {state['id']}: \\n")
            else:
                f.write(f"    {state['id']}: {'<br>'.join(vars_content)}\\n")
        
        # 添加初始转换
        if states:
            f.write(f"    [*] --> {states[0]['id']}\\n")
        
        # 添加状态转换 - 使用简洁的行号+代码格式
        for transition in transitions:
            from_state = next((s for s in states if s["id"] == transition["from"]), None)
            if from_state:
                line_num = from_state.get("line", "")
                code = from_state.get("code", "").replace("{", "").replace("}", "")
                # 限制长度
                if len(code) > 30:
                    code = code[:27] + "..."
                label = f"{line_num} - {code}"
                f.write(f"    {transition['from']} --> {transition['to']} : {label}\\n")
        
        f.write("```\\n\\n")
        
        # 添加ASCII图表部分
        f.write("## 状态详情\\n\\n")
        f.write("| 状态ID | 行号 | 代码 | 变量 |\\n")
        f.write("|--------|------|------|------|\\n")
        
        for state in states:
            vars_str = "<br>".join([f"{var}={val}" for var, val in state["locals"].items()])
            code = state.get("code", "").replace("|", "\\|")
            f.write(f"| {state['id']} | {state.get('line', '')} | `{code}` | {vars_str} |\\n")
        
        # 添加完整的状态转换表
        f.write("\\n## 完整执行路径\\n\\n")
        if states:
            f.write("```\\n")
            path = []
            for i, state in enumerate(states):
                line = f"{state['id']}: 行 {state.get('line', '')}"
                if i < len(states) - 1:
                    label = next((t["label"] for t in transitions if t["from"] == state["id"]), "")
                    line += f" -> {states[i+1]['id']}"
                path.append(line)
            f.write("\\n".join(path))
            f.write("\\n```\\n")

# 执行可视化
try:
    # 记录初始状态
    record_state()
    
    steps = 0
    while steps < max_steps:
        # 保存当前状态的代码和行号作为转换标签
        if states:
            current_state = states[-1]
            transition_label = current_state.get("code", "")
        else:
            transition_label = ""
        
        # 单步执行
        try:
            gdb.execute("step", to_string=True)
        except gdb.error as e:
            # 程序可能已结束
            break
        
        # 记录新状态
        new_state = record_state(transition_label)
        if new_state is None:
            # 如果状态被过滤（例如离开了main函数），则退出循环
            if main_only:
                break
            else:
                # 跳过此次迭代但继续循环
                continue
                
        steps += 1
        
        # 检查是否返回语句或函数结束
        if "return" in new_state.get("code", "") and new_state.get("function") == "main":
            # 再执行一次以捕获函数的最终状态
            try:
                gdb.execute("step", to_string=True)
                record_state("return " + transition_label)
            except:
                pass
            # 然后退出循环
            break
    
    # 生成图文件
    generate_plot_md()
    print(f"状态迁移图已保存到 %s")
except Exception as e:
    print(f"Error: {str(e)}")
end

quit
''' % (max_steps, "True" if main_only else "False", output_file, output_file)
    
    return script

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GDB Mermaid状态迁移图生成器")
    parser.add_argument("program", help="要分析的程序路径")
    parser.add_argument("-o", "--output", default="plot.md", help="输出文件路径")
    parser.add_argument("-s", "--steps", type=int, default=50, help="最大步数")
    parser.add_argument("-a", "--all", action="store_true", help="捕获所有函数状态，不仅限于main函数")
    
    args = parser.parse_args()
    
    # 创建GDB脚本
    script_content = create_gdb_script(args.steps, args.output, not args.all)
    script_path = "run_mermaid.gdb"
    
    with open(script_path, "w") as f:
        f.write(script_content)
    
    print(f"已创建GDB脚本: {script_path}")
    print(f"请使用以下命令执行:")
    print(f"gdb -x {script_path} {args.program}")