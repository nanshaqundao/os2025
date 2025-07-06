# Dynamic Memory Mapping: How Programs Change Memory Layout at Runtime

## Overview
This document explores how memory mappings can change during program execution, moving beyond the initial static layout set up by `execve()`. We investigate the mechanisms that allow programs to dynamically allocate and manage memory.

## Initial State vs Dynamic Changes

### Initial Process State
When a process starts via `execve()`, the kernel creates a fixed memory layout:
- **Text segment**: Program code (read-only, executable)
- **Data segment**: Initialized global variables (read-write)
- **BSS segment**: Uninitialized global variables (read-write)
- **Stack**: Function calls and local variables (read-write, grows down)
- **Heap**: Dynamic memory allocation area (read-write, grows up)

**Key insight**: All memory access outside these initial regions is illegal and will cause segmentation faults.

### The Dynamic Memory Question
When a program does:
```c
size_t size;
scanf("%zu", &size);          // Read size from user input
void *ptr = malloc(size);     // Allocate memory dynamically
```

**Where does this memory come from?**
- The `malloc(size)` call must somehow obtain memory from the system
- This memory wasn't part of the initial process layout
- There must be a mechanism to expand or modify the memory mappings

## System Calls for Memory Management

### Primary Memory Management System Calls

#### 1. `mmap()` - Memory Mapping (Modern Approach)
```c
void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
int munmap(void *addr, size_t length);
```

**How it works:**
- Maps files or anonymous memory into process address space
- Can create new memory regions anywhere in virtual memory
- Used for most dynamic allocations in modern systems
- Provides fine-grained control over memory permissions and placement

**Example:**
```c
// Allocate 1MB of anonymous memory
void *ptr = mmap(NULL, 1024*1024, PROT_READ|PROT_WRITE, 
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
```

#### 2. `brk()` and `sbrk()` - Legacy Heap Management
```c
int brk(void *addr);                    // Set program break
void *sbrk(intptr_t increment);         // Increment program break
```

**How it works (Legacy):**
- The "program break" is the end of the heap segment
- `brk()` sets the break to a specific address
- `sbrk()` moves the break by a specified amount
- **Rarely used in modern systems** - mostly replaced by `mmap()`

**Why it's outdated:**
- Limited to contiguous heap growth
- Poor interaction with threads (single heap break)
- Less flexible than `mmap()` for memory management
- Most modern malloc implementations prefer `mmap()` for large allocations

#### 3. `mprotect()` - Change Memory Protection
```c
int mprotect(void *addr, size_t len, int prot);
```

**How it works:**
- Changes permissions of existing memory regions
- Can make memory readable, writable, or executable
- Used for security mechanisms and dynamic code generation

## Understanding mmap() Arguments in Detail

The `mmap()` system call has six parameters that control exactly how memory is mapped:

```c
void *mmap(void *addr, size_t length, int prot, int flags, int fd, off_t offset);
```

### Parameter 1: `void *addr` - Preferred Address
- **Purpose**: Hint to kernel about where to place the mapping
- **Common values**:
  - `NULL` - Let kernel choose address (recommended)
  - Specific address - Request mapping at exact location
- **Behavior**:
  - If `NULL`: Kernel finds suitable address (usually what you want)
  - If specific address: Kernel tries to honor request, may fail or choose different address
  - Use `MAP_FIXED` flag to force exact address (dangerous!)

**Examples:**
```c
// Let kernel choose - recommended
void *ptr = mmap(NULL, 4096, ...);

// Request specific address - may not be honored
void *ptr = mmap((void*)0x40000000, 4096, ...);
```

### Parameter 2: `size_t length` - Size of Mapping
- **Purpose**: Number of bytes to map
- **Requirements**:
  - Must be > 0
  - Kernel rounds up to page size (typically 4KB)
  - For file mapping: can be larger than file size
- **Important**: Always use actual size needed, kernel handles page alignment

**Examples:**
```c
// Map 1 byte - kernel allocates full page (4KB)
void *ptr = mmap(NULL, 1, ...);

// Map 1MB
void *ptr = mmap(NULL, 1024*1024, ...);

// Map 10KB - kernel allocates 12KB (3 pages)
void *ptr = mmap(NULL, 10*1024, ...);
```

### Parameter 3: `int prot` - Memory Protection
Controls what operations are allowed on the mapped memory.

**Protection flags (can be OR'd together):**
- `PROT_READ` - Memory can be read
- `PROT_WRITE` - Memory can be written
- `PROT_EXEC` - Memory can be executed as code
- `PROT_NONE` - Memory cannot be accessed (useful for guard pages)

**Common combinations:**
```c
// Read-only memory
PROT_READ

// Read-write memory (most common for data)
PROT_READ | PROT_WRITE

// Executable memory (for code)
PROT_READ | PROT_EXEC

// Read-write-execute (dangerous, often blocked by security)
PROT_READ | PROT_WRITE | PROT_EXEC

// No access (guard pages, reserving address space)
PROT_NONE
```

### Parameter 4: `int flags` - Mapping Behavior
Controls how the mapping behaves and is shared.

**Essential flags:**
- `MAP_PRIVATE` - Changes are private to this process (copy-on-write)
- `MAP_SHARED` - Changes are shared with other processes
- `MAP_ANONYMOUS` - Not backed by file, just anonymous memory
- `MAP_FIXED` - Force exact address (dangerous!)

**Additional flags:**
- `MAP_LOCKED` - Lock pages in memory (prevent swapping)
- `MAP_POPULATE` - Populate page tables immediately
- `MAP_HUGETLB` - Use huge pages (2MB/1GB instead of 4KB)

**Common combinations:**
```c
// Private anonymous memory (typical malloc-style allocation)
MAP_PRIVATE | MAP_ANONYMOUS

// Shared anonymous memory (shared between processes)
MAP_SHARED | MAP_ANONYMOUS

// Private file mapping (load file into memory)
MAP_PRIVATE  // with valid fd

// Shared file mapping (memory-mapped file I/O)
MAP_SHARED   // with valid fd
```

### Parameter 5: `int fd` - File Descriptor
- **Purpose**: File to map into memory
- **Values**:
  - `-1` - For anonymous mappings (must use `MAP_ANONYMOUS`)
  - Valid file descriptor - For file-backed mappings
- **Behavior**:
  - Anonymous: `fd` ignored, memory not backed by file
  - File-backed: Contents of file mapped into memory

**Examples:**
```c
// Anonymous mapping - no file involved
void *ptr = mmap(NULL, 4096, PROT_READ|PROT_WRITE, 
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);

// File mapping
int fd = open("file.txt", O_RDONLY);
void *ptr = mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, fd, 0);
```

### Parameter 6: `off_t offset` - File Offset
- **Purpose**: Where in the file to start mapping
- **Requirements**:
  - Must be page-aligned (multiple of page size)
  - For anonymous mappings: should be 0
  - For file mappings: specifies byte offset in file
- **Behavior**:
  - 0 - Start from beginning of file
  - Page-aligned value - Start from that offset in file

**Examples:**
```c
// Map from beginning of file
void *ptr = mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, fd, 0);

// Map from 8KB offset in file (8192 is page-aligned)
void *ptr = mmap(NULL, 4096, PROT_READ, MAP_PRIVATE, fd, 8192);

// Anonymous mapping - offset ignored
void *ptr = mmap(NULL, 4096, PROT_READ|PROT_WRITE, 
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
```

## Common mmap() Usage Patterns

### 1. Anonymous Memory Allocation (like malloc)
```c
void *ptr = mmap(NULL, size, PROT_READ|PROT_WRITE, 
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
```

### 2. Memory-Mapped File I/O
```c
int fd = open("file.txt", O_RDWR);
void *ptr = mmap(NULL, file_size, PROT_READ|PROT_WRITE, 
                 MAP_SHARED, fd, 0);
```

### 3. Shared Memory Between Processes
```c
void *ptr = mmap(NULL, size, PROT_READ|PROT_WRITE, 
                 MAP_SHARED|MAP_ANONYMOUS, -1, 0);
```

### 4. Executable Memory (JIT compilation)
```c
void *ptr = mmap(NULL, size, PROT_READ|PROT_WRITE, 
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
// Write code to memory
mprotect(ptr, size, PROT_READ|PROT_EXEC); // Make executable
```

## Error Handling
`mmap()` returns `MAP_FAILED` (not NULL) on error:
```c
void *ptr = mmap(NULL, size, PROT_READ|PROT_WRITE, 
                 MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
if (ptr == MAP_FAILED) {
    perror("mmap failed");
    exit(1);
}
```

## How malloc() Works Internally (Modern Implementation)

### Modern malloc() Strategy
Modern malloc implementations (like glibc's ptmalloc, jemalloc, tcmalloc) primarily use `mmap()` for flexibility and better performance.

### Small Allocations (< 128KB typically)
1. **Check existing arenas**: Look for free blocks in memory arenas
2. **Use existing mappings**: Reuse previously mapped memory regions
3. **Create new mapping if needed**: Call `mmap()` for new arena
4. **Manage free blocks**: Maintain sophisticated data structures (red-black trees, bins)
5. **Return pointer**: Give user a pointer to allocated memory

### Large Allocations (> 128KB typically)
1. **Direct mmap()**: Create dedicated memory mapping
2. **Anonymous mapping**: Map memory not backed by a file
3. **Separate region**: Each large allocation gets its own memory region
4. **Immediate munmap()**: Free large allocations directly to kernel

### Why mmap() is Preferred
- **Thread safety**: Each thread can have separate memory arenas
- **Flexibility**: Can allocate memory anywhere in address space
- **Performance**: Kernel can optimize virtual memory management
- **Security**: ASLR works better with scattered allocations
- **Scalability**: Better for multi-threaded applications

## Memory Layout Changes During Execution

### Example: Dynamic Memory Growth
```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>

int main() {
    printf("PID: %d\n", getpid());
    
    // Check initial memory layout
    printf("Initial state - check /proc/%d/maps\n", getpid());
    getchar();  // Pause
    
    // Small allocation - extends heap
    void *small = malloc(1024);
    printf("After small malloc - check /proc/%d/maps\n", getpid());
    getchar();  // Pause
    
    // Large allocation - creates new mapping
    void *large = malloc(1024 * 1024);
    printf("After large malloc - check /proc/%d/maps\n", getpid());
    getchar();  // Pause
    
    // Memory mapping example
    void *mapped = mmap(NULL, 4096, PROT_READ|PROT_WRITE,
                        MAP_PRIVATE|MAP_ANONYMOUS, -1, 0);
    printf("After mmap - check /proc/%d/maps\n", getpid());
    getchar();  // Pause
    
    return 0;
}
```

### Observable Changes in /proc/PID/maps
1. **Initial state**: Basic segments (text, data, bss, heap, stack)
2. **After small malloc**: New anonymous mapping appears (modern malloc)
3. **After large malloc**: Dedicated anonymous mapping for large allocation
4. **After direct mmap**: Additional memory region with specified size

**Modern vs Legacy patterns:**
- **Legacy (brk/sbrk)**: Single contiguous heap region grows
- **Modern (mmap)**: Multiple scattered anonymous memory regions

## Security Implications

### Address Space Layout Randomization (ASLR)
- Dynamic allocations can be placed at random addresses
- Makes exploitation more difficult
- Each program run has different memory layout

### Memory Protection
- Initial segments have fixed permissions
- Dynamic allocations can have custom permissions
- `mprotect()` allows changing permissions after allocation

### Stack vs Heap Overflow
- Stack overflow: Overwrites return addresses, function parameters
- Heap overflow: Corrupts malloc metadata, other allocations
- Both can be exploited, but mitigations differ

## Practical Investigation Questions

### How to observe memory changes?
1. **During execution**: Monitor `/proc/PID/maps` while program runs
2. **With tools**: Use `strace` to see system calls
3. **In debugger**: GDB's `info proc mappings` command
4. **Memory tools**: `valgrind`, `AddressSanitizer` for detailed analysis

### What happens when memory is freed?
- **Small allocations**: `free()` keeps memory in arena for reuse
- **Large allocations**: `munmap()` returns memory to kernel immediately
- **Memory fragmentation**: Less problematic with mmap-based allocation
- **Arena management**: Modern allocators can release entire arenas when empty
- **Lazy deallocation**: Some allocators defer actual `munmap()` calls

### Can memory permissions change?
- Yes, via `mprotect()` system call
- Examples: JIT compilers, self-modifying code
- Security mitigations may prevent certain changes
- W^X (Write XOR Execute) policies restrict RWX regions

## System Call Investigation

### Using strace to observe memory syscalls
```bash
strace -e trace=brk,mmap,munmap,mprotect ./program
```

### Common patterns in modern programs:
- `mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)` - Allocate anonymous memory
- `munmap(addr, size)` - Free memory mapping
- `mprotect(addr, size, prot)` - Change memory permissions
- `brk(0)` - Query current heap end (still used for compatibility)

### Legacy patterns (rare in modern code):
- `brk(addr)` - Set new heap end
- `sbrk(increment)` - Increment program break

## Advanced Topics

### Memory Overcommit
- Linux allows allocating more memory than physically available
- Pages allocated on first write (lazy allocation)
- Can lead to OOM killer activation

### Huge Pages
- Special memory pages (2MB or 1GB instead of 4KB)
- Reduce TLB pressure for large allocations
- Available through `mmap()` with `MAP_HUGETLB`

### Shared Memory
- Multiple processes can map same memory region
- System V shared memory or POSIX shared memory
- Enables inter-process communication

## Modern Memory Management Evolution

### Historical Context
- **1970s-1980s**: `brk()`/`sbrk()` were primary memory management tools
- **1990s**: `mmap()` introduced for file mapping and shared memory
- **2000s**: Modern malloc implementations adopted `mmap()` for heap management
- **2010s+**: Most allocations use `mmap()` for better performance and security

### Why the Shift to mmap()?
1. **Multi-threading**: Each thread can have separate memory arenas
2. **Security**: ASLR works better with scattered allocations
3. **Performance**: Kernel can optimize virtual memory management
4. **Flexibility**: Can allocate memory anywhere in address space
5. **Scalability**: Better for large and diverse allocation patterns

## Conclusion

Memory mapping is not static - it changes dynamically as programs run. Understanding these mechanisms helps explain:
- How `malloc()` provides memory that wasn't initially available
- Why memory layouts differ between program runs
- How security features like ASLR work
- What happens "under the hood" during memory allocation

The key insight is that modern systems primarily use `mmap()` for dynamic memory management, with `brk()`/`sbrk()` relegated to legacy compatibility. The kernel provides system calls (`mmap`, `munmap`, `mprotect`) that allow programs to modify their memory layout at runtime, enabling flexible dynamic memory management while maintaining security and isolation.