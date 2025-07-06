# TestKit Explained: A Deep Dive for C Beginners

This document explains how the TestKit unit testing framework works, from high-level concepts down to the machine-level details.

## Table of Contents
1. [What TestKit Does](#what-testkit-does)
2. [Key C Concepts](#key-c-concepts)
3. [How to Read testkit.c](#how-to-read-testkitc)
4. [The Process Creation Hierarchy](#the-process-creation-hierarchy)
5. [How Test Registration Works](#how-test-registration-works)
6. [Functions at the Machine Level](#functions-at-the-machine-level)
7. [Why It All Works Together](#why-it-all-works-together)

## What TestKit Does

TestKit is a sophisticated testing system that automatically runs tests when your program finishes. Think of it as a "safety net" that catches bugs by running tests in isolated environments.

### Core Features
- **fork()** to run each test in a separate process for isolation
- **mmap()** with `MAP_SHARED | MAP_ANONYMOUS` for shared memory between parent/child
- **waitpid()** for parent processes to wait for test results
- Signal handling to detect crashes (SIGSEGV, SIGABRT, etc.)
- Timeout protection with `alarm()`

### Key Features
- Tests register automatically using `__attribute__((constructor))`
- Results are color-coded: PASS (green), FAIL (red), with crash details
- Supports both unit tests and system tests
- Shared memory stores test output and results

### Example Usage
```c
#include "testkit.h"

// This test will automatically run when TK_RUN is set
UnitTest(basic_math) {
    tk_assert(2 + 2 == 4, "Math is broken!");
}

int main() {
    printf("Hello World\n");
    return 0;
}
```

Compile and run:
```bash
gcc test.c testkit.c -o test
TK_RUN=1 ./test
```

## Key C Concepts

### 1. fork() - Creating Child Processes
```c
pid_t child_pid = fork();
if (child_pid == 0) {
    // This code runs in the CHILD process
    exit(main(t->argc, t->argv, environ));
} else {
    // This code runs in the PARENT process
    int status;
    waitpid(child_pid, &status, 0);  // Wait for child to finish
}
```

**What fork() does:**
- Creates an exact copy of the current process
- Returns 0 in the child process, child's ID in the parent
- Both processes continue running from the fork() point
- **Why use it?** If a test crashes, only the child dies - the parent continues running other tests

### 2. mmap() - Shared Memory
```c
char *buf = mmap(NULL, TK_OUTPUT_LIMIT, 
                 PROT_READ | PROT_WRITE,
                 MAP_SHARED | MAP_ANONYMOUS, -1, 0);
```

**What mmap() does:**
- Creates a memory region that both parent and child can access
- `MAP_SHARED` means changes in child are visible to parent
- `MAP_ANONYMOUS` means it's not backed by a file
- **Why use it?** Child process can write test results that parent can read

### 3. Constructor Functions
```c
__attribute__((constructor))
void register_my_test() {
    // This runs BEFORE main()
}
```

**What constructors do:**
- Functions that run automatically when program starts
- **Why use it?** Tests register themselves without you having to manually call anything

## How to Read testkit.c

Here's the logical reading order to understand this complex file:

### 📍 Step 1: Start at the Bottom (Lines 266-291)
```c
__attribute__((constructor))
void tk_register_hook(void) {
    // This runs BEFORE main()
    // Sets up the testing infrastructure
}
```
**🔍 Why start here?** This is the "entry point" that runs before your main() function.

### 📍 Step 2: Read the Data Structure (Line 10)
```c
static struct tk_testcase tests[TK_MAX_TESTS];
```
**🔍 What it is:** Global array that stores all registered tests.

### 📍 Step 3: Test Registration (Lines 17-61)
```c
void tk_add_test(struct tk_testcase t) {
    // Called by constructor macros to add tests
}
```
**🔍 What it does:** When you write `UnitTest(my_test)`, this function stores your test.

### 📍 Step 4: Main Test Runner (Lines 173-229)
```c
static void run_all_testcases(void) {
    // The heart of the testing system
}
```
**🔍 What it does:** Runs all registered tests using fork() and mmap().

### 📍 Step 5: Individual Test Runner (Lines 66-116)
```c
static int run_testcase(struct tk_testcase *t, char *buf) {
    // Runs a single test case
}
```
**🔍 What it does:** Executes one test in isolation.

### 🗺️ Reading Map with Key Concepts

#### Phase 1: Setup (Bottom of file)
```c
// Lines 266-291: tk_register_hook()
1. Creates a pipe for communication
2. Forks a "worker process" that will run tests
3. Registers notify_worker() to run when main() exits
```

#### Phase 2: Test Registration (Middle)
```c
// Lines 17-61: tk_add_test()
1. Checks if testing is enabled (TK_RUN/TK_VERBOSE environment variables)
2. Stores test in the global tests[] array
3. Handles command-line arguments for system tests
```

#### Phase 3: Test Execution (Top half)
```c
// Lines 173-229: run_all_testcases()
1. For each test:
   - Creates shared memory with mmap()
   - Forks a child process
   - Child runs the test with alarm() timeout
   - Parent waits and checks results
   - Cleans up shared memory
```

#### Phase 4: Individual Test (Core logic)
```c
// Lines 66-116: run_testcase()
1. Calls test->init() if it exists
2. Redirects stdout/stderr to memory buffer
3. If system test: forks again and calls main()
4. If unit test: directly calls test function
5. Captures all output in shared memory
```

## The Process Creation Hierarchy

There are **4 different `fork()` calls** in this code, each serving a specific purpose:

### 1. Line 280: Main Worker Process
```c
pid_t pid = fork();
if (pid == 0) {
    worker_process();  // Child becomes the test runner
} else {
    atexit(notify_worker);  // Parent continues as your main program
}
```
**Purpose:** Creates a dedicated process to run all tests
**Why:** Tests run after main() exits, so we need a separate process

### 2. Line 202: Per-Test Process
```c
pid_t pid = fork();
if (pid == 0) {
    // Child: run ONE test case
    alarm(TK_TIME_LIMIT_SEC);
    exit(run_testcase(t, buf));
} else {
    // Parent: wait and check results
    waitpid(pid, &status, 0);
}
```
**Purpose:** Each test runs in its own process
**Why:** If one test crashes, it doesn't kill other tests

### 3. Line 89: System Test Subprocess
```c
pid_t child_pid = fork();
if (child_pid == 0) {
    exit(main(t->argc, t->argv, environ));  // Call main() with different args
} else {
    waitpid(child_pid, &status, 0);
}
```
**Purpose:** Runs your main() function with different command-line arguments
**Why:** System tests need to test your program like a real user would run it

### 4. Line 120: Cleanup Process
```c
pid_t fini_pid = fork();
if (fini_pid == 0) {
    alarm(TK_TIME_LIMIT_SEC);
    t->fini();  // Run cleanup function
    exit(0);
} else {
    waitpid(fini_pid, NULL, 0);
}
```
**Purpose:** Runs cleanup code (like freeing memory)
**Why:** Even cleanup code might hang or crash, so isolate it

### 🌳 Complete Process Tree

Here's what the full process tree looks like when running:

```
Your Program (main)
│
├── Worker Process (Line 280)
│   ├── Test Process #1 (Line 202)
│   │   ├── System Test Subprocess (Line 89) [if system test]
│   │   └── Cleanup Process (Line 120) [if test has cleanup]
│   │
│   ├── Test Process #2 (Line 202)
│   │   ├── System Test Subprocess (Line 89) [if system test]
│   │   └── Cleanup Process (Line 120) [if test has cleanup]
│   │
│   └── Test Process #N...
│
└── [Your main program continues and exits]
```

### 🤔 Why So Many Processes?

Each `fork()` serves a specific **isolation** purpose:

1. **Worker Process Isolation**
   - **Problem:** Tests need to run after main() exits
   - **Solution:** Create worker process that waits for main() to finish

2. **Test Process Isolation**
   - **Problem:** If one test crashes, it kills all remaining tests
   - **Solution:** Each test runs in its own process

3. **System Test Isolation**
   - **Problem:** System tests need to call main() with different arguments
   - **Solution:** Fork again and call main() in the child

4. **Cleanup Process Isolation**
   - **Problem:** Even cleanup code can hang or crash
   - **Solution:** Run cleanup in its own process with timeout

## How Test Registration Works

The test registration **isn't object-oriented** - it's **macro magic** that generates code automatically.

### What You Write:
```c
UnitTest(my_test) {
    tk_assert(1 == 1, "This should pass");
}
```

### What the Preprocessor Generates:

The `UnitTest` macro expands to create **3 things automatically**:

#### 1. The Actual Test Function
```c
static void __tk_my_test_42(void) {
    tk_assert(1 == 1, "This should pass");
}
```

#### 2. A Constructor Function
```c
__attribute__((constructor))
void __tk_regmy_test_42() {
    tk_add_test((struct tk_testcase) {
        .enabled = 1,
        .name = "my_test",
        .loc = "test.c:15",
        .utest = __tk_my_test_42,
    });
}
```

#### 3. The Registration Happens Automatically
The `__attribute__((constructor))` makes the registration function run **before main()**.

### Step-by-Step Breakdown

#### Step 1: Macro Definition Chain
```c
#define UnitTest(name, ...) \
    __tk_testcase(name, void, utest, __VA_ARGS__)
```

#### Step 2: The Real Macro
```c
#define __tk_testcase(name_, body_arg, test, ...) \
    static void TK_UNIQUE_NAME(name_)(body_arg); \
    __attribute__((constructor)) \
    void TK_UNIQUE_NAME(reg##name_)() { \
        tk_add_test((struct tk_testcase) { \
            .enabled = 1, \
            .name = #name_, \
            .utest = TK_UNIQUE_NAME(name_), \
            __VA_ARGS__ \
        }); \
    } \
    static void TK_UNIQUE_NAME(name_)(body_arg)
```

#### Step 3: Helper Macros
```c
#define TK_UNIQUE_NAME(prefix) __tk_##prefix##_42  // Uses line number
#define TK_STRINGIFY(x) #x  // Converts to string
```

### How Registration Actually Works

#### Phase 1: Compilation
When you compile, the preprocessor expands your `UnitTest(my_test)` into:

```c
// Function declaration
static void __tk_my_test_42(void);

// Constructor function that runs before main()
__attribute__((constructor))
void __tk_regmy_test_42() {
    tk_add_test((struct tk_testcase) {
        .enabled = 1,
        .name = "my_test",
        .loc = "test.c:15",
        .utest = __tk_my_test_42,  // Function pointer!
    });
}

// Function definition (your actual test code)
static void __tk_my_test_42(void) {
    tk_assert(1 == 1, "This should pass");
}
```

#### Phase 2: Program Startup
```c
1. Program starts
2. __tk_regmy_test_42() runs automatically (constructor)
3. It calls tk_add_test() with a struct containing:
   - Test name: "my_test"
   - Function pointer: __tk_my_test_42
   - Location: "test.c:15"
4. tk_add_test() stores this in the global tests[] array
5. main() runs
6. main() exits
7. Worker process runs all stored tests
```

### It's Not Object-Oriented - It's "Struct-Oriented"

#### The Core Data Structure:
```c
struct tk_testcase {
    int enabled;
    const char *name;
    const char *loc;
    void (*utest)(void);      // Function pointer to your test!
    void (*init)(void);       // Optional setup
    void (*fini)(void);       // Optional cleanup
    // ... more fields for system tests
};
```

#### How It Works:
1. **Macros generate code** that creates these structs
2. **Constructor functions** automatically register the structs
3. **Function pointers** store references to your test functions
4. **Global array** stores all the structs
5. **Test runner** calls the function pointers later

### Why This Design?

#### Automatic Registration
- You don't need to manually call `register_test()`
- Just writing `UnitTest(foo)` automatically registers it
- No central list to maintain

#### No Runtime Overhead
- Registration happens at compile time + program startup
- No dynamic memory allocation
- No hash tables or linked lists needed

#### Type Safety
- Function pointers ensure correct signatures
- Compile-time errors if you mess up

## Functions at the Machine Level

### What Is a Function Really?

#### At the Hardware Level:
A function is literally **a sequence of machine instructions stored in memory**. When you write:

```c
void my_test() {
    printf("Hello\n");
}
```

The compiler generates something like:
```assembly
my_test:
    push   %rbp           # Save old frame pointer
    mov    %rsp,%rbp      # Set up new frame
    mov    $0x400614,%edi # Load address of "Hello\n"
    call   printf         # Call printf
    pop    %rbp           # Restore frame
    ret                   # Return to caller
```

#### In Memory:
```
Memory Address    Machine Code (bytes)    Assembly
0x400500:         55                      push %rbp
0x400501:         48 89 e5               mov %rsp,%rbp
0x400504:         bf 14 06 40 00         mov $0x400614,%edi
0x400509:         e8 f2 fe ff ff         call printf
0x40050e:         5d                      pop %rbp
0x40050f:         c3                      ret
```

### Function Pointers: Just Memory Addresses

#### A Function Pointer Is:
```c
void (*test_func)(void) = my_test;
```

This is literally just storing the memory address `0x400500` (where the function starts).

#### When You Call It:
```c
test_func();  // Same as: jump to address 0x400500
```

The CPU jumps to that memory address and starts executing instructions.

### How Functions Cross Process Boundaries

Here's the key insight: **functions are stateless code, but they can't directly cross process boundaries**. Let me explain what really happens:

#### ❌ What DOESN'T Happen:
- Function code is NOT copied between processes
- Function pointers are NOT valid across processes
- Memory addresses are different in each process

#### ✅ What ACTUALLY Happens:

##### Key Insight: fork() Creates Identical Memory Spaces

When `fork()` is called:

1. **Child process gets an EXACT copy of parent's memory**
2. **Same code is at the same virtual addresses**
3. **Function pointers remain valid because they point to the same virtual addresses**

##### Example:
```c
// In parent process:
void my_test() { printf("test\n"); }  // Lives at virtual address 0x400500
void (*ptr)(void) = my_test;          // ptr = 0x400500

fork();  // Create child process

// In child process:
my_test();  // STILL at virtual address 0x400500!
ptr();      // ptr still contains 0x400500, and it's still valid!
```

### Virtual Memory Makes This Possible

#### Each Process Has Its Own Virtual Memory Space:
```
Parent Process Virtual Memory:
0x400500: my_test function code
0x600000: tests[] array
0x600100: function pointer = 0x400500

Child Process Virtual Memory:
0x400500: my_test function code (SAME!)
0x600000: tests[] array (SAME!)
0x600100: function pointer = 0x400500 (STILL VALID!)
```

#### The OS Maps Virtual → Physical Differently:
```
Virtual Address 0x400500 in Parent → Physical RAM 0x12345000
Virtual Address 0x400500 in Child  → Physical RAM 0x67890000
```

But the **function pointer value stays the same** because it's a virtual address!

### Why the Pipe Transfer Works

Looking at the code:

```c
// Parent sends the entire tests array through pipe
write(pipe_write, tests, sizeof(tests));

// Child receives it
read(pipe_read, tests, sizeof(tests));
```

#### What Gets Transferred:
```c
struct tk_testcase {
    int enabled;
    const char *name;        // String literal address
    const char *loc;         // String literal address  
    void (*utest)(void);     // Function pointer (virtual address)
    // ...
};
```

#### Why Function Pointers Still Work:
1. **String literals** are in the code section - same virtual address in both processes
2. **Function pointers** point to code section - same virtual address in both processes  
3. **fork() copied all the code** - functions exist at the same addresses

### Functions Are Stateless, But Context Matters

#### Functions ARE Stateless:
```c
void add_numbers(int a, int b) {
    return a + b;  // No internal state
}
```

#### But They Can Access Global State:
```c
int global_counter = 0;

void increment() {
    global_counter++;  // Accesses global state
}
```

#### In TestKit:
- Functions are stateless code
- But they can access global variables like `tests[]`
- Each process has its own copy of global variables
- fork() ensures the child has the same global state as parent

## Why It All Works Together

### The Complete Picture

#### What Really Happens:
1. **Compilation:** Functions become machine code at specific virtual addresses
2. **Registration:** Function pointers (addresses) stored in structs
3. **fork():** Child gets identical virtual memory layout
4. **Pipe transfer:** Struct data (including function pointers) sent to child
5. **Execution:** Child calls function pointers, which jump to the same virtual addresses

#### Why It Works:
- Functions are just **instructions in memory**
- Virtual memory makes **same addresses valid in both processes**
- fork() ensures **identical code layout**
- Function pointers are just **numbers** (addresses) that can be copied

### The Magic Trick Summary

The TestKit framework works because:

1. **Macros generate code** that automatically registers tests
2. **Constructor functions** run before main() to set up the test infrastructure
3. **fork() creates identical memory spaces** where function pointers remain valid
4. **Shared memory (mmap)** allows test results to be communicated between processes
5. **Process isolation** ensures that crashed tests don't affect other tests
6. **Virtual memory** makes it possible for function pointers to work across process boundaries

This design prioritizes **robustness** over **simplicity** - it's designed to handle the worst possible test scenarios without breaking the test runner itself.

## Key Takeaways for C Beginners

1. **Functions are just code in memory** - they're sequences of machine instructions at specific addresses
2. **Function pointers are just addresses** - they tell the CPU where to jump to execute code
3. **fork() creates identical memory spaces** - child processes can use the same function pointers as parents
4. **Macros can generate complex code** - the preprocessor is very powerful for creating DSLs
5. **Process isolation is powerful** - separate processes can't crash each other
6. **Virtual memory enables sharing** - same virtual addresses can map to different physical memory
7. **Constructor functions run before main()** - useful for automatic initialization

The TestKit framework is a masterclass in advanced C programming techniques, combining low-level system programming with high-level abstractions to create a robust testing framework.