#!/usr/bin/env python3
import subprocess
import re
import os
import argparse
import sys

class CollatzVisualizer:
    def __init__(self, program_path, output_file="plot.md", debug=False, max_steps=30):
        self.program_path = program_path
        self.output_file = output_file
        self.debug = debug
        self.max_steps = max_steps
        self.states = []
        self.transitions = []
        
    def log(self, message):
        """输出调试信息"""
        if self.debug:
            print(f"[DEBUG] {message}", file=sys.stderr)
            sys.stderr.flush()
    
    def run(self):
        """执行GDB调试并生成状态迁移图"""
        try:
            # 运行GDB并获取输出
            gdb_output = self._run_gdb()
            
            # 解析GDB输出
            self._parse_gdb_output(gdb_output)
            
            # 生成状态迁移图
            if self.states:
                self._generate_output()
                print(f"状态迁移图已生成到 {self.output_file}")
                return True
            else:
                print("错误：未能从GDB输出中提取状态信息")
                return False
                
        except Exception as e:
            self.log(f"发生错误: {str(e)}")
            print(f"错误: {str(e)}")
            return False
    
    def _run_gdb(self):
        """运行GDB并获取输出"""
        # 构建GDB命令脚本
        commands = ["break main", "run"]
        
        # 添加多个步进命令
        for _ in range(self.max_steps):
            commands.extend(["info locals", "frame", "step"])
        
        # 写入命令文件
        script_path = "collatz_gdb_script.txt"
        with open(script_path, "w") as f:
            for cmd in commands:
                f.write(cmd + "\n")
        
        self.log(f"已创建GDB脚本: {script_path}")
        
        # 执行GDB命令
        self.log(f"执行GDB: gdb -x {script_path} --quiet --batch {self.program_path}")
        process = subprocess.run(
            ["gdb", "-x", script_path, "--quiet", "--batch", self.program_path],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        # 删除临时文件
        os.remove(script_path)
        
        if process.returncode != 0 and not process.stdout:
            self.log(f"GDB执行异常: {process.stderr}")
            raise Exception("GDB执行失败")
        
        self.log(f"GDB输出长度: {len(process.stdout)} 字符")
        return process.stdout
    
    def _parse_gdb_output(self, output):
        """解析GDB输出以提取状态信息"""
        # 使用正则表达式提取变量信息和代码行
        state_pattern = re.compile(r'n = (\d+)\nsteps = (\d+)\n#0\s+main \(\) at .*:(\d+)\n(.*)', re.MULTILINE)
        
        # 找出所有匹配项
        matches = state_pattern.findall(output)
        self.log(f"找到 {len(matches)} 个状态匹配")
        
        prev_state = None
        
        for i, match in enumerate(matches):
            if len(match) >= 4:
                n = int(match[0])
                steps = int(match[1])
                line = int(match[2])
                code = match[3].strip()
                
                # 记录状态
                state_id = f"S{i+1}"
                state = {
                    'id': state_id,
                    'n': n,
                    'steps': steps,
                    'line': line,
                    'code': code
                }
                
                self.states.append(state)
                
                # 记录转换
                if prev_state:
                    self.transitions.append({
                        'from': prev_state['id'],
                        'to': state_id,
                        'label': prev_state['code']
                    })
                
                prev_state = state
                self.log(f"记录状态 {state_id}: n={n}, steps={steps}, line={line}")
        
        self.log(f"共提取 {len(self.states)} 个状态")
    
    def _generate_ascii_diagram(self):
        """生成ASCII格式的状态图"""
        result = []
        
        for i, state in enumerate(self.states):
            # 添加状态框
            result.append(f"[{state['id']}]")
            result.append(f"  n = {state['n']}")
            result.append(f"  steps = {state['steps']}")
            
            # 添加转移（除了最后一个状态）
            if i < len(self.states) - 1:
                result.append("  |")
                result.append(f"  | {state['code']}")
                result.append("  v")
        
        return "\n".join(result)
    
    def _generate_output(self):
        """生成Markdown格式的输出"""
        with open(self.output_file, "w") as f:
            f.write("# Collatz序列状态迁移图\n\n")
            f.write("这个图展示了Collatz猜想计算过程中的状态变化。\n")
            f.write("每个状态包含变量n和steps的值，箭头上的文本表示执行的代码。\n\n")
            
            # 添加ASCII图
            f.write("## 状态迁移图\n\n")
            f.write("```\n")
            f.write(self._generate_ascii_diagram())
            f.write("\n```\n\n")
            
            # 添加状态转换表
            f.write("## 状态转换表\n\n")
            f.write("| 状态 | n值 | steps值 | 执行代码 | 下一状态 |\n")
            f.write("|------|-----|---------|----------|----------|\n")
            
            for i, state in enumerate(self.states):
                next_state = ""
                code = state['code']
                if i < len(self.states) - 1:
                    next_state = self.states[i+1]['id']
                
                f.write(f"| {state['id']} | {state['n']} | {state['steps']} | `{code}` | {next_state} |\n")
            
            # 添加序列变化图
            f.write("\n## n值变化序列\n\n")
            f.write("```\n")
            n_values = [str(state['n']) for state in self.states]
            f.write(" -> ".join(n_values))
            f.write("\n```\n\n")
            
            # 添加Collatz猜想解释
            f.write("## 关于Collatz猜想\n\n")
            f.write("Collatz猜想（又称3n+1猜想）是指对于任何一个正整数，如果它是奇数，则对它乘3再加1，如果它是偶数，则对它除以2，\n")
            f.write("如此循环，最终都能得到1。这个程序正是在计算从初始值n到达1所需的步数。\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Collatz猜想状态迁移可视化工具")
    parser.add_argument("program", help="要调试的程序路径")
    parser.add_argument("-o", "--output", default="plot.md", help="输出的Markdown文件路径")
    parser.add_argument("-d", "--debug", action="store_true", help="启用调试模式")
    parser.add_argument("-s", "--steps", type=int, default=30, help="最大步数")
    args = parser.parse_args()
    
    print(f"开始分析程序 {args.program}...")
    visualizer = CollatzVisualizer(args.program, args.output, args.debug, args.steps)
    visualizer.run()