# Study Over Simple Binary

## Overview
Analysis of the `simple` binary - a statically linked executable with large code and data sections.

## Source Code Analysis
The `simple.c` file contains:
- 10MB character array: `char arr[10485760];`
- 10MB of NOP instructions via inline assembly
- Statically linked (no shared libraries)

## ELF Header Information
```
ELF Header:
  Magic:   7f 45 4c 46 02 01 01 03 00 00 00 00 00 00 00 00 
  Class:                             ELF64
  Data:                              2's complement, little endian
  Version:                           1 (current)
  OS/ABI:                            UNIX - GNU
  ABI Version:                       0
  Type:                              EXEC (Executable file)
  Machine:                           Advanced Micro Devices X86-64
  Version:                           0x1
  Entry point address:               0x401620
  Start of program headers:          64 (bytes into file)
  Start of section headers:          11384624 (bytes into file)
  Flags:                             0x0
  Size of this header:               64 (bytes)
  Size of program headers:           56 (bytes)
  Number of program headers:         10
  Size of section headers:           64 (bytes)
  Number of section headers:         38
  Section header string table index: 37
```

## Memory Layout
```
High Addresses (0x7fff...)
┌─────────────────────────────────────┐
│ Stack (rw-p)                        │ 0x7ffffffdd000 - 0x7ffffffff000 (136KB)
│ [stack]                             │
├─────────────────────────────────────┤
│ vDSO (r-xp)                         │ 0x7ffff7ffd000 - 0x7ffff7fff000 (8KB)
│ [vdso]                              │
├─────────────────────────────────────┤
│ vvar (r--p)                         │ 0x7ffff7ff9000 - 0x7ffff7ffd000 (16KB)
│ [vvar]                              │
└─────────────────────────────────────┘

Large Gap

┌─────────────────────────────────────┐
│ Heap (rw-p)                         │ 0xec8000 - 0x18cd000 (~10MB)
│ [heap] - grows for 10MB char arr    │
├─────────────────────────────────────┤
│ Data/BSS (rw-p)                     │ 0xec1000 - 0xec8000 (28KB)
│ - Contains 10MB arr[10485760]       │
├─────────────────────────────────────┤
│ Read-only data (r--p)               │ 0xe98000 - 0xec1000 (164KB)
│ - Constants, strings                │
├─────────────────────────────────────┤
│ Code/Text (r-xp)                    │ 0x401000 - 0xe98000 (~10MB)
│ - Contains 10MB of NOP instructions │
│ - Entry point: 0x401620             │
├─────────────────────────────────────┤
│ Program headers (r--p)              │ 0x400000 - 0x401000 (4KB)
│ - ELF headers                       │
└─────────────────────────────────────┘
Low Addresses (0x400000)
```

## Key Observations

### Memory Mappings
| Start Address | End Address | Size | Permissions | Name |
|---------------|-------------|------|------------|------|
| 0x400000 | 0x401000 | 0x1000 | r--p | /home/nash/os2025/address-space/simple |
| 0x401000 | 0xe98000 | 0xa97000 | r-xp | /home/nash/os2025/address-space/simple |
| 0xe98000 | 0xec1000 | 0x29000 | r--p | /home/nash/os2025/address-space/simple |
| 0xec1000 | 0xec8000 | 0x7000 | rw-p | /home/nash/os2025/address-space/simple |
| 0xec8000 | 0x18cd000 | 0xa05000 | rw-p | [heap] |
| 0x7ffff7ff9000 | 0x7ffff7ffd000 | 0x4000 | r--p | [vvar] |
| 0x7ffff7ffd000 | 0x7ffff7fff000 | 0x2000 | r-xp | [vdso] |
| 0x7ffffffdd000 | 0x7ffffffff000 | 0x22000 | rw-p | [stack] |

### Register State
- **rip**: 0x401620 (entry point address)
- **rsp**: 0x7fffffffdb50 (stack pointer in stack region)
- Most registers zeroed (typical for process start)

### vsyscall vs vDSO
- **No vsyscall mapping** - This system uses the modern vDSO approach
- **vDSO present** at 0x7ffff7ffd000 - provides fast system calls with ASLR security
- **vvar region** at 0x7ffff7ff9000 - contains kernel variables accessible from userspace

### Static Linking
- Single executable mapping (no shared libraries)
- Large text section (~10MB) due to static linking and NOP instructions
- Self-contained binary with all dependencies included

## Security Features
- **ASLR**: vDSO and stack are randomized
- **NX bit**: Code and data sections have appropriate execute permissions
- **No vsyscall**: Avoids fixed-address security vulnerability

## Deep Dive: Revisiting the 'simple' Program (Q&A and Insights)

### What does the source code do?
- Allocates a 10MB static array (`arr[10485760]`) in the data segment.
- Generates 10MB of NOP instructions in the code segment using inline assembly.
- Is statically linked (no shared libraries in memory map).

### What does the memory map look like?
- Large `.text` segment (code) due to NOPs.
- Large `.data` segment for the array.
- Heap and stack mapped as usual.
- No shared libraries (statically linked).

### How to visualize memory layout more clearly?
- Add a large `.bss` (uninitialized data) array and a large `malloc` in `main` to see `.bss` and heap regions.
- Print the PID and pause execution to inspect `/proc/<pid>/maps`.

### GDB Usage and Observations
- `start` in GDB stops at the first line of `main` (before user code runs).
- To see the state before `main`, set a breakpoint at `_start` and run.
- `info registers` shows all general-purpose registers zeroed except `rsp` (stack pointer) and `rip` (entry point).
- `info proc mappings` shows the ELF segments mapped into memory.
- `p &arr` in GDB shows the address of the static array; `arr[1]` and `*(arr+1)` are equivalent (second element).

### ELF and Memory Map Cross-Checks
- `readelf -h simple` shows the entry point address, which matches the `rip` value at program start.
- `readelf -l simple` (program headers) and `readelf -S simple` (section headers) can be cross-checked with memory mappings for segment addresses, sizes, and permissions.
- Symbol table (`readelf -s simple` or `nm simple`) can be used to find addresses of variables/functions and compare with GDB output.

### Security Features Observed
- **ASLR**: vDSO and stack are randomized.
- **NX bit**: Code and data sections have correct execute permissions (code is executable, data is not).
- **No vsyscall**: Only vDSO is present, avoiding fixed-address vulnerabilities.

### Assembly and GDB Details
- `nop` is a no-operation instruction (does nothing, used for padding/alignment).
- In GDB assembly mode, `si` steps one instruction at a time (stepping through millions of NOPs is slow!).
- `arr[1]` and `*(arr+1)` are the same; `*arr+1` is not (it adds 1 to the value of the first element).

### ELF Info Recap
- ELF header contains entry point, program/section header offsets, and more.
- Program headers describe how segments are mapped into memory (addresses, sizes, permissions).
- Section headers describe code/data/bss/rodata regions.
- Entry point in ELF matches `rip` at process start.

### Practical Tips
- Use `readelf` and `nm` to explore ELF structure and symbols.
- Use GDB to inspect memory, registers, and process mappings at any stage.
- For static binaries, expect no shared library mappings.
- For memory experiments, add/modify static, bss, and heap allocations to see their effect in `/proc/<pid>/maps`.

## [vvar] and [vdso] Regions: Access and Usage

- The `[vvar]` (Virtual Variables) region is a special, read-only memory area mapped by the Linux kernel into every process. It provides fast access to certain kernel-maintained data, such as timekeeping information, for use by the vDSO.
- User programs do **not** access `[vvar]` directly. Instead, standard library functions like `clock_gettime()` and `gettimeofday()` use the vDSO, which in turn reads from `[vvar]` for fast, syscall-free access to kernel data.
- The `[vvar]` region is mapped as read-only (`r--p`) and is not meant for direct user or debugger access. Attempting to read it directly in GDB will usually fail or produce uninterpretable data.
- The `[vdso]` (Virtual Dynamic Shared Object) region contains kernel-provided code that implements certain system calls in user space, using data from `[vvar]`.
- **Summary:** To get data from `[vvar]`, always use standard APIs in your code. You cannot reliably or meaningfully access `[vvar]` directly from outside the process or in a debugger.

## Initial Stack Layout: Understanding execve() Process Startup

### What is the initial stack layout when execve() starts a new process?

When the kernel executes a new program via `execve()`, it sets up a specific stack layout containing command-line arguments and environment variables. This layout is standardized and follows the System V ABI.

### How is the stack organized from high to low addresses?

```
High addresses (stack grows down)
┌─────────────────────────────────────┐
│ Environment strings                 │ <- "PATH=/usr/bin\0", "HOME=/home/user\0"
│ "PATH=/usr/bin\0"                  │
│ "HOME=/home/user\0"                │
│ "SHELL=/bin/bash\0"                │
│ ...                                │
├─────────────────────────────────────┤
│ Argument strings                    │ <- "./simple\0", "arg1\0", "arg2\0"
│ "./simple\0"                       │
│ "arg1\0"                           │
│ "arg2\0"                           │
├─────────────────────────────────────┤
│ NULL                               │ <- End of envp array
├─────────────────────────────────────┤
│ envp[n-1]                          │ <- Environment variable pointers
│ envp[1]                            │
│ envp[0]                            │
├─────────────────────────────────────┤
│ NULL                               │ <- End of argv array
├─────────────────────────────────────┤
│ argv[argc-1]                       │ <- Command line argument pointers
│ argv[1]                            │
│ argv[0]                            │
├─────────────────────────────────────┤
│ argc                               │ <- Number of arguments
└─────────────────────────────────────┘
Low addresses (RSP points here at startup)
```

### What exactly is argv[x] and how does it work?

**`argv[x]` is a pointer** that points to the actual string value stored at a higher memory address on the stack.

**Key points:**
- `argc` contains the count of command-line arguments
- `argv` is an array of pointers (`char **`)
- Each `argv[x]` contains a memory address pointing to a null-terminated string
- The actual string data is stored higher up on the stack

### Can you show a concrete example?

For command: `./simple arg1 arg2`

```
High addresses
┌─────────────────────────────────────┐
│ "./simple\0"          ←─────────────┼─── argv[0] points here (0x7fff1220)
│ "arg1\0"              ←─────────────┼─── argv[1] points here (0x7fff1230)
│ "arg2\0"              ←─────────────┼─── argv[2] points here (0x7fff1240)
├─────────────────────────────────────┤
│ NULL (0x0)                         │
├─────────────────────────────────────┤
│ 0x7fff1240 (ptr to "arg2")        │ ← argv[2]
│ 0x7fff1230 (ptr to "arg1")        │ ← argv[1]
│ 0x7fff1220 (ptr to "./simple")    │ ← argv[0]
├─────────────────────────────────────┤
│ 3                                  │ ← argc
└─────────────────────────────────────┘
Low addresses (RSP points here)
```

### How do main() parameters map to this layout?

When `main(int argc, char **argv, char **envp)` is called:

1. **argc** = 3 (number of arguments including program name)
2. **argv** = pointer to the array of argument pointers
3. **envp** = pointer to the array of environment variable pointers

The C runtime library (_start function) extracts these values from the stack and passes them to main().

### What's the relationship between pointers and string data?

- `argv[0]` stores address 0x7fff1220, which points to string "./simple"
- `argv[1]` stores address 0x7fff1230, which points to string "arg1"
- `argv[2]` stores address 0x7fff1240, which points to string "arg2"

This is why `argv` is declared as `char **` (pointer to pointer to char) - it's an array of pointers where each element points to a string.

### How can you verify this in practice?

Using GDB on the simple program:
```bash
gdb ./simple
(gdb) break main
(gdb) run arg1 arg2
(gdb) print argc          # Shows: 3
(gdb) print argv[0]       # Shows: address like 0x7fff1220
(gdb) print *argv[0]      # Shows: '.' (first char of "./simple")
(gdb) x/s argv[0]         # Shows: "./simple"
(gdb) print argv[1]       # Shows: address like 0x7fff1230
(gdb) x/s argv[1]         # Shows: "arg1"
```

### Why does the kernel organize the stack this way?

1. **Efficiency**: All arguments and environment variables are in one contiguous memory region
2. **Standardization**: Follows System V ABI specification for consistent behavior
3. **Security**: Kernel controls the layout, preventing manipulation during process startup
4. **Simplicity**: C runtime can easily extract argc/argv/envp from known stack positions

---

This section summarizes the hands-on exploration and Q&A about the 'simple' program, its ELF structure, memory layout, and debugging techniques. Use it as a quick reference for future study or review.