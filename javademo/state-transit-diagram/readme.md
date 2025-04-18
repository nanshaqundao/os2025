# JDI的两种调试方式比较（更新版）

让我为您总结JDI调试Java程序的两种主要方式，并提供最终的代码和配置示例，特别注意区分编译时和运行时参数。

## 1. 启动连接器方式(Launch Connector)

这种方式由JDI调试程序直接启动被调试程序。

### 代码实现

```java
package org.example;

import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.util.*;
import java.io.*;

public class FibonacciStateVisualizer {
    private VirtualMachine vm;
    private final List<StateNode> stateNodes = new ArrayList<>();
    private final Map<Long, StateNode> threadCallMap = new HashMap<>();
    private int nodeCounter = 0;

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java org.example.FibonacciStateVisualizer <n>");
            return;
        }
        
        String n = args[0];
        new FibonacciStateVisualizer().run(n);
    }

    private void run(String n) {
        try {
            // 获取启动连接器
            LaunchingConnector connector = Bootstrap.virtualMachineManager().defaultConnector();
            
            // 设置启动参数
            Map<String, Connector.Argument> arguments = connector.defaultArguments();
            arguments.get("main").setValue("org.example.Fibonacci");
            arguments.get("options").setValue(n);
            
            System.out.println("启动参数: main=" + arguments.get("main").value() 
                              + ", options=" + arguments.get("options").value());
            
            // 启动VM
            vm = connector.launch(arguments);
            System.out.println("成功启动目标VM");
            
            // 设置事件请求
            EventRequestManager erm = vm.eventRequestManager();
            
            // 创建方法入口和出口请求
            MethodEntryRequest methodEntryRequest = erm.createMethodEntryRequest();
            methodEntryRequest.addClassFilter("org.example.Fibonacci");
            methodEntryRequest.enable();
            
            MethodExitRequest methodExitRequest = erm.createMethodExitRequest();
            methodExitRequest.addClassFilter("org.example.Fibonacci");
            methodExitRequest.enable();
            
            // 处理事件
            EventQueue eventQueue = vm.eventQueue();
            boolean connected = true;
            
            while (connected) {
                EventSet eventSet = eventQueue.remove();
                
                for (Event event : eventSet) {
                    if (event instanceof MethodEntryEvent) {
                        handleMethodEntry((MethodEntryEvent) event);
                    } else if (event instanceof MethodExitEvent) {
                        handleMethodExit((MethodExitEvent) event);
                    } else if (event instanceof VMDeathEvent || event instanceof VMDisconnectEvent) {
                        connected = false;
                    }
                }
                
                eventSet.resume();
            }
            
            // 生成状态图
            generateDotGraph("fibonacci_" + n + "_state_graph.dot");
            
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    
    // 处理方法入口事件
    private void handleMethodEntry(MethodEntryEvent event) {
        try {
            Method method = event.method();
            // 只关注fibonacci方法
            if (!"fibonacci".equals(method.name())) {
                return;
            }
            
            ThreadReference thread = event.thread();
            if (!thread.frames().isEmpty()) {
                StackFrame frame = thread.frame(0);
                
                // 获取参数n的值
                LocalVariable nVar = null;
                for (LocalVariable var : frame.visibleVariables()) {
                    if (var.name().equals("n")) {
                        nVar = var;
                        break;
                    }
                }
                
                if (nVar != null) {
                    IntegerValue nValue = (IntegerValue) frame.getValue(nVar);
                    int n = nValue.value();
                    
                    System.out.println("进入 fibonacci(" + n + ")");
                    
                    // 创建新的状态节点
                    StateNode node = new StateNode(nodeCounter++, "fibonacci", n, 0, thread.uniqueID());
                    stateNodes.add(node);
                    
                    // 建立调用关系
                    if (threadCallMap.containsKey(thread.uniqueID())) {
                        StateNode parent = threadCallMap.get(thread.uniqueID());
                        parent.addChild(node);
                    }
                    
                    // 更新当前线程的调用节点
                    threadCallMap.put(thread.uniqueID(), node);
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    
    private void handleMethodExit(MethodExitEvent event) {
        try {
            Method method = event.method();
            // 只关注fibonacci方法
            if (!"fibonacci".equals(method.name())) {
                return;
            }
            
            ThreadReference thread = event.thread();
            
            // 获取返回值
            Value returnValue = event.returnValue();
            if (returnValue instanceof IntegerValue) {
                int result = ((IntegerValue) returnValue).value();
                
                // 更新当前节点的返回值
                if (threadCallMap.containsKey(thread.uniqueID())) {
                    StateNode currentNode = threadCallMap.get(thread.uniqueID());
                    currentNode.setReturnValue(result);
                    
                    System.out.println("退出 fibonacci(" + currentNode.getParamValue() + ") = " + result);
                    
                    // 找到父节点
                    for (StateNode node : stateNodes) {
                        if (node.getThreadId() == thread.uniqueID() && 
                            node.hasChildNode(currentNode.getId())) {
                            threadCallMap.put(thread.uniqueID(), node);
                            break;
                        }
                    }
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    
    private void generateDotGraph(String fileName) {
        try (PrintWriter writer = new PrintWriter(new FileWriter(fileName))) {
            writer.println("digraph FibonacciStates {");
            writer.println("  rankdir=LR;");
            writer.println("  node [shape=box, style=filled, fillcolor=lightblue];");
            
            // 输出所有节点
            for (StateNode node : stateNodes) {
                writer.println("  node" + node.getId() + " [label=\"fibonacci(" + 
                               node.getParamValue() + ")\\nreturn " + node.getReturnValue() + "\"];");
            }
            
            // 输出所有边
            for (StateNode node : stateNodes) {
                for (StateNode child : node.getChildren()) {
                    writer.println("  node" + node.getId() + " -> node" + child.getId() + ";");
                }
            }
            
            writer.println("}");
        } catch (IOException e) {
            e.printStackTrace();
        }
    }
    
    static class StateNode {
        private final int id;
        private final String methodName;
        private final int paramValue;
        private int returnValue;
        private final long threadId;
        private final List<StateNode> children = new ArrayList<>();
        
        public StateNode(int id, String methodName, int paramValue, int returnValue, long threadId) {
            this.id = id;
            this.methodName = methodName;
            this.paramValue = paramValue;
            this.returnValue = returnValue;
            this.threadId = threadId;
        }
        
        public int getId() {
            return id;
        }
        
        public String getMethodName() {
            return methodName;
        }
        
        public int getParamValue() {
            return paramValue;
        }
        
        public int getReturnValue() {
            return returnValue;
        }
        
        public void setReturnValue(int returnValue) {
            this.returnValue = returnValue;
        }
        
        public long getThreadId() {
            return threadId;
        }
        
        public void addChild(StateNode child) {
            children.add(child);
        }
        
        public List<StateNode> getChildren() {
            return children;
        }
        
        public boolean hasChildNode(int childId) {
            for (StateNode child : children) {
                if (child.getId() == childId) {
                    return true;
                }
            }
            return false;
        }
    }
}
```

### 正确配置设置

#### 编译器配置（IntelliJ IDEA）
- **设置路径**: File → Settings → Build, Execution, Deployment → Compiler → Java Compiler
- **附加命令行参数**:
  ```
  --add-exports jdk.jdi/com.sun.jdi=ALL-UNNAMED --add-exports jdk.jdi/com.sun.tools.jdi=ALL-UNNAMED
  ```

#### 运行配置
- **Main class**: `org.example.FibonacciStateVisualizer`
- **Program arguments**: `5`
- **VM options**:
  ```
  --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.util=ALL-UNNAMED
  ```

#### Maven运行命令
```bash
# 编译时
mvn compile -Dmaven.compiler.argument="--add-exports jdk.jdi/com.sun.jdi=ALL-UNNAMED --add-exports jdk.jdi/com.sun.tools.jdi=ALL-UNNAMED"

# 运行时
mvn exec:java -Dexec.mainClass="org.example.FibonacciStateVisualizer" -Dexec.args="5" -Dexec.commandlineArgs="--add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.util=ALL-UNNAMED"
```

## 2. 附加连接器方式(Attach Connector)

这种方式先启动被调试程序，然后调试程序连接到它。

### 代码实现

```java
package org.example;

import com.sun.jdi.*;
import com.sun.jdi.connect.*;
import com.sun.jdi.event.*;
import com.sun.jdi.request.*;
import java.util.*;
import java.io.*;

public class FibonacciStateVisualizer {
    private VirtualMachine vm;
    private final List<StateNode> stateNodes = new ArrayList<>();
    private final Map<Long, StateNode> threadCallMap = new HashMap<>();
    private int nodeCounter = 0;

    public static void main(String[] args) {
        if (args.length < 1) {
            System.out.println("Usage: java org.example.FibonacciStateVisualizer <n>");
            return;
        }
        
        String n = args[0];
        new FibonacciStateVisualizer().run(n);
    }

    private void run(String n) {
        try {
            // 查找Socket附加连接器
            AttachingConnector connector = null;
            for (AttachingConnector conn : Bootstrap.virtualMachineManager().attachingConnectors()) {
                if (conn.name().equals("com.sun.jdi.SocketAttach")) {
                    connector = conn;
                    break;
                }
            }
            
            if (connector == null) {
                System.err.println("未找到Socket附加连接器");
                return;
            }
            
            // 设置连接参数
            Map<String, Connector.Argument> arguments = connector.defaultArguments();
            arguments.get("hostname").setValue("localhost");
            arguments.get("port").setValue("8000");
            
            System.out.println("正在连接到目标VM: localhost:8000");
            
            // 连接到VM
            vm = connector.attach(arguments);
            System.out.println("成功连接到目标VM");
            
            // 设置事件请求
            EventRequestManager erm = vm.eventRequestManager();
            
            // 创建方法入口和出口请求
            MethodEntryRequest methodEntryRequest = erm.createMethodEntryRequest();
            methodEntryRequest.addClassFilter("org.example.Fibonacci");
            methodEntryRequest.enable();
            
            MethodExitRequest methodExitRequest = erm.createMethodExitRequest();
            methodExitRequest.addClassFilter("org.example.Fibonacci");
            methodExitRequest.enable();
            
            // 处理事件
            EventQueue eventQueue = vm.eventQueue();
            boolean connected = true;
            
            while (connected) {
                EventSet eventSet = eventQueue.remove();
                
                for (Event event : eventSet) {
                    if (event instanceof MethodEntryEvent) {
                        handleMethodEntry((MethodEntryEvent) event);
                    } else if (event instanceof MethodExitEvent) {
                        handleMethodExit((MethodExitEvent) event);
                    } else if (event instanceof VMDeathEvent || event instanceof VMDisconnectEvent) {
                        connected = false;
                    }
                }
                
                eventSet.resume();
            }
            
            // 生成状态图
            generateDotGraph("fibonacci_" + n + "_state_graph.dot");
            
        } catch (Exception e) {
            e.printStackTrace();
        }
    }
    
    // 处理方法入口和出口事件、生成DOT图等方法的实现与前面相同
    // ...
}
```

### 正确配置设置

#### 被调试程序(Fibonacci)配置
- **运行配置**:
    - **Main class**: `org.example.Fibonacci`
    - **Program arguments**: `5`
    - **VM options**: `-agentlib:jdwp=transport=dt_socket,server=y,suspend=y,address=*:8000`

#### 调试器(FibonacciStateVisualizer)配置

##### 编译器配置（IntelliJ IDEA）
- **设置路径**: File → Settings → Build, Execution, Deployment → Compiler → Java Compiler
- **附加命令行参数**:
  ```
  --add-exports jdk.jdi/com.sun.jdi=ALL-UNNAMED --add-exports jdk.jdi/com.sun.tools.jdi=ALL-UNNAMED
  ```

##### 运行配置
- **Main class**: `org.example.FibonacciStateVisualizer`
- **Program arguments**: `5`
- **VM options**:
  ```
  --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.util=ALL-UNNAMED
  ```

#### 命令行运行步骤
```bash
# 步骤1: 编译调试器程序
javac --add-exports jdk.jdi/com.sun.jdi=ALL-UNNAMED --add-exports jdk.jdi/com.sun.tools.jdi=ALL-UNNAMED org/example/FibonacciStateVisualizer.java

# 步骤2: 启动被调试程序
java -agentlib:jdwp=transport=dt_socket,server=y,suspend=y,address=*:8000 org.example.Fibonacci 5

# 步骤3: 启动调试器
java --add-opens java.base/java.lang=ALL-UNNAMED --add-opens java.base/java.util=ALL-UNNAMED org.example.FibonacciStateVisualizer 5
```

## 区分编译时和运行时参数的重要性

在JDK 9及以后版本中，Java模块系统使得区分编译时参数和运行时参数变得至关重要：

### 编译时参数
- `--add-exports` 参数用于允许访问特定模块中的非公开API
- 这些参数必须传递给javac编译器
- 在IntelliJ中应设置在编译器选项中，不应放在运行配置的VM选项中

### 运行时参数
- `--add-opens` 参数用于允许运行时反射访问类
- 这些参数必须传递给java运行时
- 应设置在IntelliJ的运行配置VM选项中

混合这两类参数会导致编译错误和运行时问题，这就是为什么必须将它们分开配置。

## 总结

两种JDI连接方式各有优缺点，但附加连接器方式在现代JDK中通常更可靠。无论使用哪种方式，正确区分编译时和运行时参数都是确保JDI程序能够正常工作的关键。

在实际开发中，附加连接器方式更接近专业调试工具的工作方式，提供了更清晰的关注点分离和更好的灵活性。