#!/usr/bin/env python3
import subprocess
import re
import os
import argparse
import sys
import time
from graphviz import Digraph

class GDBStateVisualizer:
    def __init__(self, program_path, output_file="plot.md", debug=False):
        self.program_path = program_path
        self.output_file = output_file
        self.debug = debug
        self.states = []
        self.transitions = []
        self.current_state = {}
        self.user_defined_vars = set()
        self.state_counter = 0
        self.max_steps = 50  # 防止无限循环
        
    def log(self, message):
        """输出调试信息"""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)
            sys.stderr.flush()
    
    def run(self):
        """执行GDB调试并生成状态迁移图"""
        gdb_command = [
            "gdb", 
            "--quiet",
            "--batch",
            "-ex", "set pagination off",
            "-ex", "set print pretty on",
            "-ex", "break main",
            "-ex", "run",
            "-ex", "set logging file gdb_output.txt",
            "-ex", "set logging on",
            "-ex", "set logging redirect on",
            "-ex", "define hook-next",
            "-ex", "info locals",
            "-ex", "frame",
            "-ex", "end",
            "-ex", "define hook-step",
            "-ex", "info locals",
            "-ex", "frame",
            "-ex", "end",
            "-ex", "while 1",
            "-ex", "step",
            "-ex", "end",
            self.program_path
        ]
        
        self.log(f"启动GDB命令: {' '.join(gdb_command)}")
        
        try:
            # 先删除可能存在的输出文件
            if os.path.exists("gdb_output.txt"):
                os.remove("gdb_output.txt")
                
            # 运行GDB命令（带超时）
            process = subprocess.Popen(
                gdb_command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True
            )
            
            self.log("GDB进程已启动，等待完成或超时...")
            
            # 等待一定时间或直到程序结束
            timeout = 30  # 30秒超时
            start_time = time.time()
            
            while process.poll() is None and time.time() - start_time < timeout:
                time.sleep(0.1)
                
                # 检查输出文件是否存在且有内容
                if os.path.exists("gdb_output.txt") and os.path.getsize("gdb_output.txt") > 1000:
                    self.log("检测到足够的输出数据，终止GDB进程")
                    process.terminate()
                    break
            
            # 如果进程仍在运行，则强制终止
            if process.poll() is None:
                self.log("GDB进程超时，强制终止")
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
            
            # 检查是否有输出文件
            if not os.path.exists("gdb_output.txt"):
                self.log("没有生成输出文件")
                print("错误：GDB未能生成输出文件")
                return False
            
            # 分析GDB输出
            self.log("开始分析GDB输出")
            self._parse_gdb_output("gdb_output.txt")
            
            # 生成图
            if self.states:
                self._generate_graph()
                self.log(f"已生成状态迁移图，保存到 {self.output_file}")
                return True
            else:
                self.log("未能提取任何状态信息")
                print("错误：未能从GDB输出中提取状态信息")
                return False
                
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            print(f"错误: {str(e)}")
            return False
    
    def _parse_gdb_output(self, output_file):
        """从GDB输出文件中提取状态信息"""
        try:
            with open(output_file, 'r') as f:
                content = f.read()
            
            # 分割成块，每个块对应一次step执行
            blocks = content.split("(gdb) step")
            
            # 处理每个块
            current_line = None
            for i, block in enumerate(blocks):
                if i == 0:  # 跳过第一个块（初始状态）
                    continue
                    
                # 从块中提取局部变量信息
                var_values = {}
                locals_section = re.search(r'(gdb) info locals\n(.*?)(?=\(gdb\))', block, re.DOTALL)
                if locals_section:
                    locals_text = locals_section.group(2).strip()
                    lines = locals_text.split('\n')
                    for line in lines:
                        if '=' in line:
                            parts = line.split('=', 1)
                            var_name = parts[0].strip()
                            var_value = parts[1].strip()
                            var_values[var_name] = var_value
                            self.user_defined_vars.add(var_name)
                
                # 提取当前执行行
                frame_section = re.search(r'(gdb) frame\n(.*?)(?=\(gdb\))', block, re.DOTALL)
                if frame_section:
                    frame_text = frame_section.group(2).strip()
                    line_match = re.search(r'at .*:(\d+)', frame_text)
                    code_match = re.search(r'(\d+)\s+(.*?)$', frame_text, re.MULTILINE)
                    
                    if code_match:
                        current_line = code_match.group(2).strip()
                    elif line_match:
                        current_line = f"Line {line_match.group(1)}"
                    else:
                        current_line = f"Step {i}"
                
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
            
            self.log(f"从GDB输出中提取了 {len(self.states)} 个状态")
            return True
            
        except Exception as e:
            self.log(f"解析GDB输出时出错: {str(e)}")
            return False
    
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
    args = parser.parse_args()
    
    print(f"开始分析程序 {args.program}...")
    visualizer = GDBStateVisualizer(args.program, args.output, args.debug)
    success = visualizer.run()
    
    if success:
        print(f"状态迁移图已生成到 {args.output}")
    else:
        print("无法生成状态迁移图，请检查程序是否包含调试信息")
        print("提示: 编译时使用 -g 选项添加调试信息，例如: gcc -g program.c -o program")