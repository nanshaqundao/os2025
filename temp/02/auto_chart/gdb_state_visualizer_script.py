#!/usr/bin/env python3
import subprocess
import re
import os
import argparse
import sys
import time
from graphviz import Digraph

class GDBStateVisualizer:
    def __init__(self, program_path, output_file="plot.md", debug=False, max_steps=30):
        self.program_path = program_path
        self.output_file = output_file
        self.debug = debug
        self.max_steps = max_steps
        self.states = []
        self.transitions = []
        self.current_state = {}
        self.user_defined_vars = set()
        self.state_counter = 0
        
    def log(self, message):
        """输出调试信息"""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)
            sys.stderr.flush()
    
    def run(self):
        """执行GDB调试并生成状态迁移图"""
        try:
            # 创建GDB命令脚本
            gdb_script_path = self._create_gdb_script()
            self.log(f"已创建GDB脚本: {gdb_script_path}")
            
            # 执行GDB命令
            self.log(f"执行GDB: gdb -x {gdb_script_path} --quiet --batch {self.program_path}")
            process = subprocess.run(
                ["gdb", "-x", gdb_script_path, "--quiet", "--batch", self.program_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=60  # 设置超时时间
            )
            
            # 检查GDB输出
            output_files = ["gdb_vars.txt", "gdb_frames.txt", "gdb_cmds.txt"]
            missing_files = [f for f in output_files if not os.path.exists(f)]
            
            if missing_files:
                self.log(f"缺少输出文件: {missing_files}")
                print(f"错误: GDB未能生成所有必要的输出文件")
                return False
            
            # 分析GDB输出文件
            self.log("开始分析GDB输出文件")
            self._parse_gdb_outputs()
            
            # 清理临时文件
            for file in output_files + [gdb_script_path]:
                if os.path.exists(file):
                    os.remove(file)
            
            # 生成图
            if self.states:
                self._generate_graph()
                self.log(f"已生成状态迁移图，保存到 {self.output_file}")
                return True
            else:
                self.log("未能提取任何状态信息")
                print("错误：未能从GDB输出中提取状态信息")
                return False
                
        except subprocess.TimeoutExpired:
            self.log("GDB执行超时")
            print("错误: GDB执行超时")
            return False
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            print(f"错误: {str(e)}")
            return False
    
    def _create_gdb_script(self):
        """创建GDB命令脚本"""
        script_path = "gdb_commands.txt"
        
        with open(script_path, "w") as f:
            # 设置GDB环境
            f.write("set pagination off\n")
            f.write("set print pretty on\n")
            f.write("set confirm off\n")
            
            # 在main函数设置断点
            f.write("break main\n")
            f.write("run\n")
            
            # 创建输出文件
            f.write("set logging overwrite on\n")
            
            # 循环执行步进并输出状态
            for i in range(self.max_steps):
                # 记录变量状态
                f.write(f"set logging file gdb_vars.txt\n")
                f.write(f"set logging on\n")
                f.write(f"info locals\n")
                f.write(f"set logging off\n")
                
                # 记录当前帧信息
                f.write(f"set logging file gdb_frames.txt\n")
                f.write(f"set logging on\n")
                f.write(f"frame\n")
                f.write(f"set logging off\n")
                
                # 记录当前行的源代码
                f.write(f"set logging file gdb_cmds.txt\n")
                f.write(f"set logging on\n")
                f.write(f"list\n")
                f.write(f"set logging off\n")
                
                # 执行步进
                f.write("echo ---STEP_MARKER---\\n\n")
                f.write("step\n")
                
                # 检查是否到达main函数结尾
                f.write("if $_streq(\"main\", $func)\n")
                f.write("  if $pc >= $func + $funcsize\n")
                f.write("    echo END_OF_MAIN\\n\n")
                f.write("    quit\n")
                f.write("  end\n")
                f.write("else\n")
                f.write("  echo OUTSIDE_MAIN\\n\n")
                f.write("  quit\n")
                f.write("end\n")
                
                # 如果程序结束，退出循环
                f.write("if $_exitcode != -1\n")
                f.write("  echo PROGRAM_EXITED\\n\n")
                f.write("  quit\n")
                f.write("end\n")
            
            # 最后步数用完后退出
            f.write("quit\n")
        
        return script_path
    
    def _parse_gdb_outputs(self):
        """解析GDB输出文件以提取状态信息"""
        # 读取变量信息
        with open("gdb_vars.txt", "r") as f:
            vars_content = f.read()
        
        # 读取帧信息
        with open("gdb_frames.txt", "r") as f:
            frames_content = f.read()
        
        # 读取命令输出信息
        with open("gdb_cmds.txt", "r") as f:
            cmds_content = f.read()
        
        # 按步骤分割内容
        vars_blocks = vars_content.split("---STEP_MARKER---")
        frames_blocks = frames_content.split("---STEP_MARKER---")
        cmds_blocks = cmds_content.split("---STEP_MARKER---")
        
        # 确保所有块的数量一致
        min_blocks = min(len(vars_blocks), len(frames_blocks), len(cmds_blocks))
        self.log(f"解析到 {min_blocks} 个步骤")
        
        # 处理每个步骤
        for i in range(min_blocks):
            # 解析变量
            var_values = {}
            vars_text = vars_blocks[i]
            for line in vars_text.split('\n'):
                if '=' in line:
                    parts = line.split('=', 1)
                    var_name = parts[0].strip()
                    var_value = parts[1].strip()
                    var_values[var_name] = var_value
                    self.user_defined_vars.add(var_name)
            
            # 解析当前行代码
            current_line = None
            frames_text = frames_blocks[i]
            
            # 尝试从帧信息中提取代码行
            line_match = re.search(r'at .*:(\d+)', frames_text)
            code_match = re.search(r'(\d+)\s+(.*?)$', frames_text, re.MULTILINE)
            
            if code_match:
                current_line = code_match.group(2).strip()
            elif line_match:
                # 如果帧信息中没有代码，尝试从命令输出中获取
                line_num = line_match.group(1)
                cmds_text = cmds_blocks[i]
                for cmd_line in cmds_text.split('\n'):
                    if cmd_line.strip().startswith(line_num):
                        code_part = cmd_line.strip()[len(line_num):].strip()
                        if code_part:
                            current_line = code_part
                            break
                
                # 如果仍然没有找到代码行，使用行号
                if not current_line:
                    current_line = f"Line {line_num}"
            else:
                current_line = f"Step {i+1}"
            
            # 只有变量值发生变化时才记录新状态
            if var_values != self.current_state or not self.states:
                self.state_counter += 1
                state_id = f"S{self.state_counter}"
                
                # 记录前一个状态到当前状态的转换
                if self.states:
                    prev_state_id = self.states[-1][0]
                    self.transitions.append((prev_state_id, state_id, current_line))
                
                self.states.append((state_id, var_values.copy()))
                self.current_state = var_values.copy()
                
                self.log(f"记录状态 {state_id}: {current_line}")
        
        self.log(f"共提取 {len(self.states)} 个状态")
    
    def _generate_graph(self):
        """生成状态迁移图并输出到Markdown文件"""
        # 使用Graphviz创建图形
        dot = Digraph(comment='Program State Transitions')
        dot.attr('node', shape='box', style='rounded')
        
        # 添加状态节点
        for state_id, var_values in self.states:
            label = f"{state_id}\\n"
            label += "\\n".join([f"{var}={val}" for var, val in var_values.items()])
            dot.node(state_id, label=label)
        
        # 添加转换边
        for src, dst, label in self.transitions:
            if label:
                dot.edge(src, dst, label=label)
            else:
                dot.edge(src, dst)
        
        # 保存为SVG格式
        svg_file = "state_transitions.svg"
        dot.render(outfile=svg_file, format="svg", cleanup=True)
        
        # 创建Markdown文件
        with open(self.output_file, "w") as md_file:
            md_file.write("# 程序状态迁移图\n\n")
            md_file.write("下图展示了程序执行过程中的状态变化。每个节点代表一个程序状态，节点中显示了局部变量的值。\n")
            md_file.write("边上的文本表示执行的代码语句（已去除行首空格）。\n\n")
            md_file.write(f"![状态迁移图]({svg_file})\n\n")
            
            md_file.write("## 状态详情\n\n")
            for i, (state_id, var_values) in enumerate(self.states):
                md_file.write(f"### {state_id}\n\n")
                if var_values:
                    md_file.write("变量状态：\n\n")
                    for var, value in var_values.items():
                        md_file.write(f"- `{var}` = {value}\n")
                else:
                    md_file.write("无变量定义\n")
                md_file.write("\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GDB状态迁移可视化工具")
    parser.add_argument("program", help="要调试的程序路径")
    parser.add_argument("-o", "--output", default="plot.md", help="输出的Markdown文件路径")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式")
    parser.add_argument("-s", "--steps", type=int, default=30, help="最大步数")
    args = parser.parse_args()
    
    print(f"开始分析程序 {args.program}...")
    visualizer = GDBStateVisualizer(args.program, args.output, args.debug, args.steps)
    success = visualizer.run()
    
    if success:
        print(f"状态迁移图已生成到 {args.output}")
    else:
        print("无法生成状态迁移图，请检查程序是否包含调试信息")
        print("提示: 编译时使用 -g 选项添加调试信息，例如: gcc -g program.c -o program")