# Registers

| Register | Hex Value | Decimal Value |
|----------|-----------|---------------|
| rax | 0x0000000000000000 | 0 |
| rbx | 0x0000000000000000 | 0 |
| rcx | 0x0000000000000000 | 0 |
| rdx | 0x0000000000000000 | 0 |
| rsi | 0x0000000000000000 | 0 |
| rdi | 0x0000000000000000 | 0 |
| rbp | 0x0000000000000000 | 0 |
| rsp | 0x00007fffffffdb50 | 140737488345936 |
| r8 | 0x0000000000000000 | 0 |
| r9 | 0x0000000000000000 | 0 |
| r10 | 0x0000000000000000 | 0 |
| r11 | 0x0000000000000000 | 0 |
| r12 | 0x0000000000000000 | 0 |
| r13 | 0x0000000000000000 | 0 |
| r14 | 0x0000000000000000 | 0 |
| r15 | 0x0000000000000000 | 0 |
| rip | 0x0000000000401620 | 4199968 |
| eflags | 0x0000000000000202 | 514 |

# Memory Mappings

| Start Address | End Address | Size | Permissions | Name |
|---------------|-------------|------|--------------|------|
| 0x400000 | 0x401000 | 0x1000 | r--p | /home/nash/os2025/address-space/simple |
| 0x401000 | 0xe98000 | 0xa97000 | r-xp | /home/nash/os2025/address-space/simple |
| 0xe98000 | 0xec1000 | 0x29000 | r--p | /home/nash/os2025/address-space/simple |
| 0xec1000 | 0xec8000 | 0x7000 | rw-p | /home/nash/os2025/address-space/simple |
| 0xec8000 | 0x18cd000 | 0xa05000 | rw-p | [heap] |
| 0x7ffff7ff9000 | 0x7ffff7ffd000 | 0x4000 | r--p | [vvar] |
| 0x7ffff7ffd000 | 0x7ffff7fff000 | 0x2000 | r-xp | [vdso] |
| 0x7ffffffdd000 | 0x7ffffffff000 | 0x22000 | rw-p | [stack] |
