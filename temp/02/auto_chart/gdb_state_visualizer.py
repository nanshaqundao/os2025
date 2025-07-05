#!/usr/bin/env python3
import subprocess
import re
import os
import argparse
import sys
import time
import signal
import select
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
        self.log(f"启动GDB调试 {self.program_path}")
        
        # 使用PTY创建伪终端，这样GDB输出会更可靠
        try:
            import pty
            master, slave = pty.openpty()
            self.gdb_process = subprocess.Popen(
                ["gdb", "--quiet", "--nx", self.program_path],
                stdin=subprocess.PIPE,
                stdout=slave,
                stderr=slave,
                universal_newlines=True,
                bufsize=1,  # 行缓冲
                close_fds=True
            )
            os.close(slave)
            self.gdb_fd = master
            
            # 等待GDB启动完成
            self.log("等待GDB启动...")
            self._read_until_prompt()
            
            # 设置GDB配置
            self.log("设置GDB配置")
            self._send_command("set pagination off")
            self._send_command("set print pretty on")
            
            # 在main函数开始处设置断点并运行
            self.log("在main函数设置断点")
            self._send_command("break main")
            
            self.log("运行程序")
            output = self._send_command("run")
            
            if "Breakpoint 1" not in output and "main" not in output:
                self.log("尝试start命令")
                self._send_command("start")
            
            # 发现main函数中的局部变量
            self.log("识别局部变量")
            self._discover_user_variables()
            self.log(f"发现的变量: {self.user_defined_vars}")
            
            # 记录初始状态
            self.log("记录初始状态")
            self._record_state(None)
            
            # 单步执行并记录状态变化
            step_count = 0
            self.log("开始单步执行")
            
            while step_count < self.max_steps:
                step_count += 1
                self.log(f"步进 #{step_count}")
                
                # 获取当前行代码
                current_line = self._get_current_line()
                self.log(f"当前行: {current_line}")
                
                if not current_line:
                    self.log("无法获取当前行，可能已经执行完毕")
                    break
                
                if current_line and "}" in current_line and "main" in self._send_command("backtrace 1"):
                    self.log("检测到main函数结束")
                    break
                
                # 单步执行
                output = self._send_command("step")
                self.log(f"步进输出前50个字符: {output[:50]}...")  # 只记录前50个字符避免日志过大
                
                if "exited" in output or "exit" in output:
                    self.log("程序已退出")
                    break
                
                # 记录状态
                if current_line:
                    self._record_state(current_line.strip())
            
            # 退出GDB
            self.log("退出GDB")
            self._send_command("quit", expect_prompt=False)
            
            try:
                self.gdb_process.terminate()
                self.gdb_process.wait(timeout=5)
            except:
                try:
                    self.gdb_process.kill()
                except:
                    pass
            
            try:
                os.close(self.gdb_fd)
            except:
                pass
            
            # 生成状态迁移图
            self.log("生成状态迁移图")
            if self.states:
                self._generate_graph()
                self.log(f"已生成状态迁移图，保存到 {self.output_file}")
                return True
            else:
                self.log("没有记录到任何状态，无法生成图")
                print("错误：没有记录到任何程序状态。请确保程序可以正常运行，并包含调试信息。")
                return False
                
        except ImportError:
            self.log("无法导入pty模块，尝试使用普通管道")
            return self._run_with_pipes()
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            print(f"错误: {str(e)}")
            return False
    
    def _run_with_pipes(self):
        """使用普通管道执行GDB（备选方案）"""
        try:
            self.gdb_process = subprocess.Popen(
                ["gdb", "--quiet", "--nx", "--interpreter=mi", self.program_path],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
                bufsize=1  # 行缓冲
            )
            
            # 等待GDB启动
            self._read_mi_output()
            
            # 设置GDB配置
            self._send_mi_command("-gdb-set pagination off")
            self._send_mi_command("-gdb-set print pretty on")
            
            # 在main函数设置断点并运行
            self._send_mi_command("-break-insert main")
            self._send_mi_command("-exec-run")
            
            # 发现局部变量
            self._discover_user_variables_mi()
            self.log(f"发现的变量: {self.user_defined_vars}")
            
            # 记录初始状态
            self._record_state_mi(None)
            
            # 单步执行
            step_count = 0
            while step_count < self.max_steps:
                step_count += 1
                
                # 获取当前行
                frame_info = self._send_mi_command("-stack-info-frame")
                line_match = re.search(r'line="(\d+)"', frame_info)
                if not line_match:
                    break
                
                line_num = line_match.group(1)
                source_line = self._send_mi_command(f"-data-evaluate-expression \"$_gdb_source_line\"")
                current_line = re.search(r'value="(.*)"', source_line)
                if current_line:
                    current_line = current_line.group(1).replace('\\\\', '\\').replace('\\"', '"')
                else:
                    current_line = f"Line {line_num}"
                
                self.log(f"当前行: {current_line}")
                
                # 执行单步
                response = self._send_mi_command("-exec-step")
                if "exited" in response:
                    break
                
                # 记录状态
                self._record_state_mi(current_line.strip())
            
            # 退出GDB
            self._send_mi_command("-gdb-exit", expect_result=False)
            
            try:
                self.gdb_process.terminate()
                self.gdb_process.wait(timeout=5)
            except:
                try:
                    self.gdb_process.kill()
                except:
                    pass
            
            # 生成图
            if self.states:
                self._generate_graph()
                return True
            else:
                print("错误：没有记录到任何程序状态。请确保程序可以正常运行，并包含调试信息。")
                return False
                
        except Exception as e:
            self.log(f"MI模式出错: {str(e)}")
            print(f"错误: {str(e)}")
            return False
    
    def _read_until_prompt(self, timeout=5):
        """读取GDB输出直到出现提示符"""
        start_time = time.time()
        output = ""
        while True:
            if time.time() - start_time > timeout:
                self.log("读取GDB输出超时")
                break
            
            # 检查是否有数据可读
            ready, _, _ = select.select([self.gdb_fd], [], [], 0.1)
            if not ready:
                continue
            
            try:
                # 读取一个字符
                char = os.read(self.gdb_fd, 1).decode('utf-8', errors='replace')
                output += char
                
                # 检查是否包含GDB提示符
                if output.endswith("(gdb) "):
                    break
            except Exception as e:
                self.log(f"读取GDB输出时出错: {str(e)}")
                break
        
        self.log(f"GDB输出: {output[:100]}..." if len(output) > 100 else f"GDB输出: {output}")
        return output
    
    def _send_command(self, command, timeout=10, expect_prompt=True):
        """向GDB发送命令并读取输出"""
        self.log(f"发送GDB命令: {command}")
        
        try:
            # 写入命令
            self.gdb_process.stdin.write(command + "\n")
            self.gdb_process.stdin.flush()
            
            if expect_prompt:
                # 读取输出直到提示符
                output = self._read_until_prompt(timeout)
                return output
            return ""
            
        except Exception as e:
            self.log(f"发送命令时出错: {str(e)}")
            return f"[ERROR] {str(e)}"
    
    def _read_mi_output(self, timeout=5):
        """读取GDB/MI输出"""
        start_time = time.time()
        output_lines = []
        
        while True:
            if time.time() - start_time > timeout:
                break
                
            if self.gdb_process.stdout in select.select([self.gdb_process.stdout], [], [], 0.1)[0]:
                line = self.gdb_process.stdout.readline()
                if not line:
                    break
                    
                output_lines.append(line)
                if "(gdb)" in line:
                    break
        
        output = "".join(output_lines)
        self.log(f"MI输出: {output[:100]}..." if len(output) > 100 else f"MI输出: {output}")
        return output
    
    def _send_mi_command(self, command, timeout=10, expect_result=True):
        """发送GDB/MI命令并读取结果"""
        self.log(f"发送MI命令: {command}")
        
        try:
            self.gdb_process.stdin.write(command + "\n")
            self.gdb_process.stdin.flush()
            
            if expect_result:
                return self._read_mi_output(timeout)
            return ""
            
        except Exception as e:
            self.log(f"发送MI命令时出错: {str(e)}")
            return ""
    
    def _discover_user_variables(self):
        """发现main函数中定义的用户变量"""
        # 尝试从源代码中识别变量
        output = self._send_command("list main,+100")
        lines = output.split('\n')
        
        # 简单解析变量声明
        var_pattern = re.compile(r'\s*(int|float|double|char|long|short|unsigned|struct|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)')
        for line in lines:
            match = var_pattern.search(line)
            if match:
                var_name = match.group(2)
                self.log(f"从源码识别到变量: {var_name}")
                self.user_defined_vars.add(var_name)
        
        # 从info locals获取局部变量
        locals_output = self._send_command("info locals")
        for line in locals_output.split('\n'):
            if '=' in line:
                var_name = line.split('=')[0].strip()
                self.log(f"从info locals识别到变量: {var_name}")
                self.user_defined_vars.add(var_name)
        
        # 如果没有找到变量，尝试单步执行后再检查
        if not self.user_defined_vars:
            self.log("未识别到变量，尝试单步执行后再检查")
            self._send_command("step")
            self._send_command("info locals")
            
            # 检查内存中的变量
            response = self._send_command("info variables")
            var_pattern = re.compile(r'(\w+) += +')
            for line in response.split('\n'):
                match = var_pattern.search(line)
                if match:
                    self.user_defined_vars.add(match.group(1))
        
        # 如果仍然没有变量，添加一些常见的变量名
        if not self.user_defined_vars:
            self.log("添加常见变量名")
            common_vars = ["i", "j", "k", "n", "x", "y", "z", "a", "b", "c", "result", "sum", "count", "value", "num"]
            for var in common_vars:
                output = self._send_command(f"print {var}")
                if "No symbol" not in output and "no symbol" not in output:
                    self.user_defined_vars.add(var)
    
    def _discover_user_variables_mi(self):
        """使用MI模式发现用户变量"""
        # 获取局部变量
        locals_output = self._send_mi_command("-stack-list-locals 1")
        var_pattern = re.compile(r'name="([^"]+)"')
        for match in var_pattern.finditer(locals_output):
            self.user_defined_vars.add(match.group(1))
        
        # 尝试一些常见变量名
        if not self.user_defined_vars:
            common_vars = ["i", "j", "k", "n", "x", "y", "z", "a", "b", "c", "result", "sum", "count", "value", "num"]
            for var in common_vars:
                output = self._send_mi_command(f"-var-create - * {var}")
                if "error" not in output:
                    self.user_defined_vars.add(var)
    
    def _get_variable_values(self):
        """获取当前所有用户定义变量的值"""
        var_values = {}
        
        for var in self.user_defined_vars:
            try:
                output = self._send_command(f"print {var}")
                match = re.search(r'\$\d+ = (.*)', output)
                if match and "No symbol" not in output and "no symbol" not in output:
                    var_values[var] = match.group(1).strip()
            except Exception as e:
                self.log(f"获取变量 {var} 值时出错: {str(e)}")
        
        return var_values
    
    def _get_variable_values_mi(self):
        """使用MI模式获取变量值"""
        var_values = {}
        
        for var in self.user_defined_vars:
            try:
                output = self._send_mi_command(f"-data-evaluate-expression {var}")
                match = re.search(r'value="([^"]*)"', output)
                if match and "error" not in output:
                    var_values[var] = match.group(1).replace('\\\\', '\\').replace('\\"', '"')
            except Exception as e:
                self.log(f"MI模式获取变量 {var} 值时出错: {str(e)}")
        
        return var_values
        
    def _record_state(self, transition_label):
        """记录当前程序状态"""
        var_values = self._get_variable_values()
        self.log(f"当前变量状态: {var_values}")
        
        # 只有变量值发生变化时才记录新状态
        if var_values != self.current_state or not self.states:
            self.state_counter += 1
            state_id = f"S{self.state_counter}"
            self.log(f"记录新状态 {state_id}")
            
            # 记录前一个状态到当前状态的转换
            if self.states:
                prev_state_id = self.states[-1][0]
                self.transitions.append((prev_state_id, state_id, transition_label))
            
            self.states.append((state_id, var_values.copy()))
            self.current_state = var_values.copy()
    
    def _record_state_mi(self, transition_label):
        """使用MI模式记录状态"""
        var_values = self._get_variable_values_mi()
        self.log(f"MI模式当前变量状态: {var_values}")
        
        if var_values != self.current_state or not self.states:
            self.state_counter += 1
            state_id = f"S{self.state_counter}"
            
            if self.states:
                prev_state_id = self.states[-1][0]
                self.transitions.append((prev_state_id, state_id, transition_label))
            
            self.states.append((state_id, var_values.copy()))
            self.current_state = var_values.copy()
    
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
                md_file.write("\n") #匹配模式
        patterns = [
            r'at .*:(\d+)\n\s*(\d+)\s*(.*)',  # 标准格式
            r'at .*:(\d+)\n(.*)',            # 简化格式
            r'Line (\d+)\s*(.*)'             # 另一种可能的格式
        ]
        
        for pattern in patterns:
            match = re.search(pattern, output)
            if match:
                if len(match.groups()) >= 3:
                    return match.group(3)
                elif len(match.groups()) >= 2:
                    return match.group(2)
        
        # 如果所有模式都不匹配，尝试从list命令获取当前行
        output = self._send_command("list")
        lines = output.split('\n')
        for line in lines:
            if '=>' in line:  # GDB通常用=>标记当前行
                return line.split('=>')[1].strip()
        
        return None
    
    def _discover_user_variables(self):
        """发现main函数中定义的用户变量"""
        # 首先查看源代码
        output = self._send_command("list main,+100")
        lines = output.split('\n')
        
        # 简单解析变量声明
        var_pattern = re.compile(r'\s*(int|float|double|char|long|short|unsigned|struct|enum)\s+([a-zA-Z_][a-zA-Z0-9_]*)')
        for line in lines:
            match = var_pattern.search(line)
            if match:
                var_name = match.group(2)
                self.log(f"从源码识别到变量: {var_name}")
                self.user_defined_vars.add(var_name)
        
        # 通过info locals获取局部变量
        locals_output = self._send_command("info locals")
        for line in locals_output.split('\n'):
            if '=' in line:
                var_name = line.split('=')[0].strip()
                self.log(f"从info locals识别到变量: {var_name}")
                self.user_defined_vars.add(var_name)
        
        # 如果没有发现变量，尝试其他方法
        if not self.user_defined_vars:
            self.log("未能识别到变量，尝试其他方法")
            
            # 尝试单步执行几次，然后再检查局部变量
            for _ in range(3):
                self._send_command("step")
                locals_output = self._send_command("info locals")
                for line in locals_output.split('\n'):
                    if '=' in line:
                        var_name = line.split('=')[0].strip()
                        self.user_defined_vars.add(var_name)
            
            # 如果仍然没有变量，添加一些常见的变量名
            if not self.user_defined_vars:
                self.log("添加常见变量名")
                common_vars = ["i", "j", "k", "n", "x", "y", "z", "a", "b", "c", "result", "sum", "count"]
                for var in common_vars:
                    output = self._send_command(f"print {var}")
                    if "No symbol" not in output and "no symbol" not in output:
                        self.user_defined_vars.add(var)
    
    def _get_variable_values(self):
        """获取当前所有用户定义变量的值"""
        var_values = {}
        
        for var in self.user_defined_vars:
            try:
                output = self._send_command(f"print {var}")
                match = re.search(r'\$\d+ = (.*)', output)
                if match and "No symbol" not in output and "no symbol" not in output:
                    var_values[var] = match.group(1).strip()
            except Exception as e:
                self.log(f"获取变量 {var} 值时出错: {str(e)}")
        
        return var_values
    
    def _record_state(self, transition_label):
        """记录当前程序状态"""
        var_values = self._get_variable_values()
        self.log(f"当前变量状态: {var_values}")
        
        # 只有变量值发生变化时才记录新状态
        if var_values != self.current_state or not self.states:
            self.state_counter += 1
            state_id = f"S{self.state_counter}"
            self.log(f"记录新状态 {state_id}")
            
            # 记录前一个状态到当前状态的转换
            if self.states:
                prev_state_id = self.states[-1][0]
                self.transitions.append((prev_state_id, state_id, transition_label))
            
            self.states.append((state_id, var_values.copy()))
            self.current_state = var_values.copy()
    
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