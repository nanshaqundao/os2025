package org.demo;

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
            System.out.println("Usage: java org.demo.FibonacciStateVisualizer <n>");
            return;
        }

        String n = args[0];
        new FibonacciStateVisualizer().run(n);
    }

    private void run(String n) {
        try {
            // 使用附加连接器而不是启动连接器
            System.out.println("正在寻找Socket附加连接器...");

            AttachingConnector connector = null;
            List<AttachingConnector> connectors = Bootstrap.virtualMachineManager().attachingConnectors();

            for (AttachingConnector conn : connectors) {
                System.out.println("找到连接器: " + conn.name());
                if (conn.name().equals("com.sun.jdi.SocketAttach")) {
                    connector = conn;
                    System.out.println("选择连接器: " + conn.name());
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

            // 对所有类添加类准备请求
            ClassPrepareRequest classPrepareRequest = erm.createClassPrepareRequest();
            classPrepareRequest.addClassFilter("org.example.Fibonacci");
            classPrepareRequest.enable();

            // 对方法入口和出口添加请求
            MethodEntryRequest methodEntryRequest = erm.createMethodEntryRequest();
            methodEntryRequest.addClassFilter("org.example.Fibonacci");
            methodEntryRequest.enable();

            MethodExitRequest methodExitRequest = erm.createMethodExitRequest();
            methodExitRequest.addClassFilter("org.example.Fibonacci");
            methodExitRequest.enable();

            // 处理事件
            System.out.println("开始事件循环");
            EventQueue eventQueue = vm.eventQueue();
            boolean connected = true;

            while (connected) {
                EventSet eventSet = eventQueue.remove();

                for (Event event : eventSet) {
                    System.out.println("接收事件: " + event);

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

            // 生成图
            generateDotGraph("fibonacci_" + n + "_state_graph.dot");
            System.out.println("状态图已生成: fibonacci_" + n + "_state_graph.dot");

        } catch (Exception e) {
            e.printStackTrace();
        }
    }

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

                    // 恢复到父调用节点
                    try {
                        // 找到可能的父节点
                        for (StateNode node : stateNodes) {
                            if (node.getThreadId() == thread.uniqueID() &&
                                    node.hasChildNode(currentNode.getId())) {
                                threadCallMap.put(thread.uniqueID(), node);
                                break;
                            }
                        }
                    } catch (Exception e) {
                        // 忽略可能的线程状态异常
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

    /**
     * 表示函数调用的状态节点
     */
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