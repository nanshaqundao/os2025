#!/usr/bin/env python3
import os
import re
import sys
import time
import argparse
import subprocess

class GDBStateVisualizer:
    def __init__(self, program_path, output_file="plot.md", debug=False, max_steps=20):
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
            # 检查程序是否存在
            if not os.path.exists(self.program_path):
                print(f"错误: 找不到程序 {self.program_path}")
                return False
                
            # 直接获取程序的状态信息
            self.log(f"开始获取程序状态...")
            self._get_program_states()
            
            # 生成状态迁移图
            if self.states:
                self._generate_text_output()
                self.log(f"已生成状态迁移图文本描述，保存到 {self.output_file}")
                return True
            else:
                self.log("未能提取任何状态信息")
                print("错误：未能从GDB输出中提取状态信息")
                return False
                
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            print(f"错误: {str(e)}")
            return False

    def _get_program_states(self):
        """获取程序在执行过程中的状态"""
        # 创建一个简单的GDB批处理脚本
        script_content = """
break main
run
"""
        
        # 对于每一步，添加步进和状态输出命令
        for i in range(self.max_steps):
            script_content += f"""
# 步骤 {i+1}
p "------------STEP_{i+1}--------------"
info locals
p "------------LINE--------------"
frame
p "------------NEXT--------------"
step
"""
        
        # 写入脚本文件
        script_path = "simple_gdb_script.txt"
        with open(script_path, "w") as f:
            f.write(script_content)
            
        self.log(f"已创建简化GDB脚本: {script_path}")
        
        # 执行GDB并捕获输出
        try:
            self.log(f"执行GDB命令: gdb -x {script_path} --quiet --batch {self.program_path}")
            process = subprocess.run(
                ["gdb", "-x", script_path, "--quiet", "--batch", self.program_path],
                capture_output=True,
                text=True,
                timeout=20  # 20秒超时
            )
            
            output = process.stdout
            self.log(f"GDB输出长度: {len(output)} 字符")
            
            if len(output) < 10:  # 如果输出太少，可能有问题
                self.log(f"GDB输出太少: '{output}'")
                self.log(f"错误输出: '{process.stderr}'")
                return
                
            # 删除临时文件
            os.remove(script_path)
            
            # 解析GDB输出
            self._parse_gdb_output(output)
            
        except subprocess.TimeoutExpired:
            self.log("GDB执行超时，尝试获取部分状态")
            return
    
    def _parse_gdb_output(self, output):
        """解析GDB输出以提取程序状态"""
        # 按步骤划分输出
        step_blocks = re.split(r'"\-+STEP_\d+\-+\"', output)
        
        if len(step_blocks) <= 1:
            self.log("未找到步骤标记，无法解析输出")
            return
            
        self.log(f"识别到 {len(step_blocks)-1} 个步骤块")
        
        # 第一个块包含启动信息，从第二个块开始解析
        for i, block in enumerate(step_blocks[1:], 1):
            try:
                # 分割出各个部分
                parts = re.split(r'"\-+([A-Z]+)\-+\"', block)
                if len(parts) < 3:
                    continue
                
                # 解析局部变量
                locals_text = parts[0].strip()
                var_values = {}
                for line in locals_text.split('\n'):
                    if '=' in line:
                        # 跳过 $ 开头的GDB内部变量
                        if line.strip().startswith('$'):
                            continue
                            
                        parts = line.split('=', 1)
                        if len(parts) == 2:
                            var_name = parts[0].strip()
                            var_value = parts[1].strip()
                            # 过滤掉不是用户定义的变量
                            if not var_name.startswith('$') and var_name != "":
                                var_values[var_name] = var_value
                                self.user_defined_vars.add(var_name)
                
                # 解析当前行代码
                line_part_idx = parts.index("LINE") if "LINE" in parts else -1
                current_line = "Step " + str(i)
                
                if line_part_idx != -1 and line_part_idx + 1 < len(parts):
                    frame_text = parts[line_part_idx + 1].strip()
                    
                    # 尝试获取当前行的代码
                    code_match = re.search(r'at .*:(\d+)\s*\n[^0-9]*(\d+)\s+(.*?)(?:\n|$)', frame_text, re.DOTALL)
                    if code_match:
                        current_line = code_match.group(3).strip()
                    else:
                        # 尝试至少获取行号
                        line_match = re.search(r'at .*:(\d+)', frame_text)
                        if line_match:
                            current_line = f"Line {line_match.group(1)}"
                
                # 只有变量值发生变化，或者是第一个状态时才记录
                if var_values != self.current_state or not self.states:
                    self.state_counter += 1
                    state_id = f"S{self.state_counter}"
                    
                    self.log(f"记录状态 {state_id}: {current_line}")
                    self.log(f"变量: {var_values}")
                    
                    # 记录前一个状态到当前状态的转换
                    if self.states:
                        prev_state_id = self.states[-1][0]
                        self.transitions.append((prev_state_id, state_id, current_line))
                    
                    self.states.append((state_id, var_values.copy()))
                    self.current_state = var_values.copy()
                    
            except Exception as e:
                self.log(f"解析步骤 {i} 时出错: {str(e)}")
        
        self.log(f"成功提取 {len(self.states)} 个状态")
    
    def _generate_ascii_graph(self):
        """生成ASCII格式的状态迁移图"""
        result = []
        
        # 为每个状态生成文本描述
        for i, (state_id, var_values) in enumerate(self.states):
            # 添加状态标题
            result.append(f"[{state_id}]")
            
            # 添加变量值
            var_lines = [f"  {var}={val}" for var, val in var_values.items()]
            if var_lines:
                result.extend(var_lines)
            else:
                result.append("  (无变量)")
            
            # 添加转换（除了最后一个状态）
            if i < len(self.states) - 1:
                transition = self.transitions[i]
                result.append(f"  |")
                result.append(f"  | {transition[2]}")  # 转换标签
                result.append(f"  v")
            
        return "\n".join(result)
    
    def _generate_text_output(self):
        """生成状态迁移图的文本描述并输出到Markdown文件"""
        with open(self.output_file, "w") as md_file:
            # 标题和说明
            md_file.write("# 程序状态迁移图\n\n")
            md_file.write("下面展示了程序执行过程中的状态变化。每个节点代表一个程序状态，节点中显示了局部变量的值。\n")
            md_file.write("箭头上的文本表示执行的代码语句（已去除行首空格）。\n\n")
            
            # 生成ASCII图形
            md_file.write("## 状态迁移ASCII图\n\n")
            md_file.write("```\n")
            md_file.write(self._generate_ascii_graph())
            md_file.write("\n```\n\n")
            
            # 生成表格形式
            if self.transitions:
                md_file.write("## 状态转换表\n\n")
                md_file.write("| 从状态 | 执行语句 | 到状态 |\n")
                md_file.write("|--------|----------|--------|\n")
                
                for src, dst, label in self.transitions:
                    md_file.write(f"| {src} | `{label}` | {dst} |\n")
            
            # 状态详情
            md_file.write("\n## 状态详情\n\n")
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
    parser.add_argument("-s", "--steps", type=int, default=20, help="最大步数")
    args = parser.parse_args()
    
    print(f"开始分析程序 {args.program}...")
    visualizer = GDBStateVisualizer(args.program, args.output, args.debug, args.steps)
    success = visualizer.run()
    
    if success:
        print(f"状态迁移图已生成到 {args.output}")
    else:
        print("无法生成状态迁移图，请检查程序是否包含调试信息")
        print("提示: 编译时使用 -g 选项添加调试信息，例如: gcc -g program.c -o program")