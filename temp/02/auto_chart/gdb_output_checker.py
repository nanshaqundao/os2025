#!/usr/bin/env python3
import subprocess
import os
import argparse

def run_gdb_and_save_output(program_path, output_file="gdb_output.txt"):
    """运行GDB并保存输出到文件"""
    # 创建一个简单的GDB脚本
    gdb_script = """
break main
run
info locals
frame
step
info locals
frame
step
info locals
frame
step
info locals
frame
step
info locals
frame
quit
"""
    
    # 写入脚本文件
    script_path = "basic_gdb_script.txt"
    with open(script_path, "w") as f:
        f.write(gdb_script)
    
    # 运行GDB并获取输出
    try:
        process = subprocess.run(
            ["gdb", "-x", script_path, "--quiet", "--batch", program_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        # 保存输出
        with open(output_file, "w") as f:
            f.write("=== GDB STDOUT ===\n")
            f.write(process.stdout)
            f.write("\n\n=== GDB STDERR ===\n")
            f.write(process.stderr)
        
        # 清理临时文件
        os.remove(script_path)
        
        print(f"GDB输出已保存到 {output_file}")
        return True
    
    except Exception as e:
        print(f"错误: {str(e)}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="GDB输出查看器")
    parser.add_argument("program", help="要调试的程序路径")
    parser.add_argument("-o", "--output", default="gdb_output.txt", help="输出文件路径")
    args = parser.parse_args()
    
    print(f"正在运行GDB以分析 {args.program}...")
    run_gdb_and_save_output(args.program, args.output)